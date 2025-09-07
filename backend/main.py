import os
import shutil
import sqlite3
import pandas as pd
import yaml
import hashlib
import re
import secrets
from datetime import datetime, timedelta
import random
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any, Tuple
from pydantic import BaseModel

# Assuming parser.py will contain the core parsing logic
from parser import parse_log_data
from relationship_extractor import RelationshipExtractor
from communication_filters import CommunicationFilters
from data_normalizer import DataNormalizer
from communication_mapping import CommunicationMapper
from suspicious_activity_detector import SuspiciousActivityDetector
from search_query_system import SearchQuerySystem, SearchCriteria, SearchOperator, SortOrder
from enrichment import IPEntityEnricher

app = FastAPI()

# --- CORS Middleware ---
# Restrict origin; can be overridden by FRONTEND_ORIGIN env var
origins = [os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
SQLite persistence
------------------
We persist users and sessions in a lightweight SQLite database (backend/app.db).
This replaces the previous in-memory storage for users/sessions while keeping
data processing components in memory as before.
"""

DB_PATH = os.path.join(os.path.dirname(__file__), "app.db")

def get_db_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_db_conn()
    cur = conn.cursor()
    # Users table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            password_salt TEXT,
            role TEXT NOT NULL,
            name TEXT,
            post TEXT,
            district TEXT,
            thana TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # Ensure password_salt column exists (for older DBs)
    try:
        cur.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in cur.fetchall()]
        if 'password_salt' not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")
    except Exception:
        pass
    # Sessions table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
        )
        """
    )
    # Audit logs table
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    # Cases tables (basic case management)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_by TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS saved_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER NOT NULL,
            criteria_json TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(case_id) REFERENCES cases(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()

    # Seed default users if they don't exist
    def ensure_user(username: str, password_plain: str, role: str) -> None:
        cur.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        if cur.fetchone() is None:
            salt_hex, hash_hex = hash_password_pbkdf2(password_plain)
            cur.execute(
                "INSERT INTO users (username, email, password_hash, password_salt, role, name, created_at) VALUES (?, NULL, ?, ?, ?, ?, ?)",
                (
                    username,
                    hash_hex,
                    salt_hex,
                    role,
                    username,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    ensure_user("admin", "admin", "administrator")
    ensure_user("analyst", "analyst", "analyst")
    conn.close()

# --- Password hashing utilities (PBKDF2) ---
def hash_password_pbkdf2(password: str) -> (str, str):
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 150_000)
    return salt.hex(), hash_bytes.hex()

def verify_password_pbkdf2(password: str, salt_hex: str, hash_hex: str) -> bool:
    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        test = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 150_000)
        return secrets.compare_digest(test, expected)
    except Exception:
        return False

def log_action(username: Optional[str], action: str, details: str = "") -> None:
    try:
        conn = get_db_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_logs (username, action, details, created_at) VALUES (?, ?, ?, ?)",
            (username, action, details[:1000], datetime.now().isoformat()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

# --- In-memory storage for analytics (unchanged) ---
processed_data_store = pd.DataFrame()
relationship_extractor = None
communication_filters = None
communication_mapper = None
suspicious_activity_detector = None
search_query_system = None
data_normalizer = DataNormalizer()
UPLOAD_DIR = "uploads"
ALLOWLIST_IPS: set = set()
DENYLIST_IPS: set = set()
ip_enricher: Optional[IPEntityEnricher] = None
CASE_ANALYSES: Dict[int, Dict[str, Any]] = {}

# --- Authentication ---
security = HTTPBearer()

def require_role(allowed_roles: List[str]):
    def role_checker(credentials: HTTPAuthorizationCredentials = Depends(security)):
        token = credentials.credentials
        session = get_session(token)
        if not session:
            raise HTTPException(status_code=401, detail="Unauthorized")
        user = get_user_by_username(session.get("username"))
        if not user or user.get("role") not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return session
    return role_checker

#########################
# User/Session Utilities #
#########################

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def insert_user(user: Dict[str, Any]) -> None:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO users (username, email, password_hash, password_salt, role, name, post, district, thana, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user["username"],
            user.get("email"),
            user["password_hash"],
            user.get("password_salt"),
            user.get("role", "analyst"),
            user.get("name"),
            user.get("profile", {}).get("post"),
            user.get("profile", {}).get("district"),
            user.get("profile", {}).get("thana"),
            user.get("created_at", datetime.now().isoformat()),
        ),
    )
    conn.commit()
    conn.close()

def create_session(token: str, username: str, expires_at: datetime) -> None:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, username, datetime.now().isoformat(), expires_at.isoformat()),
    )
    conn.commit()
    conn.close()

def get_session(token: str) -> Optional[Dict[str, Any]]:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM sessions WHERE token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(token: str) -> None:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()

def delete_sessions_for_username(username: str) -> None:
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM sessions WHERE username = ?", (username,))
    conn.commit()
    conn.close()

# Pydantic models for requests
class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    success: bool
    username: str = ""
    token: str = ""
    message: str = ""

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
    post: str
    district: str
    thana: str

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    post: Optional[str] = None
    district: Optional[str] = None
    thana: Optional[str] = None

class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str

# Authentication functions
def authenticate_user(username_or_email: str, password: str) -> bool:
    """Authenticate by username or official email using SQLite."""
    user = get_user_by_username(username_or_email)
    if not user:
        user = get_user_by_email(username_or_email)
    if not user:
        return False
    # Prefer PBKDF2 with salt
    salt = user.get("password_salt")
    if salt:
        if verify_password_pbkdf2(password, salt, user.get("password_hash", "")):
            return True
        return False
    # Fallback to legacy SHA-256, and upgrade on success
    legacy_ok = user.get("password_hash") == hashlib.sha256(password.encode()).hexdigest()
    if legacy_ok:
        try:
            salt_hex, hash_hex = hash_password_pbkdf2(password)
            conn = get_db_conn()
            cur = conn.cursor()
            cur.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE username = ?", (hash_hex, salt_hex, user["username"]))
            conn.commit()
            conn.close()
        except Exception:
            pass
    return legacy_ok

def create_access_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=24)
    create_session(token, username, expires_at)
    return token

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    token = credentials.credentials
    session = get_session(token)
    if session:
        # Parse dates
        expires_at = datetime.fromisoformat(session["expires_at"]) if isinstance(session["expires_at"], str) else session["expires_at"]
        if datetime.now() < expires_at:
            return session
        # session expired -> delete
        delete_session(token)
    raise HTTPException(status_code=401, detail="Invalid or expired token")

@app.on_event("startup")
def startup_event():
    # Initialize SQLite DB and seed defaults
    init_db()
    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    # Load optional investigative config (allow/deny IPs)
    config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                cfg = yaml.safe_load(f) or {}
                allow = cfg.get('allowlist_ips', [])
                deny = cfg.get('denylist_ips', [])
                global ALLOWLIST_IPS, DENYLIST_IPS
                ALLOWLIST_IPS = set(map(str, allow or []))
                DENYLIST_IPS = set(map(str, deny or []))
        except Exception:
            ALLOWLIST_IPS.clear(); DENYLIST_IPS.clear()
    # Initialize IP enricher (loads local CSV cache if present)
    global ip_enricher
    ip_enricher = IPEntityEnricher(os.path.dirname(__file__))

@app.get("/")
def read_root():
    return {"message": "IPDR Analysis Backend is running."}

# --- Authentication Endpoints ---
@app.post("/auth/login")
async def login(request: LoginRequest):
    if authenticate_user(request.username, request.password):
        # Resolve canonical username from DB (could be a username or an email)
        user = get_user_by_username(request.username)
        if not user:
            user = get_user_by_email(request.username)
        canonical_username = user["username"] if user else request.username
        token = create_access_token(canonical_username)
        log_action(canonical_username, "login", "successful")
        return {
            "success": True,
            "username": canonical_username,
            "token": token,
            "message": "Login successful"
        }
    else:
        log_action(None, "login", f"failed for {request.username}")
        return {
            "success": False,
            "message": "Invalid username or password"
        }

@app.post("/auth/register")
async def register(request: RegisterRequest):
    """
    Simple in-memory registration for demo purposes.
    Username is the email's local part by default; we store the full email.
    """
    # Basic email validation to avoid optional dependency on email-validator
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", request.email or ""):
        raise HTTPException(status_code=400, detail="Invalid email format")

    email_lower = request.email.lower()

    # Choose username as full email to keep uniqueness simple for registered users
    username = email_lower

    # Prevent duplicates by username or email in DB
    if get_user_by_username(username) or get_user_by_email(email_lower):
        raise HTTPException(status_code=400, detail="User with this email already exists")

    salt_hex, hash_hex = hash_password_pbkdf2(request.password)
    insert_user({
        "username": username,
        "password_hash": hash_hex,
        "password_salt": salt_hex,
        "role": "analyst",
        "email": email_lower,
        "name": request.name,
        "profile": {
            "post": request.post,
            "district": request.district,
            "thana": request.thana,
        },
        "created_at": datetime.now().isoformat(),
    })

    # Auto-login after registration (frontend may ignore this token)
    token = create_access_token(username)
    log_action(username, "register", "user registered")
    return {
        "success": True,
        "username": username,
        "token": token,
        "message": "Registration successful"
    }

@app.post("/auth/logout")
async def logout(session: Dict = Depends(verify_token)):
    delete_sessions_for_username(session["username"]) 
    log_action(session.get("username"), "logout", "user logged out")
    return {"success": True, "message": "Logged out successfully"}

@app.get("/auth/verify")
async def verify_session(session: Dict = Depends(verify_token)):
    return {
        "success": True,
        "username": session["username"],
        "valid": True
    }

@app.get("/auth/me")
async def get_profile(session: Dict = Depends(verify_token)):
    user = get_user_by_username(session["username"]) or {}
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "username": user.get("username"),
        "email": user.get("email"),
        "role": user.get("role"),
        "name": user.get("name"),
        "post": user.get("post"),
        "district": user.get("district"),
        "thana": user.get("thana"),
        "created_at": user.get("created_at"),
    }

@app.put("/auth/profile")
async def update_profile(payload: ProfileUpdateRequest, session: Dict = Depends(verify_token)):
    updates = {k: v for k, v in payload.dict().items() if v is not None}
    if not updates:
        return {"success": True, "message": "No changes"}
    conn = get_db_conn()
    cur = conn.cursor()
    set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
    params = list(updates.values()) + [session["username"]]
    cur.execute(f"UPDATE users SET {set_clause} WHERE username = ?", params)
    conn.commit()
    conn.close()
    return {"success": True, "message": "Profile updated"}

@app.post("/auth/change-password")
async def change_password(payload: PasswordChangeRequest, session: Dict = Depends(verify_token)):
    user = get_user_by_username(session["username"]) or {}
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    # Verify current password (PBKDF2 if salt present, else legacy SHA-256)
    salt = user.get("password_salt")
    ok = False
    if salt:
        ok = verify_password_pbkdf2(payload.current_password, salt, user.get("password_hash", ""))
    else:
        ok = (user.get("password_hash") == hashlib.sha256(payload.current_password.encode()).hexdigest())
    if not ok:
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    # Set new PBKDF2 hash and salt
    salt_hex, hash_hex = hash_password_pbkdf2(payload.new_password)
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("UPDATE users SET password_hash = ?, password_salt = ? WHERE username = ?", (hash_hex, salt_hex, session["username"]))
    conn.commit()
    conn.close()
    # Invalidate all sessions for this user
    delete_sessions_for_username(session["username"])
    log_action(session.get("username"), "change_password", "password updated and sessions invalidated")
    return {"success": True, "message": "Password changed. Please log in again."}

def _persist_processed_data(df: pd.DataFrame, base_name: str = "processed") -> Optional[str]:
    try:
        out_dir = UPLOAD_DIR
        if not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)
        # Try parquet first
        out_path_parquet = os.path.join(out_dir, f"{base_name}.parquet")
        try:
            df.to_parquet(out_path_parquet, index=False)
            os.chmod(out_path_parquet, 0o600)
            return out_path_parquet
        except Exception:
            out_path_csv = os.path.join(out_dir, f"{base_name}.csv")
            df.to_csv(out_path_csv, index=False)
            os.chmod(out_path_csv, 0o600)
            return out_path_csv
    except Exception:
        return None

@app.post("/process-data")
async def process_data(persist: bool = False, chunksize: Optional[int] = None):
    """
    Processes the synthetic.csv file from the Scenario A1-ARFF folder.
    """
    global processed_data_store, relationship_extractor, communication_filters, communication_mapper, suspicious_activity_detector, search_query_system, data_normalizer
    
    file_path = "../Scenario A1-ARFF/synthetic.csv"
    
    try:
        processed_data_store = data_normalizer.normalize_file(file_path, chunksize=chunksize)
        normalization_stats = data_normalizer.get_normalization_stats()
        
        # Initialize all analysis modules with the processed data
        if not processed_data_store.empty:
            relationship_extractor = RelationshipExtractor(processed_data_store, allowlist_ips=ALLOWLIST_IPS, denylist_ips=DENYLIST_IPS)
            communication_filters = CommunicationFilters(processed_data_store)
            communication_mapper = CommunicationMapper(processed_data_store)
            suspicious_activity_detector = SuspiciousActivityDetector(processed_data_store)
            search_query_system = SearchQuerySystem(processed_data_store)

        saved_path = _persist_processed_data(processed_data_store, "processed") if persist else None
        response = {
            "message": f"File 'synthetic.csv' processed successfully.",
            "records_found": len(processed_data_store),
            "normalization_stats": normalization_stats,
            "persisted": bool(saved_path),
            "output_path": saved_path
        }
        log_action(None, "process_data", f"rows={len(processed_data_store)} persisted={bool(saved_path)}")
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

def _process_data_job(file_path: str, persist: bool = False, chunksize: Optional[int] = None):
    global processed_data_store, relationship_extractor, communication_filters, communication_mapper, suspicious_activity_detector, search_query_system
    try:
        df = data_normalizer.normalize_file(file_path, chunksize=chunksize)
        processed_data_store = df
        if not df.empty:
            relationship_extractor = RelationshipExtractor(df, allowlist_ips=ALLOWLIST_IPS, denylist_ips=DENYLIST_IPS)
            communication_filters = CommunicationFilters(df)
            communication_mapper = CommunicationMapper(df)
            suspicious_activity_detector = SuspiciousActivityDetector(df)
            search_query_system = SearchQuerySystem(df)
            if persist:
                _persist_processed_data(df, "processed_async")
        log_action(None, "process_data_async", f"rows={len(df)}")
    except Exception as e:
        log_action(None, "process_data_async_error", str(e))

@app.post("/process-data/async")
async def process_data_async(background_tasks: BackgroundTasks, persist: bool = False, chunksize: Optional[int] = None):
    file_path = "../Scenario A1-ARFF/synthetic.csv"
    background_tasks.add_task(_process_data_job, file_path, persist, chunksize)
    return {"message": "Processing started in background", "file": os.path.basename(file_path)}

@app.get("/data")
def get_data(query: Optional[str] = None):
    """Returns the processed data, with optional search."""
    global processed_data_store
    if processed_data_store.empty:
        return []

    df = processed_data_store
    if query:
        # Search across all columns for the query string
        mask = df.apply(lambda x: x.astype(str).str.contains(query, case=False)).any(axis=1)
        df = df[mask]

    return df.to_dict(orient="records")

@app.get("/graph")
def get_graph_data(limit: int = 100):
    """
    Returns data formatted for a network graph.
    Limits the number of rows processed to prevent browser overload.
    """
    global processed_data_store
    if processed_data_store.empty:
        return {"nodes": [], "edges": []}

    # Limit the dataframe to avoid overly large graphs
    df = processed_data_store.head(limit)

    node_ids = set()
    nodes = []
    edge_pairs = set()

    def add_node(node_id: str, label: str):
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({"id": node_id, "label": label})

    def add_edge(from_id: str, to_id: str):
        pair = (from_id, to_id)
        if pair not in edge_pairs:
            edge_pairs.add(pair)

    for _, row in df.iterrows():
        # Build typed IDs to avoid collisions and duplicates
        source_raw = str(row["Source IP"])
        target_raw = str(row["Destination IP"])
        source_id = f"ip:{source_raw}"
        target_id = f"ip:{target_raw}"
        add_node(source_id, source_raw)
        add_node(target_id, target_raw)
        add_edge(source_id, target_id)

        # Also include phone numbers when available (skip placeholder)
        phone_val = row.get("Phone") if isinstance(row, dict) else row["Phone"]
        if pd.notna(phone_val):
            phone_str = str(phone_val)
            if phone_str and phone_str != "+910000000000":
                phone_id = f"phone:{phone_str}"
                add_node(phone_id, phone_str)
                add_edge(phone_id, source_id)

    edges = [{"from": f, "to": t} for (f, t) in edge_pairs]

    return {"nodes": nodes, "edges": edges}

@app.get("/relationships")
def get_relationships():
    """
    Returns A-Party to B-Party relationships extracted from the uploaded data.
    """
    global relationship_extractor
    if not relationship_extractor:
        return {"error": "No data uploaded or relationship extractor not initialized"}
    
    try:
        relationships = relationship_extractor.extract_relationships()
        return {"relationships": relationships, "count": len(relationships)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error extracting relationships: {str(e)}")

@app.get("/relationships/summary")
def get_relationship_summary():
    """
    Returns summarized A-Party and B-Party statistics.
    """
    global relationship_extractor
    if not relationship_extractor:
        return {"error": "No data uploaded or relationship extractor not initialized"}
    
    try:
        return {
            "a_party_summary": relationship_extractor.get_a_party_summary(),
            "b_party_summary": relationship_extractor.get_b_party_summary(),
            "b_party_phone_summary": relationship_extractor.get_b_party_phone_summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating summary: {str(e)}")

@app.get("/relationships/bparty-summary")
def get_bparty_summary():
    """Explicit B-Party summary for both destination IPs and phones (if present)."""
    global relationship_extractor
    if not relationship_extractor:
        return {"error": "No data uploaded or relationship extractor not initialized"}
    try:
        return {
            "b_party_ip_summary": relationship_extractor.get_b_party_summary(),
            "b_party_phone_summary": relationship_extractor.get_b_party_phone_summary(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating B-Party summary: {str(e)}")

@app.get("/enrich/ip")
def enrich_ip(ip: str):
    """Enrich single IP from offline cache + classification."""
    global ip_enricher
    if not ip:
        raise HTTPException(status_code=400, detail="ip query param required")
    enr = ip_enricher.enrich_ip(ip) if ip_enricher else {"ip": ip}
    return {"enrichment": enr}

@app.get("/correlation/a2b")
def correlation_a2b(limit: int = 100):
    """
    Build A-party to B-party correlation edges with weights (counts).
    A label preference: Phone -> SubscriberID -> Source IP
    B label preference: B-Phone -> Destination IP
    limit: number of top edges by count to include.
    """
    global processed_data_store
    if processed_data_store.empty:
        return {"nodes": [], "edges": [], "top_pairs": []}

    df = processed_data_store.copy()

    def choose_a(row):
        phone = str(row.get('Phone', '')).strip()
        if phone and phone != '+910000000000':
            return phone, 'phone'
        subs = str(row.get('SubscriberID', '')).strip()
        if subs:
            return subs, 'subscriber'
        sip = str(row.get('Source IP', '')).strip()
        return sip, 'ip'

    def choose_b(row):
        bphone = str(row.get('B-Phone', '')).strip()
        if bphone and bphone != '+910000000000':
            return bphone, 'phone'
        dip = str(row.get('Destination IP', '')).strip()
        return dip, 'ip'

    a_labels = []
    b_labels = []
    for _, r in df.iterrows():
        a_lab, _ = choose_a(r)
        b_lab, _ = choose_b(r)
        a_labels.append(a_lab)
        b_labels.append(b_lab)
    df['_A_Label'] = a_labels
    df['_B_Label'] = b_labels

    grouped = df.groupby(['_A_Label', '_B_Label']).size().reset_index(name='count')
    grouped = grouped.sort_values('count', ascending=False).head(limit)

    nodes = []
    node_ids = set()
    edges = []
    top_pairs = []

    for _, row in grouped.iterrows():
        a = str(row['_A_Label'])
        b = str(row['_B_Label'])
        c = int(row['count'])
        a_id = f"a:{a}"
        b_id = f"b:{b}"
        if a_id not in node_ids:
            node_ids.add(a_id)
            a_shape = 'circle' if a.startswith('+') else 'box'
            nodes.append({"id": a_id, "label": a, "group": "a", "shape": a_shape})
        if b_id not in node_ids:
            node_ids.add(b_id)
            b_shape = 'circle' if b.startswith('+') else 'box'
            nodes.append({"id": b_id, "label": b, "group": "b", "shape": b_shape})
        edges.append({"from": a_id, "to": b_id, "value": c})
        top_pairs.append({"a": a, "b": b, "count": c})

    return {"nodes": nodes, "edges": edges, "top_pairs": top_pairs}

# =============================
# GEO MAP VIEWS (Plotly HTML)
# =============================

def _parse_dt_safe(val: Any) -> Optional[datetime]:
    try:
        if isinstance(val, datetime):
            return val
        return datetime.strptime(str(val), "%Y-%m-%d-%H:%M:%S")
    except Exception:
        try:
            return datetime.fromisoformat(str(val))
        except Exception:
            return None

def _make_details_html_from_row(row: pd.Series) -> str:
    fields = [
        'Protocol','Source IP','Source Port','Destination IP','Destination Port','Start Time','End Time','Duration',
        'NAT IP','NAT Port','Device','UserID','SubscriberID','CustName','Address','Email','Phone','Alt-Phone',
        'CustID','IP Type','Latitude','Longitude','B-Phone','B-SubscriberID','B-CustName'
    ]
    def val(k):
        try:
            return str(row.get(k, ''))
        except Exception:
            return ''
    rows = ''.join([f"<tr><td style='font-weight:600;padding-right:8px'>{k}</td><td>{val(k)}</td></tr>" for k in fields])
    # Tiny 1x1 placeholder PNG (light gray)
    dummy_img = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAuMBg2O7pW4AAAAASUVORK5CYII="
    )
    html = f"""
    <div style='display:flex;gap:12px;align-items:flex-start'>
      <img src='data:image/png;base64,{dummy_img}' alt='profile' style='width:64px;height:64px;border-radius:4px;border:1px solid #ccc' />
      <table style='font-size:12px'>{rows}</table>
    </div>
    """
    return html

def _build_plotly_map_html(points: List[Dict[str, Any]], title: str = "Geo Map") -> str:
    import json
    # Read Mapbox token from environment if available
    mapbox_token = os.getenv("MAPBOX_TOKEN") or os.getenv("MAPBOX_ACCESS_TOKEN") or ""
    # Prepare arrays
    lats = [p.get('lat', 0.0) for p in points]
    lons = [p.get('lon', 0.0) for p in points]
    texts = [p.get('label', '') for p in points]
    colors = [p.get('color', 'blue') for p in points]
    details = [p.get('details_html', '') for p in points]
    sizes = [p.get('size', 12) for p in points]
    # Map with in-place floating flash card on pin click
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'/>
  <script src='https://cdn.plot.ly/plotly-2.26.0.min.js'></script>
  <style>
    body {{ margin:0;background:#111;color:#ddd;font-family:Arial, sans-serif; }}
    .title {{ padding:8px 10px; }}
    #mapWrap {{ position:relative; width:100%; height:520px; }}
    #map {{ width:100%; height:100%; }}
    .tip-card {{ position:absolute; display:none; max-width:360px; background:#1e1e1e; border:1px solid #444; border-radius:8px; box-shadow:0 6px 24px rgba(0,0,0,0.4); padding:8px; z-index:9; }}
    .tip-card .close {{ float:right; cursor:pointer; color:#ccc; font-weight:bold; margin-left:8px; }}
  </style>
  <title>{title}</title>
  </head>
<body>
  <div class='title'><h4 style='margin:6px 0'>{title}</h4></div>
  <div id='mapWrap'>
    <div id='map'></div>
    <div id='tip' class='tip-card'></div>
  </div>
  <script>
    const lats = {json.dumps(lats)};
    const lons = {json.dumps(lons)};
    const texts = {json.dumps(texts)};
    const colors = {json.dumps(colors)};
    const details = {json.dumps(details)};
    const sizes = {json.dumps(sizes)};
    if (typeof Plotly === 'undefined') {{
      const warn = document.createElement('div');
      warn.style.color = '#ddd';
      warn.style.padding = '10px';
      warn.textContent = 'Unable to load Plotly library. Please ensure internet access or allow CDN domains.';
      document.getElementById('mapWrap').appendChild(warn);
    }} else {{
    const data = [{{
      type: 'scattermapbox',
      lat: lats,
      lon: lons,
      text: texts,
      mode: 'markers',
      marker: {{ size: sizes, color: colors }},
      hoverinfo: 'text',
      customdata: details
    }}];
    const layout = {{
      mapbox: {{ style: 'open-street-map' }},
      margin: {{ t:0, r:0, b:0, l:0 }},
      paper_bgcolor: '#111',
      plot_bgcolor: '#111',
    }};
    Plotly.newPlot('map', data, layout).then(g => {{
      const wrap = document.getElementById('mapWrap');
      const tip = document.getElementById('tip');
      const mapDiv = document.getElementById('map');
      function showTip(html, x, y) {{
        tip.innerHTML = "<div class='close' onclick=\"this.parentElement.style.display='none'\">×</div>" + (html || 'No details');
        const rect = wrap.getBoundingClientRect();
        const left = Math.max(6, Math.min(x - rect.left + 12, rect.width - 370));
        const top = Math.max(6, Math.min(y - rect.top + 12, rect.height - 220));
        tip.style.left = left + 'px';
        tip.style.top = top + 'px';
        tip.style.display = 'block';
      }}
      g.on('plotly_click', (ev) => {{
        try {{
          const cd = ev.points[0].customdata;
          const e = ev.event || window.event;
          const x = e.clientX; const y = e.clientY;
          showTip(cd, x, y);
        }} catch(e) {{ }}
      }});
    }});
    }}
  </script>
</body>
</html>
    """

def _build_leaflet_map_html(points: List[Dict[str, Any]], polylines: List[Dict[str, Any]] = None, title: str = "Geo Map") -> str:
    import json
    polylines = polylines or []
    # Compute center
    if points:
        clat = sum(float(p.get('lat', 0.0)) for p in points)/max(1,len(points))
        clon = sum(float(p.get('lon', 0.0)) for p in points)/max(1,len(points))
    else:
        clat, clon = 20.5937, 78.9629  # India approx center
    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset='utf-8'/>
  <title>{title}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin=""/>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
  <style>
    body {{ margin:0;background:#111;color:#ddd;font-family:Arial,sans-serif; }}
    .title {{ padding:8px 10px; }}
    #map {{ width:100%; height:520px; }}
    .leaflet-container {{ background:#111; }}
    /* Dark themed popup for high-contrast text */
    .leaflet-popup-content-wrapper {{
      background:#1e1e1e; color:#eaeaea; border:1px solid #444;
      box-shadow:0 6px 24px rgba(0,0,0,0.4);
    }}
    .leaflet-popup-tip {{ background:#1e1e1e; border:1px solid #444; }}
    .leaflet-popup-content, .leaflet-popup-content table, .leaflet-popup-content td {{ color:#eaeaea; }}
    .leaflet-popup-close-button {{ color:#ccc !important; }}
  </style>
</head>
<body>
  <div class='title'><h4 style='margin:6px 0'>{title}</h4></div>
  <div id='map'></div>
  <script>
    const points = {json.dumps(points)};
    const lines = {json.dumps(polylines)};
    const map = L.map('map', {{ zoomControl:true }}).setView([{clat}, {clon}], 5);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19 }}).addTo(map);
    // Add markers with popups (use visible dot markers for all points)
    points.forEach(p => {{
      if (!p || p.lat===undefined || p.lon===undefined) return;
      const color = p.color || '#8E24AA';
      const size = (p.size||12);
      const r = Math.max(4, Math.floor(size/2));
      const popupHtml = (p.details_html || '').toString();
      const m = L.circleMarker([p.lat, p.lon], {{
        radius: r,
        color: '#ffffff',        // bright border for visibility on dark map
        weight: 2,
        fillColor: color,        // inner fill shows type (phone/police)
        fillOpacity: 0.95
      }}).addTo(map);
      m.bindPopup(popupHtml, {{ maxWidth: 380, className: 'dark-popup' }});
      m.bindTooltip(p.label || '', {{ direction: 'top' }});
    }});
    // Add polylines
    lines.forEach(l => {{
      if (!l || !l.path || l.path.length < 2) return;
      L.polyline(l.path, {{ color: l.color || '#000', weight: l.weight || 3, dashArray: l.dash || '8 6', opacity: 0.95 }}).addTo(map);
    }});
  </script>
</body>
</html>
    """

@app.get("/map/suspicious-phones/html")
def map_suspicious_phones_html(days: int = 7, limit: int = 100):
    """Plot suspicious phones' last locations within the past N days."""
    global processed_data_store
    if processed_data_store.empty:
        return HTMLResponse("<html><body>No data loaded</body></html>", media_type='text/html')
    df = processed_data_store.copy()
    # Parse Start time and window
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfw = df[df['__dt'] >= window_start]
    # Heuristic suspicion
    def is_suspicious(r):
        try:
            port = int(r.get('Destination Port', 0))
            dur = int(r.get('Duration', 0))
            tt = _parse_dt_safe(r.get('Start Time')) or datetime.now()
            off = (tt.hour >= 22 or tt.hour <= 5)
            if port in [22,23,3389,5900] or dur > 300 or off:
                return True
        except Exception:
            return False
        return False
    dfw = dfw[dfw.apply(is_suspicious, axis=1)]
    # Last record per phone
    dfw = dfw[dfw['Phone'].astype(str) != '+910000000000']
    if dfw.empty:
        return HTMLResponse("<html><body>No suspicious phones found in window</body></html>", media_type='text/html')
    idx = dfw.groupby('Phone')['__dt'].idxmax()
    last = dfw.loc[idx]
    # Build points
    pts = []
    for _, r in last.head(limit).iterrows():
        details_html = _make_details_html_from_row(r)
        pts.append({
            'lat': float(r.get('Latitude', 0.0) or 0.0),
            'lon': float(r.get('Longitude', 0.0) or 0.0),
            'label': f"{r.get('Phone','')} — {r.get('CustName','')}",
            'color': '#8E24AA',  # purple for suspicious
            'size': 12,
            'details_html': details_html,
        })
    html = _build_leaflet_map_html(pts, title=f"Suspicious Phones — Last {days} Days")
    return HTMLResponse(html, media_type='text/html')

@app.get("/map/suspicious-phones-network/html")
def map_suspicious_phones_network_html(days: int = 7, limit: int = 200):
    """
    Suspicious phones (last N days) plotted with a network overlay:
    - Nodes: suspicious phones' last locations
    - Edges (dashed red): direct phone->phone communications within window (Phone == A and B-Phone == B)
    - Edges (dotted blue): inferred links via shared destination IPs
    - If no edges exist, create a simple ring among first few suspicious phones to showcase network
    """
    global processed_data_store
    if processed_data_store.empty:
        return HTMLResponse("<html><body>No data loaded</body></html>", media_type='text/html')

    df = processed_data_store.copy()
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfw = df[df['__dt'] >= window_start]

    # Suspicion heuristic (same as earlier)
    def is_suspicious(r):
        try:
            port = int(r.get('Destination Port', 0))
            dur = int(r.get('Duration', 0))
            tt = _parse_dt_safe(r.get('Start Time')) or datetime.now()
            off = (tt.hour >= 22 or tt.hour <= 5)
            if port in [22, 23, 3389, 5900] or dur > 300 or off:
                return True
        except Exception:
            return False
        return False

    dfw = dfw[dfw.apply(is_suspicious, axis=1)]
    dfw = dfw[dfw['Phone'].astype(str) != '+910000000000']
    if dfw.empty:
        return HTMLResponse("<html><body>No suspicious phones found in window</body></html>", media_type='text/html')

    # Last record per phone
    idx = dfw.groupby('Phone')['__dt'].idxmax()
    last = dfw.loc[idx]
    if last.empty:
        return HTMLResponse("<html><body>No suspicious phones found in window</body></html>", media_type='text/html')

    phones = last['Phone'].astype(str).tolist()
    phone_set = set(phones)

    # Build points
    points = []
    phone_coords = {}
    for _, r in last.head(limit).iterrows():
        phone = str(r.get('Phone',''))
        lat = float(r.get('Latitude', 0.0) or 0.0)
        lon = float(r.get('Longitude', 0.0) or 0.0)
        if lat == 0.0 and lon == 0.0:
            continue
        phone_coords[phone] = (lat, lon, r)
        points.append({
            'lat': lat,
            'lon': lon,
            'label': f"{phone} — {r.get('CustName','')}",
            'color': '#8E24AA',
            'size': 12,
            'details_html': _make_details_html_from_row(r)
        })

    # Prepare line arrays
    direct_lats, direct_lons = [], []  # dashed red
    infer_lats, infer_lons = [], []    # dotted blue

    # Direct communications among suspicious phones
    if 'B-Phone' in dfw.columns:
        dsub = df[(df['__dt'] >= window_start)]
        # Only rows where both phones in suspicious set
        dsub = dsub[(dsub['Phone'].astype(str).isin(phone_set)) & (dsub['B-Phone'].astype(str).isin(phone_set))]
        seen_pairs = set()
        for _, row in dsub.iterrows():
            a = str(row.get('Phone',''))
            b = str(row.get('B-Phone',''))
            if a == b:
                continue
            key = tuple(sorted([a,b]))
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            if a in phone_coords and b in phone_coords:
                lat1, lon1, _ = phone_coords[a]
                lat2, lon2, _ = phone_coords[b]
                direct_lats += [lat1, lat2, None]
                direct_lons += [lon1, lon2, None]

    # Inferred links via shared destination IPs
    ip_groups = dfw.groupby('Destination IP')
    for ip, group in ip_groups:
        phs = group['Phone'].astype(str).unique().tolist()
        phs = [p for p in phs if p in phone_coords]
        if len(phs) < 2:
            continue
        # Connect all pairs
        for i in range(len(phs)):
            for j in range(i+1, len(phs)):
                p1, p2 = phs[i], phs[j]
                lat1, lon1, _ = phone_coords[p1]
                lat2, lon2, _ = phone_coords[p2]
                infer_lats += [lat1, lat2, None]
                infer_lons += [lon1, lon2, None]

    # If no relations found, create a simple ring among first few nodes to showcase
    if not direct_lats and not infer_lats:
        keys = list(phone_coords.keys())[:min(8, len(phone_coords))]
        for i in range(len(keys)):
            p1 = keys[i]
            p2 = keys[(i+1) % len(keys)]
            lat1, lon1, _ = phone_coords[p1]
            lat2, lon2, _ = phone_coords[p2]
            infer_lats += [lat1, lat2, None]
            infer_lons += [lon1, lon2, None]

    # Convert lat/lon sequences into Leaflet polylines
    def to_pairs(lat_list, lon_list):
        pairs = []
        for i in range(0, min(len(lat_list), len(lon_list)), 3):
            if i + 1 < len(lat_list) and lat_list[i] is not None and lat_list[i+1] is not None:
                try:
                    a = [float(lat_list[i]), float(lon_list[i])]
                    b = [float(lat_list[i+1]), float(lon_list[i+1])]
                    pairs.append([a, b])
                except Exception:
                    continue
        return pairs
    lines = []
    # Direct phone-to-phone links: dashed red, heavier stroke
    for seg in to_pairs(direct_lats, direct_lons):
        lines.append({'path': seg, 'color': '#E53935', 'weight': 3, 'dash': '10 6'})
    # Inferred links via shared destination IPs: dotted/short-dash blue, lighter stroke
    for seg in to_pairs(infer_lats, infer_lons):
        lines.append({'path': seg, 'color': '#1E88E5', 'weight': 2, 'dash': '4 6'})
    html = _build_leaflet_map_html(points, lines, title=f"Suspicious Phones Network — Last {days} Days")
    return HTMLResponse(html, media_type='text/html')

@app.get("/map/conversation/html")
def map_conversation_html(phone_a: str, phone_b: str, days: int = 7):
    """Plot two people's last known locations with roles and categories."""
    global processed_data_store
    if processed_data_store.empty:
        return HTMLResponse("<html><body>No data loaded</body></html>", media_type='text/html')
    df = processed_data_store.copy()
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfw = df[df['__dt'] >= window_start]

    # Normalize input to E.164 (+91) to match normalized dataset
    import re as _re
    def _normalize_phone_input(p: str) -> str:
        digits = _re.sub(r"\D", "", str(p or ""))
        if not digits:
            return ""
        # Handle 10-digit local
        if len(digits) == 10:
            return "+91" + digits
        # Handle 12-digit starting with 91
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits
        # Handle trunk '0' prefix 11-digit
        if len(digits) == 11 and digits.startswith("0"):
            return "+91" + digits[1:]
        # Fallback
        return "+" + digits

    def last_record_for_phone(pn: str) -> Optional[pd.Series]:
        pn_norm = _normalize_phone_input(pn)
        d = dfw[dfw['Phone'].astype(str) == pn_norm]
        if d.empty:
            return None
        return d.loc[d['__dt'].idxmax()]

    arow = last_record_for_phone(phone_a)
    brow = last_record_for_phone(phone_b)
    if arow is None and brow is None:
        return HTMLResponse("<html><body>No records for given phones in window</body></html>", media_type='text/html')

    def categorize(r: Optional[pd.Series]) -> str:
        if r is None:
            return 'unknown'
        try:
            port = int(r.get('Destination Port', 0))
            dur = int(r.get('Duration', 0))
            tt = _parse_dt_safe(r.get('Start Time')) or datetime.now()
            off = (tt.hour >= 22 or tt.hour <= 5)
            if port in [22,23,3389,5900] or dur > 300 or off:
                return 'suspicious'
        except Exception:
            pass
        return 'genuine'

    cat_a = categorize(arow)
    cat_b = categorize(brow)

    pts = []
    if arow is not None:
        pts.append({
            'lat': float(arow.get('Latitude', 0.0) or 0.0),
            'lon': float(arow.get('Longitude', 0.0) or 0.0),
            'label': f"A (caller): {arow.get('Phone','')} — {arow.get('CustName','')}",
            'color': '#E53935' if cat_a=='suspicious' else '#F44336',  # red shades
            'size': 14,
            'details_html': _make_details_html_from_row(arow),
        })
    if brow is not None:
        pts.append({
            'lat': float(brow.get('Latitude', 0.0) or 0.0),
            'lon': float(brow.get('Longitude', 0.0) or 0.0),
            'label': f"B (callee): {brow.get('Phone','')} → {brow.get('B-Phone','')}",
            'color': '#FB8C00' if cat_b=='suspicious' else '#FFA726',  # orange shades
            'size': 14,
            'details_html': _make_details_html_from_row(brow),
        })

    html = _build_plotly_map_html(pts, title=f"Conversation Map — A: {phone_a} vs B: {phone_b} ({cat_a} / {cat_b})")
    return HTMLResponse(html, media_type='text/html')

# =============================
# CASE AI ANALYSIS + MAP VIEW
# =============================

@app.post("/cases/{case_id}/ai-analyze")
async def ai_analyze_case(case_id: int, case_file: UploadFile = File(...), dataset_file: UploadFile = File(...), llm_prompt: Optional[str] = None, provider: str = "auto", chunksize: Optional[int] = None):
    """
    Accept a case document and a raw IPDR dataset, run analysis (A->B mapping, suspicious detection),
    and store results under the given case_id for visualization. This simulates LLM-assisted analysis
    by leveraging local analytics modules (normalizer, relationship extractor, suspicious detector).
    """
    if not case_file.filename or not dataset_file.filename:
        raise HTTPException(status_code=400, detail="Both case_file and dataset_file are required")
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    case_path = os.path.join(UPLOAD_DIR, f"case_{case_id}_{case_file.filename}")
    data_path = os.path.join(UPLOAD_DIR, f"case_{case_id}_{dataset_file.filename}")
    try:
        # Save uploads
        with open(case_path, "wb") as bf:
            shutil.copyfileobj(case_file.file, bf)
        with open(data_path, "wb") as df:
            shutil.copyfileobj(dataset_file.file, df)

        # Normalize and analyze dataset
        df = data_normalizer.normalize_file(data_path, provider=provider, chunksize=chunksize)
        if df.empty:
            CASE_ANALYSES.pop(case_id, None)
            raise HTTPException(status_code=400, detail="Uploaded dataset produced no records after normalization")

        CASE_ANALYSES[case_id] = {
            "df": df,
            "last_updated": datetime.now().isoformat(),
            "llm_prompt": llm_prompt or "",
            "provider": provider,
            "rows": len(df),
        }
        # Clean temp dataset file; keep case doc
        try:
            os.remove(data_path)
        except Exception:
            pass
        return {
            "case_id": case_id,
            "rows": len(df),
            "message": "Case analysis stored. View map via /map/case-network/html?case_id=...",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing case dataset: {str(e)}")

@app.get("/map/case-network/html")
def map_case_network_html(case_id: int, days: int = 7, limit: int = 200):
    """
    Render a case-specific network map:
    - Flag (🚩) markers for suspicious phones' last locations in the past N days
    - Dashed lines between linked phones (direct via B-Phone, inferred via shared destination IPs)
    - Pin (📍) markers for nearest police stations per city with hypothetical incharge cards
    """
    if case_id not in CASE_ANALYSES:
        return HTMLResponse("<html><body>No case analysis found. Upload via Cases tab.</body></html>", media_type='text/html')
    df = CASE_ANALYSES[case_id]["df"]
    if df.empty:
        return HTMLResponse("<html><body>No data available for this case</body></html>", media_type='text/html')

    dfx = df.copy()
    dfx['__dt'] = dfx['Start Time'].apply(_parse_dt_safe)
    max_dt = dfx['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfx = dfx[dfx['__dt'] >= window_start]

    def is_suspicious(r):
        try:
            port = int(r.get('Destination Port', 0))
            dur = int(r.get('Duration', 0))
            tt = _parse_dt_safe(r.get('Start Time')) or datetime.now()
            off = (tt.hour >= 22 or tt.hour <= 5)
            if port in [22, 23, 3389, 5900] or dur > 300 or off:
                return True
        except Exception:
            return False
        return False

    dfx = dfx[dfx['Phone'].astype(str) != '+910000000000']
    dfx = dfx[dfx.apply(is_suspicious, axis=1)]
    if dfx.empty:
        return HTMLResponse("<html><body>No suspicious phones found in case window</body></html>", media_type='text/html')

    # Last record per phone
    idx = dfx.groupby('Phone')['__dt'].idxmax()
    last = dfx.loc[idx]

    # Build phone points (flags)
    phone_coords = {}
    points = []
    for _, r in last.head(limit).iterrows():
        phone = str(r.get('Phone',''))
        lat = float(r.get('Latitude', 0.0) or 0.0)
        lon = float(r.get('Longitude', 0.0) or 0.0)
        if lat == 0.0 and lon == 0.0:
            continue
        phone_coords[phone] = (lat, lon, r)
        points.append({
            'lat': lat,
            'lon': lon,
            'label': f"{phone} — {r.get('CustName','')}",
            'color': '#8E24AA',
            'size': 16,
            'icon': 'flag',
            'details_html': _make_details_html_from_row(r)
        })

    # Edges: direct and inferred
    direct_lats, direct_lons = [], []
    infer_lats, infer_lons = [], []
    if 'B-Phone' in dfx.columns:
        dsub = dfx[(dfx['Phone'].astype(str).isin(phone_coords.keys())) & (dfx['B-Phone'].astype(str).isin(phone_coords.keys()))]
        seen = set()
        for _, row in dsub.iterrows():
            a = str(row.get('Phone',''))
            b = str(row.get('B-Phone',''))
            if a == b:
                continue
            key = tuple(sorted([a,b]))
            if key in seen:
                continue
            seen.add(key)
            if a in phone_coords and b in phone_coords:
                lat1, lon1, _ = phone_coords[a]
                lat2, lon2, _ = phone_coords[b]
                direct_lats += [lat1, lat2, None]
                direct_lons += [lon1, lon2, None]

    # Inferred via shared Destination IPs
    for ip, group in dfx.groupby('Destination IP'):
        phs = [p for p in group['Phone'].astype(str).unique().tolist() if p in phone_coords]
        if len(phs) < 2:
            continue
        for i in range(len(phs)):
            for j in range(i+1, len(phs)):
                p1, p2 = phs[i], phs[j]
                lat1, lon1, _ = phone_coords[p1]
                lat2, lon2, _ = phone_coords[p2]
                infer_lats += [lat1, lat2, None]
                infer_lons += [lon1, lon2, None]

    # Dummy showcase ring if none
    if not direct_lats and not infer_lats:
        keys = list(phone_coords.keys())[:min(8, len(phone_coords))]
        for i in range(len(keys)):
            p1 = keys[i]
            p2 = keys[(i+1) % len(keys)]
            lat1, lon1, _ = phone_coords[p1]
            lat2, lon2, _ = phone_coords[p2]
            infer_lats += [lat1, lat2, None]
            infer_lons += [lon1, lon2, None]

    # Police stations per city (hypothetical incharge)
    def extract_city(addr: str) -> str:
        try:
            if not addr:
                return ''
            parts = str(addr).split(',')
            return parts[-2].strip() if len(parts) >= 2 else parts[-1].strip()
        except Exception:
            return ''

    city_points: Dict[str, List[Tuple[float,float]]] = {}
    for _, r in last.iterrows():
        city = extract_city(r.get('Address',''))
        if not city:
            continue
        lat = float(r.get('Latitude', 0.0) or 0.0)
        lon = float(r.get('Longitude', 0.0) or 0.0)
        if lat == 0.0 and lon == 0.0:
            continue
        city_points.setdefault(city, []).append((lat, lon))

    def avg(coords: List[Tuple[float,float]]) -> Tuple[float,float]:
        if not coords:
            return (0.0, 0.0)
        la = sum(c[0] for c in coords) / len(coords)
        lo = sum(c[1] for c in coords) / len(coords)
        return (la, lo)

    def fake_incharge(city: str) -> Tuple[str, str]:
        first = random.choice(["Rajesh","Anita","Vikram","Pooja","Amit","Neha","Arun","Kiran"])  # hypothetical
        lastn = random.choice(["Sharma","Singh","Verma","Patel","Kumar","Yadav","Reddy","Das"])  # hypothetical
        phone = "+91" + str(random.randint(6000000000, 9999999999))
        return (f"Inspector {first} {lastn} ({city})", phone)

    for city, coords in city_points.items():
        la, lo = avg(coords)
        if la == 0.0 and lo == 0.0:
            continue
        inc, ph = fake_incharge(city)
        card = f"<div style='font-size:12px'><b>Police Station</b><br/>City: {city}<br/>Incharge: {inc}<br/>Phone: {ph}</div>"
        points.append({
            'lat': la,
            'lon': lo,
            'label': f"Police Station - {city}",
            'icon': 'pin',
            'size': 18,
            'details_html': card,
            'color': '#FFC107',
        })

    # Convert lat/lon sequences into Leaflet polylines
    def to_pairs(lat_list, lon_list):
        pairs = []
        for i in range(0, min(len(lat_list), len(lon_list)), 3):
            if i + 1 < len(lat_list) and lat_list[i] is not None and lat_list[i+1] is not None:
                try:
                    a = [float(lat_list[i]), float(lon_list[i])]
                    b = [float(lat_list[i+1]), float(lon_list[i+1])]
                    pairs.append([a, b])
                except Exception:
                    continue
        return pairs

    lines = []
    for seg in to_pairs(direct_lats, direct_lons):
        lines.append({'path': seg, 'color': '#E53935', 'weight': 3, 'dash': '10 6'})
    for seg in to_pairs(infer_lats, infer_lons):
        lines.append({'path': seg, 'color': '#1E88E5', 'weight': 2, 'dash': '4 6'})

    html = _build_leaflet_map_html(points, lines, title=f"Case {case_id} — AI Network Map (Last {days} Days)")
    return HTMLResponse(html, media_type='text/html')

# =============================
# LINK ANALYSIS (Top connections for a suspect phone)
# =============================

@app.get("/link-analysis/phone")
def link_analysis_phone(phone: str, limit: int = 10, days: int = 30):
    """
    Build a small ego-network for the suspect phone showing top N connections.
    Uses Phone (A) -> B-Phone when available, otherwise Destination IP.
    Also considers rows where suspect appears as B-Phone (callee) and connects other A-phones to suspect.
    Returns nodes/edges for a simple network graph.
    """
    global processed_data_store
    if processed_data_store.empty:
        return {"nodes": [], "edges": []}

    df = processed_data_store.copy()
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    df = df[df['__dt'] >= window_start]

    import re as _re
    def _normalize_phone_input(p: str) -> str:
        digits = _re.sub(r"\D", "", str(p or ""))
        if not digits:
            return ""
        if len(digits) == 10:
            return "+91" + digits
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits
        if len(digits) == 11 and digits.startswith("0"):
            return "+91" + digits[1:]
        return "+" + digits

    suspect = _normalize_phone_input(phone)
    if not suspect:
        return {"nodes": [], "edges": []}

    # Suspect as A (caller)
    df_a = df[df['Phone'].astype(str) == suspect]
    # Suspect as B (callee)
    df_b = df[df.get('B-Phone', '').astype(str) == suspect] if 'B-Phone' in df.columns else pd.DataFrame()

    # Build neighbor tallies
    from collections import Counter
    neigh = Counter()
    # A->B
    if not df_a.empty:
        for _, r in df_a.iterrows():
            tgt = str(r.get('B-Phone', '')).strip()
            if not tgt:
                tgt = str(r.get('Destination IP', '')).strip()
                if tgt:
                    tgt = f"ip:{tgt}"
            else:
                tgt = f"phone:{tgt}"
            if tgt:
                neigh[tgt] += 1
    # other A -> suspect (as B)
    if not df_b.empty:
        for _, r in df_b.iterrows():
            src = str(r.get('Phone', '')).strip()
            if src:
                src = f"phone:{src}"
                neigh[src] += 1

    # Top N neighbors
    top = neigh.most_common(max(1, limit))

    nodes = []
    edges = []
    node_ids = set()

    def add_node(nid: str, label: str, group: str):
        if nid not in node_ids:
            node_ids.add(nid)
            nodes.append({"id": nid, "label": label, "group": group})

    # Suspect node
    suspect_id = f"phone:{suspect}"
    add_node(suspect_id, suspect, "suspect")

    for nid, cnt in top:
        if nid.startswith('phone:'):
            label = nid.split(':',1)[1]
            add_node(nid, label, "phone")
        elif nid.startswith('ip:'):
            label = nid.split(':',1)[1]
            add_node(nid, label, "ip")
        else:
            # Fallback assume ip label
            label = nid
            add_node(nid, label, "ip")
        edges.append({"from": suspect_id, "to": nid, "value": int(cnt)})

    return {"nodes": nodes, "edges": edges}

# Backward-compatible alias with trailing slash (some proxies trim differently)
@app.get("/link-analysis/phone/")
def link_analysis_phone_alias(phone: str, limit: int = 10, days: int = 30):
    return link_analysis_phone(phone=phone, limit=limit, days=days)

@app.get("/link-analysis/phone-map/html")
def link_analysis_phone_map_html(phone: str, limit: int = 10, days: int = 30):
    """
    Plot suspect phone and its top connections on a map.
    - Suspect located by last record where Phone == suspect within window
    - Neighbor phones located by their last record where Phone == neighbor (fallback: where B-Phone == neighbor)
    - Neighbor IPs located by last record where Destination IP == ip
    Draws lines from suspect to each neighbor.
    """
    global processed_data_store
    if processed_data_store.empty:
        return HTMLResponse("<html><body>No data loaded</body></html>", media_type='text/html')

    df = processed_data_store.copy()
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfw = df[df['__dt'] >= window_start]

    import re as _re
    def _normalize_phone_input(p: str) -> str:
        digits = _re.sub(r"\D", "", str(p or ""))
        if not digits:
            return ""
        if len(digits) == 10:
            return "+91" + digits
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits
        if len(digits) == 11 and digits.startswith("0"):
            return "+91" + digits[1:]
        return "+" + digits

    suspect = _normalize_phone_input(phone)
    if not suspect:
        return HTMLResponse("<html><body>Invalid phone</body></html>", media_type='text/html')

    # Suspect last position
    dfa = dfw[dfw['Phone'].astype(str) == suspect]
    srow = None
    if not dfa.empty:
        srow = dfa.loc[dfa['__dt'].idxmax()]
    elif 'B-Phone' in dfw.columns:
        dfb = dfw[dfw['B-Phone'].astype(str) == suspect]
        if not dfb.empty:
            srow = dfb.loc[dfb['__dt'].idxmax()]
    if srow is None:
        return HTMLResponse("<html><body>No records for suspect within window</body></html>", media_type='text/html')

    # Build neighbor counts (reuse link logic quickly)
    from collections import Counter
    neigh = Counter()
    # As A (caller)
    if not dfa.empty:
        for _, r in dfa.iterrows():
            tgt = str(r.get('B-Phone', '')).strip()
            if not tgt:
                dip = str(r.get('Destination IP', '')).strip()
                if dip:
                    neigh[f"ip:{dip}"] += 1
            else:
                neigh[f"phone:{tgt}"] += 1
    # As B (callee)
    if 'B-Phone' in dfw.columns:
        dfb = dfw[dfw['B-Phone'].astype(str) == suspect]
        for _, r in dfb.iterrows():
            src = str(r.get('Phone', '')).strip()
            if src:
                neigh[f"phone:{src}"] += 1

    top = neigh.most_common(max(1, limit))

    # Helper to get last lat/lon for an identifier
    def last_coords_for_phone(ph: str):
        d = dfw[dfw['Phone'].astype(str) == ph]
        if not d.empty:
            rw = d.loc[d['__dt'].idxmax()]
            return float(rw.get('Latitude', 0.0) or 0.0), float(rw.get('Longitude', 0.0) or 0.0), rw
        if 'B-Phone' in dfw.columns:
            d2 = dfw[dfw['B-Phone'].astype(str) == ph]
            if not d2.empty:
                rw = d2.loc[d2['__dt'].idxmax()]
                return float(rw.get('Latitude', 0.0) or 0.0), float(rw.get('Longitude', 0.0) or 0.0), rw
        return 0.0, 0.0, None

    def last_coords_for_ip(ip: str):
        d = dfw[dfw['Destination IP'].astype(str) == ip]
        if not d.empty:
            rw = d.loc[d['__dt'].idxmax()]
            return float(rw.get('Latitude', 0.0) or 0.0), float(rw.get('Longitude', 0.0) or 0.0), rw
        return 0.0, 0.0, None

    # Suspect point
    points = []
    s_lat = float(srow.get('Latitude', 0.0) or 0.0)
    s_lon = float(srow.get('Longitude', 0.0) or 0.0)
    points.append({
        'lat': s_lat,
        'lon': s_lon,
        'label': f"Suspect: {suspect}",
        'color': '#2E7D32',
        'size': 14,
        'details_html': _make_details_html_from_row(srow)
    })

    # Lines arrays
    line_lats = []
    line_lons = []

    # Neighbor points and collect co-occurrence sets for IPs
    ip_phone_sets: Dict[str, set] = {}
    for nid, cnt in top:
        if nid.startswith('phone:'):
            ph = nid.split(':', 1)[1]
            lat, lon, row = last_coords_for_phone(ph)
            if lat == 0.0 and lon == 0.0:
                continue
            points.append({
                'lat': lat,
                'lon': lon,
                'label': f"{ph} (x{cnt})",
                'color': '#66BB6A',
                'size': 12,
                'details_html': _make_details_html_from_row(row) if row is not None else ''
            })
            line_lats += [s_lat, lat, None]
            line_lons += [s_lon, lon, None]
        elif nid.startswith('ip:'):
            ip = nid.split(':', 1)[1]
            lat, lon, row = last_coords_for_ip(ip)
            if lat == 0.0 and lon == 0.0:
                continue
            points.append({
                'lat': lat,
                'lon': lon,
                'label': f"{ip} (x{cnt})",
                'color': '#42A5F5',
                'size': 12,
                'details_html': _make_details_html_from_row(row) if row is not None else ''
            })
            line_lats += [s_lat, lat, None]
            line_lons += [s_lon, lon, None]
            iphones = set(dfw[dfw['Destination IP'].astype(str) == ip]['Phone'].astype(str).tolist())
            ip_phone_sets[ip] = iphones

    # Neighbor<->neighbor (IP-IP) dotted lines when sharing any phone
    pair_lats: List[float] = []
    pair_lons: List[float] = []
    ip_keys = list(ip_phone_sets.keys())
    max_pairs = 200
    pair_count = 0
    for i in range(len(ip_keys)):
        for j in range(i + 1, len(ip_keys)):
            if pair_count >= max_pairs:
                break
            ip1, ip2 = ip_keys[i], ip_keys[j]
            s1, s2 = ip_phone_sets.get(ip1, set()), ip_phone_sets.get(ip2, set())
            if s1 and s2 and (s1 & s2):
                lat1, lon1, _ = last_coords_for_ip(ip1)
                lat2, lon2, _ = last_coords_for_ip(ip2)
                if (lat1 == 0.0 and lon1 == 0.0) or (lat2 == 0.0 and lon2 == 0.0):
                    continue
                pair_lats += [lat1, lat2, None]
                pair_lons += [lon1, lon2, None]
                pair_count += 1

    # Build HTML with markers + lines
    import json
    markers_html = _build_plotly_map_html(points, title=f"Link Analysis Map — {suspect}")
    inject = f"""
<script>
(function(){{
  const mapDiv = document.getElementById('map');
  Plotly.addTraces(mapDiv, [{{
    type:'scattermapbox', mode:'lines', lat:{json.dumps(line_lats)}, lon:{json.dumps(line_lons)},
    line:{{color:'#BDBDBD', width:2, dash:'dash'}}, hoverinfo:'skip'
  }},{{
    type:'scattermapbox', mode:'lines', lat:{json.dumps(pair_lats)}, lon:{json.dumps(pair_lons)},
    line:{{color:'#90CAF9', width:1, dash:'dot'}}, hoverinfo:'skip'
  }}]);
}})();
</script>
"""
    html = markers_html.replace('</body>\n</html>', inject + '</body>\n</html>')
    return HTMLResponse(html, media_type='text/html')

@app.get("/link-analysis/phone-phone-map/html")
def link_analysis_phone_phone_map_html(phone: str, limit: int = 10, days: int = 30):
    """
    Phone-only network on map:
    - Suspect phone (blue)
    - Connected phones (red)
    - Dashed lines between suspect and all connected phones
    - Dashed lines between any connected phones that directly communicated with each other
    """
    global processed_data_store
    if processed_data_store.empty:
        return HTMLResponse("<html><body>No data loaded</body></html>", media_type='text/html')

    df = processed_data_store.copy()
    df['__dt'] = df['Start Time'].apply(_parse_dt_safe)
    max_dt = df['__dt'].max()
    if not isinstance(max_dt, datetime):
        max_dt = datetime.now()
    window_start = max_dt - timedelta(days=max(1, days))
    dfw = df[df['__dt'] >= window_start]

    import re as _re
    def _normalize_phone_input(p: str) -> str:
        digits = _re.sub(r"\D", "", str(p or ""))
        if not digits:
            return ""
        if len(digits) == 10:
            return "+91" + digits
        if len(digits) == 12 and digits.startswith("91"):
            return "+" + digits
        if len(digits) == 11 and digits.startswith("0"):
            return "+91" + digits[1:]
        return "+" + digits

    suspect = _normalize_phone_input(phone)
    if not suspect:
        return HTMLResponse("<html><body>Invalid phone</body></html>", media_type='text/html')

    # Find suspect last known coords (from rows where Phone==suspect or B-Phone==suspect)
    def last_row_for_phone(ph: str) -> Optional[pd.Series]:
        d1 = dfw[dfw['Phone'].astype(str) == ph]
        if not d1.empty:
            return d1.loc[d1['__dt'].idxmax()]
        if 'B-Phone' in dfw.columns:
            d2 = dfw[dfw['B-Phone'].astype(str) == ph]
            if not d2.empty:
                return d2.loc[d2['__dt'].idxmax()]
        return None

    srow = last_row_for_phone(suspect)
    if srow is None:
        return HTMLResponse("<html><body>No records for suspect within window</body></html>", media_type='text/html')

    # Build neighbor phone set from communications with suspect
    from collections import Counter
    phone_neigh = Counter()
    # Suspect as caller (A)
    df_a = dfw[dfw['Phone'].astype(str) == suspect]
    if 'B-Phone' in dfw.columns and not df_a.empty:
        for bp in df_a['B-Phone'].astype(str).tolist():
            if bp and bp != '+910000000000':
                phone_neigh[bp] += 1
    # Suspect as callee (B)
    if 'B-Phone' in dfw.columns:
        df_b = dfw[dfw['B-Phone'].astype(str) == suspect]
        if not df_b.empty:
            for ap in df_b['Phone'].astype(str).tolist():
                if ap and ap != '+910000000000':
                    phone_neigh[ap] += 1

    top = phone_neigh.most_common(max(1, limit))

    # Gather points
    points = []
    s_lat = float(srow.get('Latitude', 0.0) or 0.0)
    s_lon = float(srow.get('Longitude', 0.0) or 0.0)
    points.append({
        'lat': s_lat,
        'lon': s_lon,
        'label': f"Source: {suspect}",
        'color': '#1E88E5',  # Blue for source
        'size': 14,
        'details_html': _make_details_html_from_row(srow)
    })

    # Lines arrays
    sl_lats: List[float] = []
    sl_lons: List[float] = []
    pp_lats: List[float] = []
    pp_lons: List[float] = []

    # Add neighbor phones
    neighbors = []
    for ph, cnt in top:
        nrow = last_row_for_phone(ph)
        if not nrow is None:
            lat = float(nrow.get('Latitude', 0.0) or 0.0)
            lon = float(nrow.get('Longitude', 0.0) or 0.0)
            if lat == 0.0 and lon == 0.0:
                continue
            points.append({
                'lat': lat,
                'lon': lon,
                'label': f"{ph} (x{cnt})",
                'color': '#E53935',  # Red for other phones
                'size': 12,
                'details_html': _make_details_html_from_row(nrow)
            })
            neighbors.append((ph, lat, lon))
            sl_lats += [s_lat, lat, None]
            sl_lons += [s_lon, lon, None]

    # Add lines between neighbor phones if they directly communicated
    neigh_set = {ph for ph, _, _ in neighbors}
    if 'B-Phone' in dfw.columns:
        # Create a set of observed (A,B) pairs within window
        pairs = set(zip(dfw['Phone'].astype(str), dfw['B-Phone'].astype(str)))
        # For each pair among neighbors, connect if pair exists in either direction
        max_pairs = 300
        cnt_pairs = 0
        for i in range(len(neighbors)):
            for j in range(i+1, len(neighbors)):
                if cnt_pairs >= max_pairs:
                    break
                ph1, lat1, lon1 = neighbors[i]
                ph2, lat2, lon2 = neighbors[j]
                if (ph1, ph2) in pairs or (ph2, ph1) in pairs:
                    pp_lats += [lat1, lat2, None]
                    pp_lons += [lon1, lon2, None]
                    cnt_pairs += 1

    # Render map with markers and dashed lines
    import json
    markers_html = _build_plotly_map_html(points, title=f"Phone Network Map — {suspect}")
    inject = f"""
<script>
(function(){{
  const mapDiv = document.getElementById('map');
  Plotly.addTraces(mapDiv, [{{
    type:'scattermapbox', mode:'lines', lat:{json.dumps(sl_lats)}, lon:{json.dumps(sl_lons)},
    line:{{color:'#BDBDBD', width:2, dash:'dash'}}, hoverinfo:'skip'
  }},{{
    type:'scattermapbox', mode:'lines', lat:{json.dumps(pp_lats)}, lon:{json.dumps(pp_lons)},
    line:{{color:'#EF9A9A', width:1, dash:'dash'}}, hoverinfo:'skip'
  }}]);
}})();
</script>
"""
    html = markers_html.replace('</body>\n</html>', inject + '</body>\n</html>')
    return HTMLResponse(html, media_type='text/html')

@app.get("/relationships/suspicious")
def get_suspicious_patterns():
    """
    Returns identified suspicious communication patterns.
    """
    global relationship_extractor
    if not relationship_extractor:
        return {"error": "No data uploaded or relationship extractor not initialized"}
    
    try:
        patterns = relationship_extractor.identify_suspicious_patterns()
        return {"suspicious_patterns": patterns}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error identifying patterns: {str(e)}")

@app.get("/relationships/export/{format}")
def export_relationships(format: str):
    """
    Export relationships in specified format (json or summary).
    """
    global relationship_extractor
    if not relationship_extractor:
        return {"error": "No data uploaded or relationship extractor not initialized"}
    
    try:
        if format not in ['json', 'summary']:
            raise HTTPException(status_code=400, detail="Format must be 'json' or 'summary'")
        
        export_data = relationship_extractor.export_relationships(format)
        return {"export_data": export_data, "format": format}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting relationships: {str(e)}")

@app.get("/filters/investigation-focus")
def apply_investigation_focus_filters(config: Optional[str] = None):
    """
    Apply comprehensive investigation-focused filtering pipeline.
    Optional config parameter as JSON string for custom filter configuration.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        filter_config = None
        if config:
            import json
            filter_config = json.loads(config)
        
        filtered_data = communication_filters.apply_investigation_focus_filters(filter_config)
        filter_stats = communication_filters.get_filter_statistics()
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "filter_statistics": filter_stats,
            "total_records": len(filtered_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying filters: {str(e)}")

@app.get("/filters/priority")
def apply_priority_filters():
    """
    Apply high-priority investigation filters:
    - Suspicious ports and protocols
    - Long duration communications  
    - Public IP destinations
    - Unusual time patterns
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        communication_filters.reset_filters()
        filtered_data = communication_filters.apply_investigation_priority_filters()
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Applied investigation priority filters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying priority filters: {str(e)}")

@app.get("/filters/exclude-routine")
def exclude_routine_traffic():
    """
    Exclude routine/benign traffic not relevant for investigations:
    - DNS queries to common resolvers
    - Short HTTP/HTTPS sessions
    - Internal network communications
    - Broadcast/multicast traffic
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        filtered_data = communication_filters.exclude_routine_traffic()
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Excluded routine traffic"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error excluding routine traffic: {str(e)}")

@app.get("/filters/risk-based")
def apply_risk_based_filters(risk_threshold: float = 0.5):
    """
    Filter communications based on calculated risk scores.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        filtered_data = communication_filters.filter_by_risk_indicators(risk_threshold)
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "risk_threshold": risk_threshold,
            "message": f"Applied risk-based filters with threshold {risk_threshold}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying risk-based filters: {str(e)}")

@app.get("/filters/geographic")
def apply_geographic_filters(
    lat_min: Optional[float] = None,
    lat_max: Optional[float] = None, 
    lon_min: Optional[float] = None,
    lon_max: Optional[float] = None,
    cities: Optional[str] = None
):
    """
    Filter by geographic regions of investigation interest.
    Cities parameter should be comma-separated list.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        lat_range = (lat_min, lat_max) if lat_min is not None and lat_max is not None else None
        lon_range = (lon_min, lon_max) if lon_min is not None and lon_max is not None else None
        city_list = cities.split(',') if cities else None
        
        filtered_data = communication_filters.filter_by_geographic_region(
            lat_range=lat_range,
            lon_range=lon_range,
            cities=city_list
        )
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Applied geographic filters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying geographic filters: {str(e)}")

@app.get("/filters/time-window")
def apply_time_window_filters(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    time_of_day_start: Optional[str] = None,
    time_of_day_end: Optional[str] = None
):
    """
    Filter by specific time windows of investigation interest.
    Format: start_time/end_time as 'YYYY-MM-DD-HH:MM:SS'
    time_of_day_start/end as 'HH:MM' (e.g., '22:00', '05:00')
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        filtered_data = communication_filters.filter_by_time_window(
            start_time=start_time,
            end_time=end_time,
            time_of_day_start=time_of_day_start,
            time_of_day_end=time_of_day_end
        )
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Applied time window filters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying time window filters: {str(e)}")

@app.get("/filters/communication-patterns")
def apply_communication_pattern_filters():
    """
    Filter based on suspicious communication patterns:
    - Port scanning behavior
    - Bulk data transfers
    - Repeated connections to same destinations
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        filtered_data = communication_filters.filter_by_communication_patterns()
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Applied communication pattern filters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying communication pattern filters: {str(e)}")

@app.get("/filters/customer-profile")
def apply_customer_profile_filters(
    high_value_customers: Optional[str] = None,
    exclude_customers: Optional[str] = None
):
    """
    Filter based on customer profiles of investigation interest.
    Parameters should be comma-separated lists of subscriber IDs, names, or phone numbers.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        high_value_list = high_value_customers.split(',') if high_value_customers else None
        exclude_list = exclude_customers.split(',') if exclude_customers else None
        
        filtered_data = communication_filters.filter_by_customer_profile(
            high_value_customers=high_value_list,
            exclude_customers=exclude_list
        )
        
        return {
            "filtered_data": filtered_data.to_dict(orient="records"),
            "total_records": len(filtered_data),
            "message": "Applied customer profile filters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying customer profile filters: {str(e)}")

@app.get("/filters/statistics")
def get_filter_statistics():
    """
    Get detailed statistics about the current filtering process.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        stats = communication_filters.get_filter_statistics()
        return {"filter_statistics": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting filter statistics: {str(e)}")

@app.get("/filters/report")
def get_filter_report():
    """
    Export comprehensive filter report for investigation.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        report = communication_filters.export_filter_report()
        return {"filter_report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating filter report: {str(e)}")

@app.get("/filters/reset")
def reset_filters():
    """
    Reset filters to original unfiltered data.
    """
    global communication_filters
    if not communication_filters:
        return {"error": "No data uploaded or communication filters not initialized"}
    
    try:
        communication_filters.reset_filters()
        original_data = communication_filters.get_filtered_data()
        
        return {
            "message": "Filters reset to original data",
            "total_records": len(original_data),
            "data": original_data.to_dict(orient="records")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting filters: {str(e)}")

@app.get("/normalization/formats")
def get_supported_formats():
    """
    Get list of supported file formats for normalization.
    """
    global data_normalizer
    return {
        "supported_formats": data_normalizer.get_supported_formats(),
        "description": "File formats that can be normalized to standard IPDR structure"
    }

@app.get("/normalization/schema")
def get_standard_schema():
    """
    Get the standard schema that all data is normalized to.
    """
    global data_normalizer
    return {
        "standard_schema": data_normalizer.get_standard_schema(),
        "description": "Standard IPDR schema based on synthetic.csv structure"
    }

@app.get("/normalization/stats")
def get_normalization_statistics():
    """
    Get detailed statistics about normalization processes.
    """
    global data_normalizer
    return {
        "normalization_statistics": data_normalizer.get_normalization_stats(),
        "description": "Statistics about files processed and normalization success rates"
    }

@app.post("/normalization/analyze-sample")
async def analyze_sample_data(file: UploadFile = File(...)):
    """
    Analyze a sample file to suggest custom field mappings.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    file_path = os.path.join(UPLOAD_DIR, f"sample_{file.filename}")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        global data_normalizer
        
        # Try to detect format and read a sample
        file_format = data_normalizer._detect_file_format(file_path)
        encoding = data_normalizer._detect_encoding(file_path)
        
        # Parse just a sample of the data
        sample_data = data_normalizer._parse_file(file_path, file_format, encoding)
        
        if len(sample_data) > 100:
            sample_data = sample_data.head(100)  # Limit sample size
        
        # Generate custom mapping suggestions
        suggested_mapping = data_normalizer.create_custom_mapping(sample_data)
        
        # Auto-detect provider
        provider = data_normalizer._auto_detect_provider(sample_data, file_path)
        
        return {
            "file_format": file_format,
            "encoding": encoding,
            "provider_detected": provider,
            "sample_columns": list(sample_data.columns),
            "sample_records": len(sample_data),
            "suggested_mapping": suggested_mapping,
            "sample_data": sample_data.head(5).to_dict(orient="records")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing sample data: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/normalization/upload-with-mapping")
async def upload_with_custom_mapping(
    file: UploadFile = File(...),
    provider: str = "custom",
    custom_mapping: str = "{}",
    persist: bool = False,
    chunksize: Optional[int] = None
):
    """
    Upload and normalize file with custom field mapping.
    custom_mapping should be JSON string mapping standard fields to source fields.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    file_path = os.path.join(UPLOAD_DIR, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse custom mapping
        try:
            import json
            mapping_dict = json.loads(custom_mapping)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format for custom_mapping")

        global processed_data_store, relationship_extractor, communication_filters, data_normalizer
        
        # Use custom mapping for normalization
        processed_data_store = data_normalizer.normalize_file(file_path, provider, mapping_dict, chunksize=chunksize)
        normalization_stats = data_normalizer.get_normalization_stats()
        
        # Initialize relationship extractor and filters with the processed data
        if not processed_data_store.empty:
            relationship_extractor = RelationshipExtractor(processed_data_store, allowlist_ips=ALLOWLIST_IPS, denylist_ips=DENYLIST_IPS)
            communication_filters = CommunicationFilters(processed_data_store)

        saved_path = _persist_processed_data(processed_data_store, f"normalized_{os.path.splitext(file.filename)[0]}") if persist else None
        return {
            "message": f"File '{file.filename}' uploaded and normalized with custom mapping.",
            "records_found": len(processed_data_store),
            "provider": provider,
            "custom_mapping_applied": mapping_dict,
            "normalization_stats": normalization_stats,
            "persisted": bool(saved_path),
            "output_path": saved_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file with custom mapping: {str(e)}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

@app.post("/normalization/batch-upload")
async def batch_upload_files(
    files: List[UploadFile] = File(...),
    provider: str = "auto",
    persist: bool = False,
    chunksize: Optional[int] = None
):
    """
    Upload and normalize multiple files, combining them into a single dataset.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    file_paths = []
    try:
        # Save all files
        for file in files:
            if not file.filename:
                continue
            file_path = os.path.join(UPLOAD_DIR, f"batch_{file.filename}")
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            file_paths.append(file_path)

        if not file_paths:
            raise HTTPException(status_code=400, detail="No valid files provided")

        global processed_data_store, relationship_extractor, communication_filters, data_normalizer
        
        # Normalize and combine all files
        if chunksize:
            # If chunksize requested, process each with chunks and concat
            dfs = []
            for fp in file_paths:
                dfs.append(data_normalizer.normalize_file(fp, provider, chunksize=chunksize))
            processed_data_store = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
        else:
            processed_data_store = data_normalizer.normalize_multiple_files(file_paths, provider)
        normalization_stats = data_normalizer.get_normalization_stats()
        
        # Initialize relationship extractor and filters with the combined data
        if not processed_data_store.empty:
            relationship_extractor = RelationshipExtractor(processed_data_store, allowlist_ips=ALLOWLIST_IPS, denylist_ips=DENYLIST_IPS)
            communication_filters = CommunicationFilters(processed_data_store)

        saved_path = _persist_processed_data(processed_data_store, "batch_processed") if persist else None
        return {
            "message": f"Successfully processed {len(file_paths)} files.",
            "files_processed": [os.path.basename(fp) for fp in file_paths],
            "total_records": len(processed_data_store),
            "provider_used": provider,
            "normalization_stats": normalization_stats,
            "persisted": bool(saved_path),
            "output_path": saved_path
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing batch files: {str(e)}")
    finally:
        # Clean up temporary files
        for file_path in file_paths:
            if os.path.exists(file_path):
                os.remove(file_path)

@app.get("/normalization/provider-mappings")
def get_provider_mappings():
    """
    Get available provider-specific field mappings.
    """
    global data_normalizer
    return {
        "provider_mappings": data_normalizer.provider_mappings,
        "field_aliases": data_normalizer.field_aliases,
        "description": "Available provider mappings and field aliases for normalization"
    }

@app.get("/mapping/phone-connections")
def get_phone_connection_table():
    """
    Get table showing phone number connections and communication patterns.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        phone_table = communication_mapper.create_phone_connection_table()
        return {
            "phone_connections": phone_table.to_dict(orient="records"),
            "total_phones": len(phone_table),
            "description": "Phone number communication patterns and connections"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating phone connection table: {str(e)}")

@app.get("/mapping/ip-connections")
def get_ip_connection_table():
    """
    Get table showing IP address connections and communication patterns.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        ip_table = communication_mapper.create_ip_connection_table()
        return {
            "ip_connections": ip_table.to_dict(orient="records"),
            "total_connections": len(ip_table),
            "description": "IP address communication patterns and statistics"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating IP connection table: {str(e)}")

@app.get("/mapping/customer-connections")
def get_customer_connection_table():
    """
    Get table showing customer connections and relationships.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        customer_table = communication_mapper.create_customer_connection_table()
        return {
            "customer_connections": customer_table.to_dict(orient="records"),
            "total_customers": len(customer_table),
            "description": "Customer communication patterns and relationships"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating customer connection table: {str(e)}")

@app.get("/mapping/communication-matrix/{matrix_type}")
def get_communication_matrix(matrix_type: str):
    """
    Get adjacency matrix for communication relationships.
    matrix_type: 'phone', 'ip', or 'customer'
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    if matrix_type not in ['phone', 'ip', 'customer']:
        raise HTTPException(status_code=400, detail="matrix_type must be 'phone', 'ip', or 'customer'")
    
    try:
        matrix = communication_mapper.create_communication_matrix(matrix_type)
        return {
            "matrix": matrix.to_dict(),
            "matrix_type": matrix_type,
            "dimensions": matrix.shape,
            "description": f"Adjacency matrix for {matrix_type} communications"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating communication matrix: {str(e)}")

@app.get("/mapping/visualization/{network_type}")
def generate_network_visualization(
    network_type: str,
    layout: str = "spring",
    format: str = "base64"
):
    """
    Generate network visualization.
    network_type: 'phone', 'ip', 'customer', or 'combined'
    layout: 'spring', 'circular', or 'kamada_kawai'
    format: 'base64' or 'file'
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    if network_type not in ['phone', 'ip', 'customer', 'combined']:
        raise HTTPException(status_code=400, detail="network_type must be 'phone', 'ip', 'customer', or 'combined'")
    
    try:
        if format == "base64":
            image_data = communication_mapper.generate_network_visualization(
                network_type=network_type, layout=layout
            )
        else:
            save_path = f"{UPLOAD_DIR}/network_{network_type}_{layout}.png"
            image_data = communication_mapper.generate_network_visualization(
                network_type=network_type, layout=layout, save_path=save_path
            )
        
        return {
            "visualization": image_data,
            "network_type": network_type,
            "layout": layout,
            "format": format,
            "description": f"Network visualization for {network_type} communications"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating network visualization: {str(e)}")

@app.get("/mapping/interactive-visualization/{network_type}")
def generate_interactive_visualization(network_type: str):
    """
    Generate interactive network visualization using Plotly.
    network_type: 'phone', 'ip', 'customer', or 'combined'
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    if network_type not in ['phone', 'ip', 'customer', 'combined']:
        raise HTTPException(status_code=400, detail="network_type must be 'phone', 'ip', 'customer', or 'combined'")
    
    try:
        html_content = communication_mapper.generate_interactive_visualization(network_type)
        return {
            "html_content": html_content,
            "network_type": network_type,
            "description": f"Interactive network visualization for {network_type} communications"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating interactive visualization: {str(e)}")

@app.get("/mapping/geographic-visualization")
def generate_geographic_visualization():
    """
    Generate geographic visualization of communication patterns.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        html_content = communication_mapper.create_geographic_visualization()
        return {
            "html_content": html_content,
            "description": "Geographic distribution of communications on interactive map"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating geographic visualization: {str(e)}")

@app.get("/mapping/timeline-visualization")
def generate_timeline_visualization():
    """
    Generate timeline visualization of communication patterns.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        html_content = communication_mapper.generate_communication_timeline()
        return {
            "html_content": html_content,
            "description": "Timeline analysis of communication patterns by hour and date"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating timeline visualization: {str(e)}")

@app.get("/mapping/statistics")
def get_communication_statistics():
    """
    Get comprehensive statistics about communication patterns and network structure.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        stats = communication_mapper.get_communication_statistics()
        mapping_stats = communication_mapper.get_mapping_stats()
        
        return {
            "communication_statistics": stats,
            "mapping_statistics": mapping_stats,
            "description": "Comprehensive analysis of communication networks and patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating communication statistics: {str(e)}")

@app.get("/mapping/export-all-tables")
def export_all_mapping_tables():
    """
    Export all communication mapping tables and matrices.
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    try:
        all_tables = communication_mapper.export_all_tables()
        
        # Convert all DataFrames to dict format for JSON response
        export_data = {}
        for table_name, table_df in all_tables.items():
            export_data[table_name] = table_df.to_dict(orient="records")
            export_data[f"{table_name}_info"] = {
                "rows": len(table_df),
                "columns": list(table_df.columns)
            }
        
        return {
            "exported_tables": export_data,
            "table_types": list(all_tables.keys()),
            "description": "All communication mapping tables and matrices exported"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting mapping tables: {str(e)}")

@app.get("/mapping/network-analysis/{network_type}")
def analyze_network_properties(network_type: str):
    """
    Perform detailed network analysis including centrality measures, clustering, etc.
    network_type: 'phone', 'ip', 'customer', or 'combined'
    """
    global communication_mapper
    if not communication_mapper:
        return {"error": "No data uploaded or communication mapper not initialized"}
    
    if network_type not in ['phone', 'ip', 'customer', 'combined']:
        raise HTTPException(status_code=400, detail="network_type must be 'phone', 'ip', 'customer', or 'combined'")
    
    try:
        import networkx as nx
        
        # Get the appropriate network
        if network_type == 'phone':
            G = communication_mapper.phone_network
        elif network_type == 'ip':
            G = communication_mapper.ip_network
        elif network_type == 'customer':
            G = communication_mapper.customer_network
        else:  # combined
            G = communication_mapper.combined_network
        
        analysis = {
            "basic_metrics": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "density": nx.density(G),
                "is_connected": nx.is_connected(G) if not G.is_directed() else nx.is_strongly_connected(G)
            }
        }
        
        # Add centrality measures for smaller networks
        if G.number_of_nodes() <= 1000:  # Limit for performance
            try:
                # Degree centrality
                degree_centrality = nx.degree_centrality(G)
                top_degree = sorted(degree_centrality.items(), key=lambda x: x[1], reverse=True)[:10]
                analysis["centrality_measures"] = {
                    "top_degree_centrality": top_degree
                }
                
                # Clustering coefficient (for undirected graphs)
                if not G.is_directed():
                    analysis["clustering"] = {
                        "average_clustering": nx.average_clustering(G),
                        "transitivity": nx.transitivity(G)
                    }
                
            except Exception as e:
                analysis["centrality_error"] = str(e)
        
        # Connected components analysis
        if not G.is_directed():
            components = list(nx.connected_components(G))
            analysis["components"] = {
                "number_of_components": len(components),
                "largest_component_size": len(max(components, key=len)) if components else 0,
                "component_sizes": [len(c) for c in components[:10]]  # Top 10 component sizes
            }
        
        return {
            "network_analysis": analysis,
            "network_type": network_type,
            "description": f"Detailed network analysis for {network_type} communication network"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing network analysis: {str(e)}")

@app.get("/suspicious/comprehensive-analysis")
def run_comprehensive_suspicious_analysis():
    """
    Run comprehensive suspicious activity analysis across all detection algorithms.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.run_comprehensive_analysis()
        summary_report = suspicious_activity_detector.generate_summary_report(alerts)
        
        return {
            "suspicious_activities": alerts,
            "summary_report": summary_report,
            "description": "Comprehensive analysis of suspicious communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running suspicious activity analysis: {str(e)}")

@app.get("/suspicious/late-night-activity")
def detect_late_night_activity():
    """
    Detect unusual late-night communication patterns (22:00-05:00).
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_late_night_activity()
        return {
            "late_night_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of unusual late-night communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting late-night activity: {str(e)}")

@app.get("/suspicious/short-duration-patterns")
def detect_short_duration_patterns():
    """
    Detect patterns of unusually short duration calls.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_short_duration_patterns()
        return {
            "short_duration_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of unusual short-duration communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting short duration patterns: {str(e)}")

@app.get("/suspicious/high-frequency-activity")
def detect_high_frequency_activity():
    """
    Detect unusually high frequency communication patterns.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_high_frequency_activity()
        return {
            "high_frequency_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of unusual high-frequency communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting high frequency activity: {str(e)}")

@app.get("/suspicious/port-scanning-behavior")
def detect_port_scanning_behavior():
    """
    Detect potential port scanning activities.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_port_scanning_behavior()
        return {
            "port_scanning_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of potential port scanning behavior"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting port scanning behavior: {str(e)}")

@app.get("/suspicious/protocol-anomalies")
def detect_protocol_anomalies():
    """
    Detect unusual protocol usage patterns.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_protocol_anomalies()
        return {
            "protocol_anomaly_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of unusual protocol usage patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting protocol anomalies: {str(e)}")

@app.get("/suspicious/geographic-anomalies")
def detect_geographic_anomalies():
    """
    Detect geographically suspicious activities.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_geographic_anomalies()
        return {
            "geographic_anomaly_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of geographic anomalies in communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting geographic anomalies: {str(e)}")

@app.get("/suspicious/burst-activity-patterns")
def detect_burst_activity_patterns():
    """
    Detect burst communication patterns.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_burst_activity_patterns()
        return {
            "burst_activity_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of burst communication patterns"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting burst activity patterns: {str(e)}")

@app.get("/suspicious/off-hours-business-activity")
def detect_off_hours_business_activity():
    """
    Detect unusual off-hours business activity patterns.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_off_hours_business_activity()
        return {
            "off_hours_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of unusual off-hours business activity"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting off-hours business activity: {str(e)}")

@app.get("/suspicious/statistical-anomalies")
def detect_statistical_anomalies():
    """
    Detect statistical anomalies using machine learning techniques.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        alerts = suspicious_activity_detector.detect_statistical_anomalies()
        return {
            "statistical_anomaly_alerts": alerts,
            "alert_count": len(alerts),
            "description": "Detection of statistical anomalies using machine learning"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error detecting statistical anomalies: {str(e)}")

@app.get("/suspicious/detection-statistics")
def get_detection_statistics():
    """
    Get statistics about the suspicious activity detection process.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        stats = suspicious_activity_detector.get_detection_statistics()
        return {
            "detection_statistics": stats,
            "description": "Statistics about the suspicious activity detection process"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting detection statistics: {str(e)}")

@app.post("/suspicious/export-alerts")
async def export_suspicious_alerts(format: str = "csv", session: Dict = Depends(require_role(["administrator"]))):
    """
    Export all suspicious activity alerts to specified format.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        # Run comprehensive analysis first
        alerts = suspicious_activity_detector.run_comprehensive_analysis()
        
        if format.lower() == "csv":
            # Export to CSV
            filename = f"{UPLOAD_DIR}/suspicious_activities.csv"
            csv_file = suspicious_activity_detector.export_alerts_to_csv(alerts, filename)
            try:
                os.chmod(csv_file, 0o600)
            except Exception:
                pass
            log_action(session.get("username"), "export_alerts", f"format={format}")
            
            return {
                "export_file": csv_file,
                "format": format,
                "total_alerts": sum(len(alert_list) for alert_list in alerts.values()),
                "description": f"Suspicious activity alerts exported to {format.upper()} format"
            }
        
        elif format.lower() == "json":
            return {
                "alerts": alerts,
                "format": format,
                "total_alerts": sum(len(alert_list) for alert_list in alerts.values()),
                "description": f"Suspicious activity alerts exported in {format.upper()} format"
            }
        
        else:
            raise HTTPException(status_code=400, detail="Format must be 'csv' or 'json'")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting suspicious alerts: {str(e)}")

@app.get("/suspicious/update-thresholds")
def update_alert_thresholds(
    late_night_min_count: Optional[int] = None,
    short_duration_max: Optional[int] = None,
    high_frequency_min_count: Optional[int] = None,
    port_scanning_threshold: Optional[int] = None,
    session: Dict = Depends(require_role(["administrator"]))
):
    """
    Update alert thresholds for suspicious activity detection.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        updated_thresholds = {}
        
        if late_night_min_count is not None:
            suspicious_activity_detector.alert_thresholds['late_night_calls']['min_count'] = late_night_min_count
            updated_thresholds['late_night_min_count'] = late_night_min_count
        
        if short_duration_max is not None:
            suspicious_activity_detector.alert_thresholds['short_duration_calls']['max_duration'] = short_duration_max
            updated_thresholds['short_duration_max'] = short_duration_max
        
        if high_frequency_min_count is not None:
            suspicious_activity_detector.alert_thresholds['high_frequency_calls']['min_count'] = high_frequency_min_count
            updated_thresholds['high_frequency_min_count'] = high_frequency_min_count
        
        if port_scanning_threshold is not None:
            suspicious_activity_detector.alert_thresholds['port_scanning']['unique_ports_threshold'] = port_scanning_threshold
            updated_thresholds['port_scanning_threshold'] = port_scanning_threshold
        
        log_action(session.get("username"), "update_thresholds", str(updated_thresholds))
        return {
            "message": "Alert thresholds updated successfully",
            "updated_thresholds": updated_thresholds,
            "current_thresholds": suspicious_activity_detector.alert_thresholds
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating alert thresholds: {str(e)}")

@app.get("/suspicious/behavioral-baselines")
def get_behavioral_baselines():
    """
    Get established behavioral baselines for anomaly detection.
    """
    global suspicious_activity_detector
    if not suspicious_activity_detector:
        return {"error": "No data uploaded or suspicious activity detector not initialized"}
    
    try:
        return {
            "behavioral_baselines": suspicious_activity_detector.behavioral_baselines,
            "description": "Established behavioral baselines for anomaly detection"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting behavioral baselines: {str(e)}")

# =============================================================================
# SEARCH AND QUERY SYSTEM ENDPOINTS - TASK 8
# =============================================================================

@app.get("/search/phone/{phone_number}")
def search_by_phone_number(phone_number: str, include_alt_phone: bool = True, exact_match: bool = False):
    """
    Search for records by phone number.
    Allows investigators to find all communications involving a specific phone number.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        result = search_query_system.search_by_phone_number(
            phone_number=phone_number,
            include_alt_phone=include_alt_phone,
            exact_match=exact_match
        )
        
        return {
            "phone_number": phone_number,
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by phone number: {str(e)}")

@app.get("/search/ip/{ip_address}")
def search_by_ip_address(ip_address: str, 
                        search_source: bool = True, 
                        search_destination: bool = True, 
                        search_nat: bool = True, 
                        exact_match: bool = True):
    """
    Search for records by IP address.
    Allows investigators to find all communications involving a specific IP address.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        result = search_query_system.search_by_ip_address(
            ip_address=ip_address,
            search_source=search_source,
            search_destination=search_destination,
            search_nat=search_nat,
            exact_match=exact_match
        )
        
        return {
            "ip_address": ip_address,
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by IP address: {str(e)}")

@app.get("/search/date-range")
def search_by_date_range(start_date: str, end_date: str, date_field: str = "Start_DateTime"):
    """
    Search for records within a specific date range.
    Allows investigators to analyze communications during specific time periods.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        result = search_query_system.search_by_date_range(
            start_date=start_date,
            end_date=end_date,
            date_field=date_field
        )
        
        return {
            "date_range": f"{start_date} to {end_date}",
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by date range: {str(e)}")

@app.get("/search/communication-type")
def search_by_communication_type(protocol: Optional[str] = None,
                                min_port: Optional[int] = None,
                                max_port: Optional[int] = None,
                                min_duration: Optional[int] = None,
                                max_duration: Optional[int] = None):
    """
    Search for records by communication type (protocol, ports, duration).
    Allows investigators to filter by specific communication characteristics.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        port_range = None
        if min_port is not None and max_port is not None:
            port_range = (min_port, max_port)
        
        duration_range = None
        if min_duration is not None and max_duration is not None:
            duration_range = (min_duration, max_duration)
        
        result = search_query_system.search_by_communication_type(
            protocol=protocol,
            port_range=port_range,
            duration_range=duration_range
        )
        
        return {
            "filters": {
                "protocol": protocol,
                "port_range": f"{min_port}-{max_port}" if port_range else None,
                "duration_range": f"{min_duration}-{max_duration}" if duration_range else None
            },
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by communication type: {str(e)}")

@app.get("/search/customer")
def search_by_customer(customer_name: Optional[str] = None,
                      customer_id: Optional[str] = None,
                      subscriber_id: Optional[str] = None,
                      exact_match: bool = False):
    """
    Search for records by customer information.
    Allows investigators to find all communications for a specific customer or subscriber.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        result = search_query_system.search_by_customer(
            customer_name=customer_name,
            customer_id=customer_id,
            subscriber_id=subscriber_id,
            exact_match=exact_match
        )
        
        return {
            "search_criteria": {
                "customer_name": customer_name,
                "customer_id": customer_id,
                "subscriber_id": subscriber_id
            },
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching by customer: {str(e)}")

@app.post("/search/advanced")
def advanced_search(search_request: dict):
    """
    Perform advanced search with multiple criteria.
    Allows investigators to combine multiple search conditions with AND/OR logic.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        # Parse search criteria from request
        criteria_list = []
        for criteria_dict in search_request.get('criteria', []):
            criteria = SearchCriteria(
                field=criteria_dict['field'],
                operator=SearchOperator(criteria_dict['operator']),
                value=criteria_dict['value'],
                case_sensitive=criteria_dict.get('case_sensitive', False)
            )
            criteria_list.append(criteria)
        
        result = search_query_system.advanced_search(
            criteria_list=criteria_list,
            combine_with_and=search_request.get('combine_with_and', True),
            sort_by=search_request.get('sort_by'),
            sort_order=SortOrder(search_request.get('sort_order', 'asc')),
            limit=search_request.get('limit', 1000)
        )
        
        return {
            "search_criteria": [
                {
                    "field": c.field,
                    "operator": c.operator.value,
                    "value": c.value
                } for c in criteria_list
            ],
            "total_records": result.total_count,
            "matching_records": result.filtered_count,
            "search_time_ms": result.search_time_ms,
            "records": result.records.to_dict('records')[:100],  # Limit to 100 for API response
            "has_more": result.filtered_count > 100
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error performing advanced search: {str(e)}")

@app.get("/search/suggestions")
def get_search_suggestions(query: str, field: str):
    """
    Get search suggestions for auto-completion.
    Helps investigators find relevant search terms.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        suggestions = search_query_system.get_search_suggestions(query, field)
        
        return {
            "query": query,
            "field": field,
            "suggestions": suggestions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting search suggestions: {str(e)}")

@app.get("/search/statistics")
def get_search_statistics():
    """
    Get statistics about searchable data.
    Provides investigators with overview of available data for searching.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        stats = search_query_system.get_search_statistics()
        
        return {
            "search_statistics": stats,
            "description": "Statistics about searchable IPDR data"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting search statistics: {str(e)}")

@app.post("/search/export")
def export_search_results(export_request: dict, session: Dict = Depends(require_role(["administrator", "analyst"]))):
    """
    Export search results to CSV file.
    Allows investigators to save search results for further analysis.
    """
    global search_query_system
    if not search_query_system:
        return {"error": "No data uploaded or search system not initialized"}
    
    try:
        # Perform the search first based on provided criteria
        search_type = export_request.get('search_type')
        
        if search_type == 'phone':
            result = search_query_system.search_by_phone_number(
                phone_number=export_request.get('phone_number'),
                include_alt_phone=export_request.get('include_alt_phone', True),
                exact_match=export_request.get('exact_match', False)
            )
        elif search_type == 'ip':
            result = search_query_system.search_by_ip_address(
                ip_address=export_request.get('ip_address'),
                exact_match=export_request.get('exact_match', True)
            )
        elif search_type == 'date_range':
            result = search_query_system.search_by_date_range(
                start_date=export_request.get('start_date'),
                end_date=export_request.get('end_date'),
                date_field=export_request.get('date_field', 'Start_DateTime')
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid search type for export")
        
        # Export the results
        filename = export_request.get('filename', 'search_results.csv')
        exported_file = search_query_system.export_search_results(
            search_result=result,
            filename=filename,
            include_metadata=export_request.get('include_metadata', True),
            anonymize=export_request.get('anonymize', False)
        )
        try:
            os.chmod(exported_file, 0o600)
        except Exception:
            pass
        log_action(session.get("username"), "export_search", f"file={filename}")
        
        return {
            "message": "Search results exported successfully",
            "filename": exported_file,
            "records_exported": result.filtered_count,
            "export_time": f"{result.search_time_ms:.2f} ms"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error exporting search results: {str(e)}")

# =============================
# CASE MANAGEMENT ENDPOINTS
# =============================

class CreateCaseRequest(BaseModel):
    name: str
    notes: Optional[str] = None

class SaveSearchRequest(BaseModel):
    criteria_json: Dict[str, Any]
    notes: Optional[str] = None

@app.post("/cases")
def create_case(payload: CreateCaseRequest, session: Dict = Depends(verify_token)):
    if not payload.name or not payload.name.strip():
        raise HTTPException(status_code=400, detail="Case name is required")
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO cases (name, created_by, created_at) VALUES (?, ?, ?)",
        (payload.name.strip(), session.get("username"), datetime.now().isoformat()),
    )
    case_id = cur.lastrowid
    conn.commit()
    conn.close()
    log_action(session.get("username"), "create_case", f"case_id={case_id}")
    return {"id": case_id, "name": payload.name.strip()}

@app.get("/cases")
def list_cases(session: Dict = Depends(verify_token)):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, created_by, created_at FROM cases ORDER BY id DESC")
    rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    conn.close()
    return {"cases": rows}

@app.post("/cases/{case_id}/save-search")
def save_search_to_case(case_id: int, payload: SaveSearchRequest, session: Dict = Depends(verify_token)):
    conn = get_db_conn()
    cur = conn.cursor()
    # Ensure case exists
    cur.execute("SELECT 1 FROM cases WHERE id = ?", (case_id,))
    if cur.fetchone() is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    import json
    cur.execute(
        "INSERT INTO saved_searches (case_id, criteria_json, notes, created_at) VALUES (?, ?, ?, ?)",
        (case_id, json.dumps(payload.criteria_json), payload.notes or "", datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()
    log_action(session.get("username"), "save_search", f"case_id={case_id}")
    return {"success": True}

@app.get("/cases/{case_id}/searches")
def list_saved_searches(case_id: int, session: Dict = Depends(verify_token)):
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, criteria_json, notes, created_at FROM saved_searches WHERE case_id = ? ORDER BY id DESC", (case_id,))
    rows = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    conn.close()
    return {"saved_searches": rows}

@app.post("/cases/{case_id}/export-pack")
def export_case_pack(case_id: int, session: Dict = Depends(verify_token)):
    # Export a simple pack with saved searches + summaries
    conn = get_db_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, name, created_by, created_at FROM cases WHERE id = ?", (case_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Case not found")
    case = dict(zip([c[0] for c in cur.description], row))
    cur.execute("SELECT id, criteria_json, notes, created_at FROM saved_searches WHERE case_id = ?", (case_id,))
    searches = [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]
    conn.close()

    # Summaries
    bparty = None
    try:
        bparty = {
            "ips": relationship_extractor.get_b_party_summary() if relationship_extractor else {},
            "phones": relationship_extractor.get_b_party_phone_summary() if relationship_extractor else {},
        }
    except Exception:
        bparty = {"ips": {}, "phones": {}}

    # Write pack
    import json, zipfile
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    zip_path = os.path.join(UPLOAD_DIR, f"case_{case_id}_pack.zip")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('case.json', json.dumps(case, indent=2))
        zf.writestr('saved_searches.json', json.dumps(searches, indent=2))
        zf.writestr('bparty_summary.json', json.dumps(bparty, indent=2))
    try:
        os.chmod(zip_path, 0o600)
    except Exception:
        pass
    log_action(session.get("username"), "export_case_pack", f"case_id={case_id}")
    return {"export_file": zip_path}

if __name__ == "__main__":
    import uvicorn
    host = os.getenv("HOST", "0.0.0.0")
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000
    print(f"Starting API on {host}:{port} (set HOST/PORT env to override)")
    uvicorn.run(app, host=host, port=port)
