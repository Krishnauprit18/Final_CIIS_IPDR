# Phase 15 — Authentication and Authorization

## Passwords

New registrations and password changes use Argon2id with an explicit memory,
time and parallelism profile. Existing PBKDF2 and legacy SHA-256 records remain
readable only for migration: after a successful legacy login, the password is
rewritten as Argon2id and the old salt is cleared.

The application never logs or returns password material. `password_salt` is
retained only as a backwards-compatible database column for records that have
not yet logged in after the migration.

## Sessions

The API returns a random opaque bearer token once. PostgreSQL stores only its
SHA-256 digest in the existing `sessions.token` column. Token verification
hashes the presented bearer value before lookup, so a database read does not
reveal active bearer credentials. Migration `0003_phase15_auth_security`
invalidates sessions created before this behavior was deployed.

Sessions remain short-lived (24 hours in the current compatibility handler),
and logout/password change invalidates all sessions for the user. Refresh-token
rotation is intentionally left for a later auth API phase; this phase removes
the plaintext-session and weak-new-password paths first.

## Roles and case access

Users have an application role (`analyst` by default). Each case can have a
`case_memberships` row with `viewer`, `analyst` or `owner` access. Case creators
are treated as owners for backwards compatibility and receive an explicit
owner membership on creation.

The following case operations require membership:

- list cases only returns owned or explicitly shared cases;
- analysis upload and saved-search writes require analyst access;
- saved-search reads, case-pack export and case network-map reads require
  viewer access;
- asynchronous case analysis jobs require an authenticated analyst.

Unauthorized existing cases return `403` rather than leaking case contents.
Audit events continue to be written through the existing `audit_logs` boundary
for login, logout, registration, password changes and case operations.

## Migration and verification

```bash
./.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
./.venv/bin/python -m pytest backend/test_phase15_auth_security.py -q
./.venv/bin/python -m pytest backend -q -ra
```

The migration adds `users.role`, creates `case_memberships`, adds indexes and
invalidates pre-Phase-15 sessions. Apply it before starting API/worker pods;
the Helm API init container already runs `alembic upgrade head`.

## Boundary

Phase 15 does not claim a full external identity provider, refresh-token
rotation, or multi-tenant policy engine. Those can be layered onto the
explicit authentication and case-membership boundaries later without moving
password/session logic back into the monolithic handler.
