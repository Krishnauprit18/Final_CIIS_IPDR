# CIIS Phase 0 Baseline

Status: Phase 0 complete; fresh-clone acceptance verified

This document records the actual Phase 0 environment, runtime, test, and build results. Values must be updated only from commands executed in this repository.

## Repository

- Branch: `chore/phase-0-repository-hygiene`
- Baseline commit before Phase 0 changes: `744593786e563d2568a46c9106d8178023f8a7d7`
- Phase 0 commit: recorded on `chore/phase-0-repository-hygiene`

## Environment

- OS: Linux
- Python: 3.10.12 observed before Phase 0
- Node: v24.5.0 observed before Phase 0
- npm: 11.13.0 observed before Phase 0
- Docker: installed; Floci image/container not found in the accessible Docker engine
- Podman: installed
- Floci endpoint configured in shell: `http://localhost:4566`
- Floci endpoint observed reachable: No; no service was listening during initial inspection

## Backend dependency baseline

Initial system-Python inspection found:

- `plotly` missing.
- `kaleido` missing.
- `scikit-learn` failed with a NumPy binary ABI incompatibility.

Phase 0 isolated environment result:

- `.venv` created successfully with Python 3.10.
- `backend/requirements-dev.txt` installed successfully.
- `python -m pip check`: PASS.
- FastAPI, Pandas, Plotly, scikit-learn, SciPy, and NetworkX imports: PASS.

Command:

```text
python -m pip check
```

Result:

```text
No broken requirements found.
```

## Backend health baseline

Command:

```text
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

Initial system-Python result:

```text
Failed before startup: ModuleNotFoundError: No module named 'plotly'
```

Phase 0 virtual-environment result:

```text
Uvicorn application startup: PASS.
Application startup complete: PASS.
The sandbox blocked a separate shell from reaching the temporary loopback port, so route logic was also verified in-process.
```

The application must be started from `backend/` because the current implementation uses the relative dataset path `../Scenario A1-ARFF/synthetic.csv`.

In-process route/data verification from the correct `backend/` working directory:

```text
main_import=PASS
startup_event=PASS
process_seconds=14.92
process_records=12000
process_persisted=False
search_total_records=12000
graph_nodes=74
graph_edges=50
bparty_ip_groups=8000
bparty_phone_groups=0
phone_matching_records=41
```

## Dataset processing baseline

Dataset:

```text
Scenario A1-ARFF/synthetic.csv
```

Observed dataset size:

- Approximately 12,000 records.
- 25 columns.

Direct normalizer verification before Phase 0:

- Normalized shape: `(12000, 25)`.
- Relationship extraction: 12,000 row-level relationships.
- A-Party summary: 300 grouped entities.
- Phone search and IP search executed successfully in isolation.

API processing result:

```text
PASS: 12,000 records processed in approximately 14.92 seconds.
```

## Backend test baseline

Command:

```text
python -m pytest backend -q -ra
```

Result:

```text
8 passed, 8 warnings in 1.06s
```

Known test-suite risks from repository inspection:

- Several tests reference `/home/krishna/Music/CIIS (Part 2)/...` instead of this checkout.
- `test_dashboard_api.py` expects older route names such as `/upload/`.
- Several tests are print-based procedural scripts rather than assertion-focused tests.
- Existing tests return booleans instead of using assertions, producing `PytestReturnNotNoneWarning`.
- The passing pytest result is therefore a structural baseline, not complete behavioral proof.

## Frontend baseline

Initial frontend result before dependency installation:

```text
Failed: react-scripts: not found
```

This was caused by the absence of `frontend/node_modules`.

Phase 0 commands:

```text
npm ci
npm run build
```

Result:

```text
PASS: 1,395 packages added and audited.
Warning: npm reported 60 dependency audit findings (12 low, 15 moderate, 31 high, 2 critical).
```

Production build result:

```text
PASS: Compiled successfully.
Gzipped JavaScript: 516.56 kB.
Gzipped CSS: 493 B.
```

## Frontend test baseline

Command:

```text
CI=true npm test -- --watchAll=false --runInBand
```

Result:

```text
FAIL: Jest could not parse the ESM Axios package.
Tests: 0 executed.
Root error: SyntaxError: Cannot use import statement outside a module.
```

This is documented as a baseline issue and was not changed during Phase 0.

## Secret review

The committed `backend/.env` contained only these key names:

- `LLM_PROVIDER`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

No AWS key, API token, password, private key, or secret-named variable was identified during the value-redacted review. No credential rotation was required from this file. The file has been removed from Git tracking and preserved locally as ignored state.

## Frontend runtime baseline

Result:

```text
The CRA development server could not bind to 0.0.0.0 or 127.0.0.1 in the
managed execution sandbox (`listen EPERM`). The production build is verified;
interactive browser verification remains an environment limitation.
```

## Repository hygiene target

The final Phase 0 Git index must not contain:

- `.env` files except `.env.example`.
- SQLite databases or database backups.
- `uploads/` contents.
- `__pycache__/` directories.
- `.pyc` files.
- Generated reports and local artifacts.
- Local infrastructure state.

The final Phase 0 repository must contain:

- Root `.gitignore`.
- `backend/.env.example`.
- `backend/requirements-dev.txt`.
- `docs/current-architecture.md`.
- `docs/phase-0-baseline.md`.

## Fresh-clone verification

Result:

```text
PASS: clone contains no tracked .env, SQLite database, database backup,
uploads, __pycache__, or .pyc files before local runtime state is created.
PASS: backend dependencies installed and pip check reported no broken requirements.
PASS: backend acceptance from the documented backend/ working directory processed
12,000 records successfully.
PASS: frontend npm ci completed and npm run build compiled successfully.
```

The fresh-clone backend acceptance must run from `backend/`, because the current
application resolves `../Scenario A1-ARFF/synthetic.csv` relative to the current
working directory. Runtime-created SQLite files and caches are ignored by the
root `.gitignore` and are not part of the clone's tracked state.

The frontend Jest baseline remains a known issue: Axios ESM parsing fails before
tests execute. This was documented but intentionally not changed in Phase 0.
