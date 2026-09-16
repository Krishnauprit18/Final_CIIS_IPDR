# Phase 3 - S3-Compatible Object Storage

## Goal

Move durable file artifacts out of the backend filesystem and behind an S3-compatible storage boundary. Local development uses MinIO; production can use AWS S3 by changing environment configuration.

## Architecture

```text
FastAPI handlers
      |
      v
Storage service / StorageBackend
      |
      v
S3-compatible API
      |
      +-- Local: MinIO
      +-- Production: AWS S3
```

Temporary files that exist only while a parser processes an upload may still use local disk. Durable artifacts are redirected to object storage.

## Durable artifacts redirected in Phase 3

- Persisted normalized/processed datasets
- Uploaded case documents retained after case analysis
- Case export ZIP files
- Suspicious-activity CSV exports
- Search CSV exports

The public HTTP route contract is preserved. Returned durable file locations use `s3://<bucket>/<key>` URIs.

## Local services

Start PostgreSQL and MinIO from the repository root:

```bash
docker compose -f compose.db.yaml up -d
docker compose -f compose.storage.yaml up -d
```

Check status:

```bash
docker compose -f compose.db.yaml ps
docker compose -f compose.storage.yaml ps -a
```

Expected object-storage state:

- `ciis-minio`: healthy
- `ciis-minio-init`: exited with code 0
- bucket: `ciis-storage`
- bucket access: private

MinIO console: `http://localhost:9001`

## Environment

Local defaults are documented in `backend/.env.example`:

```env
STORAGE_BUCKET=ciis-storage
STORAGE_ENDPOINT_URL=http://localhost:9000
STORAGE_ACCESS_KEY=ciisadmin
STORAGE_SECRET_KEY=ciisadmin123
STORAGE_REGION=us-east-1
STORAGE_USE_SSL=false
```

Do not commit real credentials. For AWS S3, `STORAGE_ENDPOINT_URL` can be empty and credentials should come from the standard AWS credential chain or workload/IAM role.

## Acceptance

From `backend/`:

```bash
python -m pytest -q
alembic current
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Expected:

- all backend tests pass
- Alembic reports `0001_initial_postgresql (head)`
- API startup completes only when PostgreSQL and object storage are reachable

Optional direct storage smoke test:

```bash
python - <<'PY'
from app.storage.service import delete_object, download_bytes, object_exists, upload_bytes

key = "smoke/phase3.txt"
uri = upload_bytes(b"phase3-ok", key, content_type="text/plain")
print("uploaded:", uri)
print("exists:", object_exists(key))
print("downloaded:", download_bytes(key).decode())
delete_object(key)
print("exists-after-delete:", object_exists(key))
PY
```

Expected output includes `phase3-ok` and `exists-after-delete: False`.
