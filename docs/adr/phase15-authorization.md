# ADR: Phase 15 authentication and authorization

## Decision

CIIS separates authentication from authorization.

Authentication proves who the caller is. Authorization decides which cases and actions the caller may access.

## Passwords

New passwords use Argon2id through argon2-cffi. Existing PBKDF2-SHA256 and legacy SHA-256 hashes remain readable only for migration. A successful legacy login immediately replaces the stored hash with Argon2id and clears the old salt.

## Sessions

Access tokens are signed JWTs with a 15 minute lifetime.

Refresh sessions are server-side PostgreSQL records with a 7 day lifetime. The browser receives the raw refresh token only through an HttpOnly SameSite cookie. PostgreSQL stores only the SHA-256 token hash.

Refresh rotates the refresh token. The old refresh session is revoked before a new one is issued.

Logout revokes the current refresh session. Logout-all revokes every active refresh session for the user.

## Global roles

- ADMIN: global administrative access.
- INVESTIGATOR: case access requires membership.
- VIEWER: case access requires membership and remains read-oriented.

Existing users are migrated to INVESTIGATOR.

## Case roles

- OWNER
- EDITOR
- VIEWER

A user creating a case becomes OWNER.

ADMIN bypasses case membership. Other users require explicit membership.

Read operations accept OWNER, EDITOR and VIEWER. Mutating case analysis/search operations require OWNER or EDITOR. Membership changes require OWNER or ADMIN.

## Audit

Structured audit_events record security-relevant actions such as login, registration, refresh, password changes, case creation, membership changes, analysis submission, export and permission denial.

Passwords, access tokens, refresh tokens and raw evidence content are never stored in audit metadata.

## Browser storage

Only the short-lived access token remains in the existing frontend localStorage compatibility path. The longer-lived refresh token is HttpOnly and therefore unavailable to JavaScript. A later hardening pass may move the access token to in-memory storage as well.
