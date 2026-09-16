# Phase 1 - Modular Backend

## Goal

Refactor the monolithic FastAPI backend into a modular monolith without changing the external API contract.

## What changed

- `backend/main.py` is now a small compatibility entry point.
- `backend/app/main.py` is the application composition root.
- API routes are grouped by domain under `backend/app/api/routers/`.
- Existing domain engines live under `backend/app/services/`; root-level modules remain as compatibility shims for the existing tests/imports.
- Stable project, dataset, upload, config and environment paths are defined in `backend/app/core/config.py`.
- Existing handler behavior is retained in `backend/app/legacy_handlers.py` during this phase so the refactor does not mix structural changes with persistence or business-logic changes.
- Dataset and upload paths no longer depend on the current working directory.

## Router domains

- `analysis.py`: 14 routes
- `analytics.py`: 18 routes
- `auth.py`: 7 routes
- `cases.py`: 6 routes
- `health.py`: 1 routes
- `link_analysis.py`: 4 routes
- `mapping.py`: 11 routes
- `maps.py`: 3 routes
- `normalization.py`: 7 routes
- `processing.py`: 3 routes
- `search.py`: 9 routes

Total preserved application routes: **83**.

## Deliberately unchanged in Phase 1

- SQLite persistence
- in-process Pandas/analytics state
- authentication behavior
- local filesystem uploads
- frontend implementation
- no Docker, S3, SQS, Floci, PostgreSQL, or Kubernetes yet

## Next phase

Phase 2 can migrate persistence behind the now-stable application composition/API layer without combining that migration with the Phase 1 structural refactor.
