# Current CIIS Architecture

Status: Phase 0 baseline documentation
Scope: Current implementation only
Last reviewed: 2026-09-16

## 1. System overview

CIIS is currently implemented as a local two-tier web application:

- React and TypeScript frontend.
- FastAPI and Python backend.
- SQLite for users, sessions, audit logs, cases, and saved searches.
- Pandas DataFrames for the active IPDR dataset and analytics state.
- Local filesystem storage for uploaded case documents and generated case packs.

The current application is not yet a distributed system. The backend is a monolithic FastAPI process, and the active analytics state is held in process memory.

## 2. Repository layout

### Frontend

Location: `frontend/`

Important files:

- `frontend/src/App.tsx`
- `frontend/src/Login.tsx`
- `frontend/src/Register.tsx`
- `frontend/src/Dashboard.tsx`
- `frontend/package.json`

The frontend uses React, TypeScript, Material UI, Axios, MUI Data Grid, and `react-graph-vis`.

### Backend

Location: `backend/`

Important files:

- `backend/main.py`
- `backend/data_normalizer.py`
- `backend/parser.py`
- `backend/relationship_extractor.py`
- `backend/communication_mapping.py`
- `backend/communication_filters.py`
- `backend/suspicious_activity_detector.py`
- `backend/search_query_system.py`

### Dataset

Location: `Scenario A1-ARFF/synthetic.csv`

The dataset contains approximately 12,000 IPDR records and 25 canonical fields.

## 3. Frontend request flow

The frontend currently uses a hard-coded backend URL:

```text
http://localhost:8000
```

The main flow is:

```text
Browser
  |
  v
React application on localhost:3000
  |
  | Axios REST requests
  v
FastAPI backend on localhost:8000
```

Authentication state is kept in browser `localStorage` using:

- `ipdr_token`
- `ipdr_username`

After login, the token is also configured as Axios' default `Authorization` header.

## 4. Authentication request flow

```text
Login form
  |
  | POST /auth/login
  v
FastAPI authentication route
  |
  v
SQLite users table
  |
  | PBKDF2 password verification
  v
SQLite sessions table
  |
  v
Session token returned to browser
```

The backend creates a random token with an approximately 24-hour expiry. Authentication actions are written to `audit_logs`.

## 5. Registration flow

```text
Registration form
  |
  | POST /auth/register
  v
FastAPI registration route
  |
  | Validate email
  | Generate PBKDF2 password hash and salt
  v
SQLite users table
```

The CAPTCHA currently exists only in the frontend. It is not independently validated by the backend.

## 6. Main data-processing flow

The dashboard calls:

```text
POST /process-data
```

The backend then:

1. Uses the fixed path `../Scenario A1-ARFF/synthetic.csv`.
2. Sends the file to `DataNormalizer`.
3. Converts the input to the canonical 25-column schema.
4. Stores the resulting Pandas DataFrame in the global `processed_data_store` variable.
5. Initializes `RelationshipExtractor`, `CommunicationFilters`, `CommunicationMapper`, `SuspiciousActivityDetector`, and `SearchQuerySystem`.
6. Returns the processed record count to the frontend.

## 7. Normalization flow

```text
Input file
  |
  v
DataNormalizer
  |
  | Format detection
  | Encoding detection
  | Provider detection
  | Provider mapping
  | Field aliases
  | Data cleaning
  | Type conversion
  v
Canonical 25-column DataFrame
```

Supported formats currently include CSV, JSON, XML, TXT, TSV, LOG, and YAML.

Missing fields are filled with default values. Invalid IPs, ports, timestamps, phone numbers, and coordinates are cleaned or replaced.

## 8. Search flow

```text
Frontend search controls
  |
  | GET /search/...
  v
SearchQuerySystem
  |
  | In-memory Pandas filtering
  | Search-friendly columns
  | Phone normalization
  | IP conversion
  | Date fields
  v
JSON response
  |
  v
MUI DataGrid
```

Search data is not stored in a separate search engine. It exists only inside the backend process.

## 9. Relationship and network flow

```text
processed_data_store
  |
  +--> RelationshipExtractor
  |       |
  |       +--> A-Party summary
  |       +--> B-Party summary
  |       +--> Risk-related attributes
  |
  +--> CommunicationMapper
          |
          +--> Phone connections
          +--> IP connections
          +--> Customer connections
          +--> NetworkX graphs
          +--> Plotly visualizations
```

The frontend renders graph data using `react-graph-vis`.

## 10. Suspicious-activity flow

```text
processed_data_store
  |
  v
SuspiciousActivityDetector
  |
  +--> Late-night activity
  +--> Short-duration patterns
  +--> High-frequency activity
  +--> Port scanning
  +--> Protocol anomalies
  +--> Geographic anomalies
  +--> Burst activity
  +--> Off-hours activity
  +--> Statistical anomalies
  |
  v
Dashboard alerts
```

The detector uses heuristic thresholds and scikit-learn-based statistical models.

## 11. Case-management flow

```text
Authenticated frontend
  |
  +--> POST /cases
  |       |
  |       v
  |     SQLite cases table
  |
  +--> POST /cases/{case_id}/save-search
  |       |
  |       v
  |     SQLite saved_searches table
  |
  +--> POST /cases/{case_id}/ai-analyze
          |
          +--> Save DOCX to local uploads directory
          +--> Save dataset temporarily
          +--> Normalize dataset
          +--> Store DataFrame in CASE_ANALYSES
          +--> Remove temporary dataset
```

The current case-analysis implementation is local deterministic analytics. It does not currently parse DOCX contents or call an LLM.

`CASE_ANALYSES` is process memory. Case analysis state is lost when the backend restarts.

## 12. Map flow

The backend generates HTML map pages and the frontend displays them inside iframes.

Current external map dependencies include Plotly CDN, Leaflet CDN, and OpenStreetMap tiles.

Map routes include:

- `/map/suspicious-phones/html`
- `/map/suspicious-phones-network/html`
- `/map/case-network/html`
- `/link-analysis/phone-map/html`
- `/link-analysis/phone-phone-map/html`

Some case-map content is currently synthetic or hypothetical, including randomly generated police-station incharge details and fallback visual connections.

## 13. Persistence model

### SQLite persistence

SQLite currently stores users, sessions, audit logs, cases, and saved searches.

### Filesystem persistence

The filesystem currently stores uploaded case documents, exported case packs, temporary normalized files, and optional processed datasets.

### In-memory state

The backend process stores the active processed DataFrame, analysis objects, and case-analysis DataFrames in memory.

Restarting the backend clears the in-memory analytics state.

## 14. Current limitations

- Backend is monolithic.
- Analytics state is process-local.
- No queue or worker service exists.
- No object-storage abstraction exists.
- SQLite is used directly by the API process.
- No external search/index service exists.
- Authentication coverage is inconsistent across routes.
- Case ownership enforcement is incomplete.
- Upload validation and file isolation require hardening.
- Frontend API URL is hard-coded.
- No Dockerfile, Compose file, or infrastructure-as-code exists.
- No Floci runtime is currently connected to CIIS.

## 15. Phase 0 runtime baseline

The exact runtime, dependency, test, and build results are recorded separately in:

```text
docs/phase-0-baseline.md
```

This document describes the current application only. It does not describe the future distributed architecture.
