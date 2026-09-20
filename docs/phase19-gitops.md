# Phase 19 - GitOps Continuous Delivery

## Boundary

Jenkins is responsible for checkout, linting, tests, container builds,
security validation, integration tests, and immutable Git-SHA image publishing.
Jenkins does not run `helm upgrade`, `kubectl apply`, or `terraform apply` as
part of the normal application delivery path.

The separate `CIIS_deployment_config` repository stores the Helm chart,
environment values, and Argo CD Application definition. Argo CD watches that
repository and reconciles the Kubernetes cluster to the Git state.

## Local Floci notes

The local Floci EKS emulator currently exposes a Docker-network IP to the
Kubernetes cluster through the chart's `floci-local` Service and Endpoints
resource. The development values file therefore contains the current local
Floci bridge IP. Recreating the Floci container can change that IP; update the
GitOps development values and commit the new desired state when that happens.

The `ciis-runtime-secrets` Kubernetes Secret is bootstrap-managed by the
existing Phase 14 workflow. Plaintext secret values are not stored in either
repository.

## Verified flow

1. Jenkins-published immutable images are tagged with the application Git SHA.
2. The GitOps development values select that SHA.
3. Argo CD reports the `ciis-dev` Application as `Synced` and `Healthy`.
4. API, worker, web, and PostgreSQL workloads are Ready.
5. API liveness and readiness checks pass; readiness reports database, storage,
   and queue dependencies as healthy.
6. A manual replica drift is restored by Argo CD self-healing.

## Recovery behavior

`scripts/phase12-13-deploy.sh` remains a manual bootstrap and recovery tool.
It is not the normal CD path. `scripts/phase13-kube-env.sh` tolerates a
transient Floci `CREATING` status only when the existing Kubernetes API is
actually reachable; otherwise it still fails safely.
