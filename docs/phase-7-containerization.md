# Phase 7 — Production-style containerization

Phase 7 turns the application into three deployable runtime roles:

- `ciis-frontend`
- `ciis-api`
- `ciis-worker`

The API and worker intentionally reuse the same backend image. Their runtime command and `CIIS_ROLE` differ.

## Backend image

Build from `backend/`:

```bash
docker build -t ciis-backend:phase7 .
```

The backend Dockerfile uses:

- pinned `python:3.10.15-slim-bookworm` build/runtime stages
- wheel-building in the builder stage
- UID/GID `10001` non-root runtime user
- `.dockerignore` protection for `.env`, virtualenvs, caches, local DBs and generated artifacts
- an image healthcheck
- API as the default command

Run as API:

```bash
docker run --rm --name ciis-api \
  --network host \
  --env-file .env \
  -e CIIS_ROLE=api \
  ciis-backend:phase7
```

Run the same image as worker:

```bash
docker run --rm --name ciis-worker \
  --network host \
  --env-file .env \
  -e CIIS_ROLE=worker \
  ciis-backend:phase7 \
  python -m app.workers.analysis_worker
```

`--network host` is only a Phase 7 learning/smoke-test convenience so existing localhost Postgres/MinIO/LocalStack endpoints work from the container. Phase 8 replaces this with a normal Compose network and service DNS names.

## Frontend image

Build from `frontend/`:

```bash
docker build \
  --build-arg REACT_APP_API_BASE_URL=/api \
  -t ciis-frontend:phase7 .
```

The frontend uses a pinned Node builder and `nginxinc/nginx-unprivileged` runtime. Nginx listens on port `8080` and proxies `/api/` to the future Phase 8 Compose service named `api`.

Standalone health smoke test:

```bash
docker run --rm -d --name ciis-frontend -p 8080:8080 ciis-frontend:phase7
curl http://127.0.0.1:8080/healthz
docker inspect --format '{{.State.Health.Status}}' ciis-frontend
docker stop ciis-frontend
```

The `/api/` proxy will only resolve once frontend and API share a Docker network (Phase 8); `/healthz` and static frontend serving can still be tested independently in Phase 7.

## What to inspect

```bash
docker image ls | grep ciis
docker history ciis-backend:phase7
docker inspect ciis-backend:phase7 --format '{{json .Config.User}}'
docker inspect ciis-frontend:phase7 --format '{{json .Config.User}}'
```

Expected backend runtime user is `10001:10001`. The unprivileged Nginx image supplies its own non-root runtime user.

Verify secrets were not baked into image history or filesystem. Runtime configuration is injected with environment variables / `--env-file`; `.env` is excluded from build context.

## Phase 7 acceptance

- backend tests pass, including Phase 7 static invariants
- `ciis-backend:phase7` builds
- same backend image runs as API and worker with different commands
- API runs as non-root
- frontend image builds and serves `/healthz`
- frontend runtime is unprivileged and listens on 8080
- both images report healthy when run in their supported smoke-test mode
- `.env`, local virtualenvs, SQLite files and generated artifacts are not copied into images

Phase 8 will add a single Compose network for frontend, API, worker, PostgreSQL, Prometheus and Grafana, then keep the AWS emulator separate.
