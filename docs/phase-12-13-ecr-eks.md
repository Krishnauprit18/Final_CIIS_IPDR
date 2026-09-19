# Phase 12–13 — Local ECR, Floci EKS and Helm

## Simple summary

Phase 12 changed CIIS from "Docker images only on the developer machine" to a registry workflow:

```text
code -> Docker build -> Git SHA tag -> Floci ECR -> Kubernetes pulls image
```

Three immutable repositories are managed by Terraform:

```text
ciis-api
ciis-worker
ciis-web
```

Phase 13 changed the runtime from Compose-only workloads to a real local Kubernetes lab through Floci EKS real mode (k3s):

```text
Browser
  -> ciis-web
  -> api Service
  -> ciis-api
       -> PostgreSQL
       -> Floci S3
       -> Floci SQS
            -> ciis-worker
            -> result back to S3/PostgreSQL
```

## What was implemented

- Floci persistent mode and real EKS/k3s mode.
- Terraform ECR and EKS modules.
- Dedicated local IAM identity for kubectl/EKS authentication.
- Git-SHA image build and push to Floci ECR.
- Helm chart for API, worker, frontend and PostgreSQL.
- ConfigMap and Secret separation for local configuration.
- Alembic migration init container before API startup.
- Readiness/liveness probes and resource requests/limits.
- Kubernetes Service/Endpoints bridge named `floci-local` so pods can reach Floci S3/SQS without relying on Docker Compose DNS.
- Stale NotReady k3s node cleanup during deployment.
- kubeconfig credential pinning so later test/test AWS CLI credentials do not break kubectl.
- `scripts/floci-aws.sh` for isolated local AWS commands.
- `scripts/phase13-verify.sh` for infrastructure smoke verification.
- `scripts/phase12-13-acceptance.sh` for system acceptance.

## Acceptance scenarios

`phase12-13-acceptance.sh` covers:

1. End-to-end analysis: CSV -> API -> S3 -> PostgreSQL job -> SQS -> worker -> result -> SUCCEEDED.
2. Worker scaling: two worker replicas process submitted jobs independently from the API.
3. Worker crash recovery: kill the active worker during RUNNING, Kubernetes replaces it, SQS/lease retry lets the job finish.
4. ECR immutability: a conflicting push to the same Git-SHA tag must fail and the registry digest must remain unchanged.

If the normal sample finishes too quickly for the crash test, Step 21 reports `INCONCLUSIVE` rather than a false pass; rerun with a larger file via `CIIS_ACCEPTANCE_DATASET`.

## Commands

Infrastructure verification:

```bash
source scripts/phase13-kube-env.sh
bash scripts/phase13-verify.sh
```

Full Phase 12/13 acceptance:

```bash
bash scripts/phase12-13-acceptance.sh
```

For normal Floci AWS inspection use:

```bash
bash scripts/floci-aws.sh s3 ls
bash scripts/floci-aws.sh sqs list-queues
```

Do not export test/test credentials into the interactive shell used by kubectl.

## Current boundary

This is a production-shaped local AWS/Kubernetes lab, not real AWS production. PostgreSQL is still running inside Kubernetes for this phase. RDS, Secrets Manager, dedicated /health/live and /health/ready endpoints, Ingress, HPA, PDB, NetworkPolicy, stronger ServiceAccount/RBAC, Jenkins/CD and later reliability/security work remain future phases.
