# CIIS IPDR Analysis Platform — CV Content

This document is the evidence-based CV draft for the CIIS IPDR project. It is written for DevOps, Cloud/Platform Engineering, SRE, and DevSecOps applications.

The wording intentionally describes a **production-shaped local platform**. The project uses Floci and other AWS-compatible local services for emulation; it should not be presented as a live production AWS deployment or as a system serving real users.

## Recommended project title

**CIIS IPDR Analysis Platform — Production-Shaped Distributed System**

## One-line project description

Re-architected a FastAPI IPDR analysis application from a local monolith into a containerized, asynchronous, production-shaped platform using PostgreSQL, S3-compatible object storage, SQS-style workers, Kubernetes/Helm, Terraform, Jenkins CI, GitOps, observability, and DevSecOps controls.

## Resume-ready version — recommended

**CIIS IPDR Analysis Platform | DevOps / Platform Engineering Project**

GitHub: [Application repository](https://github.com/Krishnauprit18/Final_CIIS_IPDR) · [GitOps deployment repository](https://github.com/Krishnauprit18/CIIS_deployment_config)

- Re-architected a FastAPI IPDR analysis application from a monolithic SQLite/local-file design into a modular, containerized distributed workflow with PostgreSQL/Alembic persistence, S3-compatible object storage, and an asynchronous SQS-style analysis worker with retry, DLQ, job-claim, and duplicate-delivery handling.
- Containerized the API, worker, and React frontend with Docker and Docker Compose; created a Floci-based local AWS-compatible environment for ECR, S3, SQS, IAM/secrets, and EKS-style infrastructure development without using production cloud credentials.
- Built a Jenkins CI pipeline covering backend linting and PostgreSQL-backed tests, frontend lint/test/build, Docker image creation, Trivy vulnerability scanning, dependency and secret scanning, Bandit SAST, Terraform/Helm validation, CycloneDX SBOM generation, and container integration checks.
- Implemented immutable Git-SHA image publishing and separated deployment configuration into a GitOps repository containing Helm environment values and an Argo CD application definition for environment reconciliation.
- Added production-oriented observability and operations controls with Prometheus metrics, Grafana dashboards, OpenTelemetry/Jaeger tracing, structured request correlation, API/worker liveness and readiness probes, retry visibility, and health-aware Kubernetes deployments.
- Implemented application security and data-protection controls including Argon2 password hashing, JWT-based authentication, RBAC and case authorization, audit events, S3-compatible versioning/lifecycle configuration, SHA-256 integrity metadata, invalid-input quarantine, and PostgreSQL backup/restore drill scripts.

## Short version — for a one-page CV

**CIIS IPDR Analysis Platform | DevOps / Cloud Engineering Project**

- Modernized a FastAPI IPDR analysis application into a production-shaped distributed platform using PostgreSQL/Alembic, S3-compatible storage, SQS-style asynchronous workers, Docker, Kubernetes/Helm, Terraform, and Floci AWS emulation.
- Implemented Jenkins CI with backend/frontend quality gates, Docker builds, Trivy dependency/image/filesystem scans, Gitleaks, Bandit, SBOM generation, Helm/Terraform validation, container integration testing, and immutable Git-SHA image publishing.
- Added GitOps deployment configuration with Helm environment values and Argo CD, plus Prometheus/Grafana/OpenTelemetry observability, health probes, RBAC, audit logging, retry/DLQ handling, data-integrity hashes, and quarantine workflows.

## Slightly more humanized version — interview or LinkedIn project section

I took an existing FastAPI IPDR analysis application and evolved it into a production-shaped platform rather than only adding infrastructure around the original code. The application now separates API requests from asynchronous analysis work, persists application state in PostgreSQL, stores uploaded and generated artifacts behind an S3-compatible storage boundary, and uses an SQS-style queue with worker retry and DLQ behavior. I containerized the runtime, modeled the local AWS environment with Floci, defined infrastructure with Terraform and Helm, added Jenkins quality/security gates, and separated deployment configuration into a GitOps repository for Argo CD. The project also includes observability, health semantics, authentication/RBAC, audit logging, data-integrity metadata, backup/restore scripts, reliability-lab scripts, and a Locust load-testing harness.

## Skills and technology keywords

Use only the keywords relevant to the job description. The repository supports the following verified project technologies:

**Cloud and infrastructure:** AWS-compatible local emulation, Floci, Terraform, ECR-compatible registry, S3-compatible storage, SQS-compatible queues, IAM/secrets configuration, Kubernetes/EKS-style deployment definitions.

**Containers and deployment:** Docker, Docker Compose, Helm, Kubernetes, Argo CD, GitOps, non-root container images, readiness/liveness probes.

**CI/CD and DevSecOps:** Jenkins, immutable Git-SHA tags, pip-audit, npm audit, Gitleaks, Bandit, Trivy, Syft/CycloneDX SBOM, Helm lint, Terraform validate, container integration tests.

**Backend and distributed systems:** Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, boto3, S3 boundaries, SQS-style workers, retry handling, DLQ, idempotent job claims, asynchronous processing, REST APIs.

**Observability and reliability:** Prometheus, Grafana, OpenTelemetry, Jaeger, structured logging, request correlation, health/readiness checks, failure-lab automation, backup/restore drills, Locust.

**Frontend:** React, TypeScript, React Testing Library, Plotly-based visualization and frontend CI build validation.

## Evidence-backed project facts

These details were checked against the local repository and the two public GitHub repositories. They are useful for interview preparation but do not all need to appear on the CV.

- The application repository contains the FastAPI application, React frontend, Dockerfiles, Compose environments, Terraform modules, Helm chart, Jenkinsfile, CI/security scripts, performance harness, reliability scripts, and phase documentation.
- The application repository currently contains a dedicated `backend/app` package with API routers, authentication, database, storage, queue, worker, health, observability, and service boundaries.
- The runtime dependency set includes FastAPI, SQLAlchemy, Alembic, psycopg, boto3, Prometheus client libraries, Argon2, PyJWT, and OpenTelemetry instrumentation.
- The Jenkins pipeline includes backend lint, backend tests, frontend CI, dependency security, SAST, secret scanning, Trivy filesystem scanning, Docker image builds, Trivy image scanning, SBOM generation, Helm validation, Terraform validation, IaC scanning, container integration, and conditional immutable image publishing.
- The separate `CIIS_deployment_config` repository is public and contains `chart`, `argocd`, and environment-oriented deployment configuration. It is intentionally separate from the application repository to demonstrate CI/CD and GitOps separation.
- The recorded backend verification reached `60 passed` with legacy-test warnings; frontend lint, tests, and production build also passed in the recorded verification. These numbers should be refreshed before being quoted as a current project metric.
- The project documentation explicitly avoids claiming that local Floci/MinIO provides AWS durability or that the application is a live production AWS service.

## What not to claim on the CV

Do not write any of the following unless the project is later verified in that exact environment:

- “Deployed and operated in production AWS.”
- “Production EKS experience” without clearly saying that this project uses local AWS-compatible emulation and Kubernetes deployment definitions.
- “Zero vulnerabilities.” The pipeline is designed to fail on blocking findings, but the repository also contains documented, time-bounded local-emulator/base-image exceptions.
- “Handled X users,” “X requests per second,” “Y% latency reduction,” or “Z% cost reduction.” No measured performance result should be invented; the Locust harness is present, but a resume metric requires a recorded run.
- “Achieved high availability,” “multi-region disaster recovery,” or “guaranteed durability.” The project contains local reliability and backup/restore workflows, not a managed multi-region AWS durability guarantee.
- “Built a fully independent microservices architecture.” The current design is better described as a modular application plus separate API/worker runtime processes, not a large fleet of independently deployed business microservices.

## Best positioning by target role

### DevOps Engineer

Emphasize Jenkins, Docker, Compose, Terraform, Helm, Kubernetes, automated quality/security gates, shell automation, and troubleshooting of local CI/infrastructure dependencies.

### Cloud Engineer

Emphasize AWS-compatible Floci emulation, Terraform modules, ECR/S3/SQS/IAM/secrets boundaries, PostgreSQL, Helm, and the distinction between local emulation and managed AWS services.

### Platform Engineer

Emphasize the platform workflow: application containerization, reusable CI gates, GitOps repository separation, Argo CD reconciliation, observability, health semantics, secrets boundaries, and developer-facing scripts/documentation.

### SRE / Reliability Engineer

Emphasize worker retries, DLQ behavior, duplicate-delivery protection, readiness/liveness semantics, failure-lab scripts, quarantine handling, audit logging, backup/restore drills, and the Locust harness. Add numerical reliability or latency claims only after recording experiments.

### DevSecOps Engineer

Emphasize dependency scanning, secret scanning, SAST, Trivy filesystem/image/IaC scanning, SBOM generation, critical-finding blocking, narrowly scoped exceptions, non-root images, Argon2/JWT/RBAC, and audit events.

## Suggested interview explanation

“I started with an existing FastAPI IPDR analysis application and treated it as a modernization exercise. The first goal was to preserve the application behavior while creating clearer boundaries. I then moved persistence to PostgreSQL, placed uploaded and generated artifacts behind an object-storage abstraction, and moved expensive analysis to a queue-backed worker. After that I containerized the API, worker, and frontend, modeled the AWS dependencies locally with Floci, added Terraform and Helm definitions, and built Jenkins gates for tests, security scans, image creation, SBOMs, and integration checks. I kept deployment configuration in a separate GitOps repository so CI could build and publish while Argo CD reconciled the desired deployment state. The project is deliberately honest about its scope: it is a locally emulated, production-shaped platform, not a claim of operating a live production AWS system.”

## Portfolio links

- Application and platform repository: <https://github.com/Krishnauprit18/Final_CIIS_IPDR>
- GitOps deployment repository: <https://github.com/Krishnauprit18/CIIS_deployment_config>

## Why this wording matches current DevOps/platform hiring language

Recent platform and infrastructure job descriptions commonly group together Kubernetes, Docker, Terraform, Helm, CI/CD, GitOps, observability, security, reliability, secrets management, and operational documentation. This project genuinely contains those categories, but the wording above qualifies local emulation and unmeasured areas instead of converting design intent into unsupported production claims.

Research references:

- [Zopa — Senior Platform Engineer](https://jobs.lever.co/zopa/33ed6dc4-4578-4737-8409-d843e7847aad)
- [Smarsh — Platform Engineer III, AWS Network](https://jobs.lever.co/smarsh/51200110-1501-45cb-83ef-9cb472304bba)
- [PointClickCare — Senior Software Engineer, Platform Engineering](https://jobs.lever.co/pointclickcare/560fc3cf-e98e-44aa-b9b8-3ac3f3513b68)
- [Valarian Technologies — Platform Engineer](https://jobs.lever.co/valarian/4199857d-92f7-4bbc-9e28-51a75d76e8e1)
- [100ms — Platform Engineer, Core Infrastructure](https://jobs.lever.co/100ms/250f1e05-83be-4582-ac62-c5dea6a30b8)

## Final recommendation

For a one-page CV, use the **Short version** or the **Resume-ready version** with four to six bullets. Keep the two repository links. During interviews, use the **Suggested interview explanation** and be explicit that Floci is the local AWS-compatible emulator and that any performance/reliability numbers must come from recorded experiments.
