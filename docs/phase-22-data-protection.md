# Phase 22 — Data protection

## Implemented controls

- PostgreSQL `audit_events` is append-only at the database trigger boundary;
  the application also continues to write audit events through one repository.
- Analysis jobs retain input SHA-256, result SHA-256, and quarantine URI.
- Terraform now declares S3-compatible public-access blocking, versioning, and
  scoped lifecycle retention: raw inputs 30 days, results 90 days, and
  non-current versions retained for a shorter recovery window.
- The local MinIO initializer enables versioning and a raw-input expiry rule.
- `scripts/data-protection/configure-object-storage.sh` applies the complete
  policy to a running Floci/MinIO-compatible endpoint and prints the readback.
- `postgres-backup.sh` creates a custom-format, checksummed backup.
- `postgres-restore-drill.sh` restores only to an explicitly supplied,
  disposable target and verifies the restored Alembic revision.

## Commands

```bash
DATABASE_URL='postgresql+psycopg://ciis:ciis@127.0.0.1:55432/ciis' \
  bash scripts/data-protection/postgres-backup.sh

STORAGE_ENDPOINT_URL='http://127.0.0.1:59000' \
  bash scripts/data-protection/configure-object-storage.sh
```

For a non-default local endpoint, pass `STORAGE_ACCESS_KEY` and
`STORAGE_SECRET_KEY`; these endpoint-specific values take precedence over any
ambient AWS CLI credentials in the shell.

For restore, set `RESTORE_DATABASE_URL` to a disposable database and require
`ALLOW_RESTORE_TARGET=1`. The source database is never used as the restore
target by this script.

## Migration rollback strategy

1. Take and checksum a PostgreSQL backup before a schema deployment.
2. Apply additive/expand migrations first and verify `alembic current`.
3. Deploy code that is compatible with both old and new columns.
4. Run the restore drill in a disposable database.
5. Roll back application code first if needed. Use `alembic downgrade -1`
   only against a reviewed, backed-up environment; never execute a downgrade
   blindly in production.

These scripts demonstrate the workflow locally; they do not turn local Floci
or MinIO into an AWS durability guarantee.
