# Phase 24 — Test quality

## Coverage added

- Backend CI now runs the complete PostgreSQL-backed suite with `pytest-cov`
  and archives `.ci-artifacts/backend/coverage.xml`.
- Frontend CI now runs lint, tests, build, and Cobertura coverage; the report
  is archived at `.ci-artifacts/frontend/coverage.xml`.
- Reliability/data-integrity unit tests cover valid and invalid IPDR gates,
  deterministic hashes, and the append-only migration contract.
- Frontend tests cover terminal job polling and transient polling failure with
  retry behavior.
- Existing authentication, API, worker, migration, and health tests remain in
  the same CI suite rather than being replaced by smoke-only tests.

## Test layers and remaining environment-dependent evidence

- Domain/unit: runnable without infrastructure.
- Repository/API/worker integration: run by `scripts/ci/backend-test.sh` with
  a disposable PostgreSQL container and Alembic migrations.
- Frontend critical flow: runs with React Testing Library in `frontend-ci.sh`.
- Storage/SQS/Kubernetes failure labs and Locust load tests require explicitly
  started local infrastructure and are kept out of the default PR test path.

The pipeline archives measurements and reports; it does not enforce an
arbitrary coverage percentage without a baseline review.
