# Phase 14 — Secrets Management

## Goal

Remove runtime credentials from tracked application configuration and make
Floci Secrets Manager the local AWS-shaped source for Kubernetes runtime
secrets. The repository contains only secret names, configuration wiring and
the bootstrap procedure; it does not contain secret values.

## Runtime flow

```text
operator environment
        |
        v
scripts/bootstrap-secrets.sh
        |
        v
Floci Secrets Manager
  ciis/database
  ciis/application
        |
        v
scripts/phase14-sync-k8s-secrets.sh
        |
        v
Kubernetes Secret: ciis-runtime-secrets
        |
        +--> API init container and API
        +--> analysis worker
        +--> PostgreSQL
```

`ConfigMap/ciis-config` contains only non-secret endpoints, names and tuning
values. Storage and SQS access keys are now part of the application secret and
are injected through `ciis-runtime-secrets`.

The Python Secrets Manager client is configuration-driven and supports the
Floci endpoint through `SECRETS_MANAGER_ENDPOINT_URL` or `AWS_ENDPOINT_URL`.
The current Kubernetes path intentionally uses the explicit bootstrap/sync
bridge so the application does not need to call Secrets Manager during startup.
This keeps local startup deterministic while preserving an AWS-shaped secret
provider boundary for the next deployment stages.

## Local procedure

First create the secret containers through the Phase 9–13 Terraform workflow.
Then provide values only in the current shell or another local secret source:

```bash
export CIIS_DATABASE_URL='postgresql+psycopg://ciis:<password>@<host>:5432/ciis'
export CIIS_POSTGRES_PASSWORD='<postgres-password>'
export CIIS_AUTH_SECRET='<application-secret>'
export CIIS_STORAGE_ACCESS_KEY='<floci-access-key>'
export CIIS_STORAGE_SECRET_KEY='<floci-secret-key>'
export CIIS_SQS_ACCESS_KEY='<floci-access-key>'
export CIIS_SQS_SECRET_KEY='<floci-secret-key>'

bash scripts/bootstrap-secrets.sh
bash scripts/phase14-sync-k8s-secrets.sh
```

The two scripts use the isolated `scripts/floci-aws.sh` wrapper and never
write the secret values to a tracked file. The sync script is idempotent: it
uses `kubectl create secret ... --dry-run=client | kubectl apply -f -`.

## Verification

Static Phase 14 checks:

```bash
./.venv/bin/python -m pytest backend/test_phase14_secrets.py -q
bash -n scripts/bootstrap-secrets.sh
bash -n scripts/phase14-sync-k8s-secrets.sh
```

Deployment verification must additionally confirm that the Kubernetes Secret
exists before Helm deployment and that the API/worker pods receive the
expected keys. Secret values must be inspected only through the deployment's
secret-management controls; never print them into CI logs.

## Boundary

Phase 14 does not yet change password hashing, access-token semantics, roles,
case authorization, observability, or health endpoint semantics. Those are
Phase 15–17 concerns.
