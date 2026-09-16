# Phase 2 - PostgreSQL Persistence

Phase 2 removes SQLite as the application persistence boundary and introduces PostgreSQL through SQLAlchemy 2.x and Alembic.

## Runtime contract

The application reads one database setting:

```text
DATABASE_URL=postgresql+psycopg://ciis:ciis@localhost:5432/ciis
```

Tables are never created from application startup. The schema is owned by Alembic migrations.

## Local database

From repository root:

```bash
docker compose -f compose.db.yaml up -d
```

Install backend dependencies, then run the migration from `backend/`:

```bash
pip install -r requirements.txt
alembic upgrade head
```

Start the API only after migrations are current:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Startup checks PostgreSQL connectivity and the current `alembic_version`. A missing/outdated migration fails fast instead of silently creating tables.

## Tables

- `users`
- `sessions`
- `audit_logs`
- `cases`
- `saved_searches`
- `jobs`
- `analysis_metadata`
- `alerts`

The last three tables establish the persistence model needed by later asynchronous worker and alerting phases; Phase 2 does not yet implement SQS/workers.

## Architecture

```text
FastAPI
  |
SQLAlchemy 2.x
  |
PostgreSQL
  ^
Alembic migrations
```

SQLite database files are no longer part of runtime behavior.
