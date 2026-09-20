# Phase 20 - Security Pipeline

## Policy

The Jenkins pipeline runs dependency scanning, secret scanning, SAST, Trivy
filesystem scanning, Trivy image scanning, Terraform/Kubernetes IaC scanning,
and CycloneDX SBOM generation.

Critical vulnerability findings fail the pipeline. Secret findings fail the
pipeline. High-confidence/high-severity Bandit findings fail the pipeline.
Low and medium SAST findings remain in the archived report for remediation;
they are not silently ignored.

## Implemented scanners

| Area | Tool | Report | Blocking rule |
| --- | --- | --- | --- |
| Python dependencies | pip-audit | `.ci-artifacts/pip-audit.json` | Any known backend dependency vulnerability |
| Node dependencies | npm audit | `.ci-artifacts/npm-audit.json` | Critical findings |
| Secret scanning | Gitleaks | `.ci-artifacts/gitleaks.sarif` | Any detected secret |
| Python SAST | Bandit | `.ci-artifacts/bandit.json` | High severity and high confidence |
| Filesystem | Trivy | `.ci-artifacts/trivy-filesystem.json` | Critical findings |
| Images | Trivy | `.ci-artifacts/*.trivy.json` | Critical findings except documented exact base-image IDs |
| Terraform | Trivy config | `.ci-artifacts/trivy-terraform.json` | Critical findings except documented local-emulator IDs |
| Kubernetes/Helm | Trivy config | `.ci-artifacts/trivy-kubernetes.json` | Critical findings |
| SBOM | Syft | `.ci-artifacts/*.cdx.json` | Artifact generation must succeed |

## Narrow local-emulator exceptions

The following exact Trivy IDs are currently allowlisted only because the local
Floci Terraform emulator models an EKS-compatible API and does not expose the
same private-endpoint controls as managed AWS EKS:

| Finding ID | Scope | Reason | Compensating control | Owner | Created | Expiry | Remediation issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AWS-0040 | `infra/terraform` local Floci environment | Local emulator endpoint model does not provide the managed-EKS private endpoint setting | Local-only cluster, loopback/local Docker access, no production credentials | CIIS maintainers | 2026-09-20 | 2026-12-20 | Replace with provider-supported private endpoint configuration before real AWS deployment |
| AWS-0041 | `infra/terraform` local Floci environment | Local emulator CIDR behavior is required for the local lab network | Local-only cluster, no public cloud account, Floci endpoint restricted to the local machine | CIIS maintainers | 2026-09-20 | 2026-12-20 | Restrict EKS API CIDRs before any real AWS deployment |

These exceptions are exact IDs only. No wildcard critical, secret, or path-wide
security suppression is permitted.

## Time-bounded base-image exceptions

The backend runtime is currently based on `python:3.10.15-slim-bookworm`. The
Trivy database reports the following CRITICAL Debian advisories against the
base OS packages, with no fixed version available from the Debian Bookworm
repositories used by that image at the time of this Phase 20 implementation:

| Finding ID | Package | Scope | Compensating control | Owner | Created | Expiry | Remediation issue |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CVE-2025-7458 | `libsqlite3-0` | Backend runtime image | PostgreSQL is the application persistence path; image is non-root and SQLite is not exposed as a service | CIIS maintainers | 2026-09-20 | 2026-12-20 | Re-evaluate on every base-image refresh and move to a fixed Debian/Python base |
| CVE-2026-13221 | `perl-base` | Backend runtime image | Perl is not an application runtime dependency; image runs as UID 10001 | CIIS maintainers | 2026-09-20 | 2026-12-20 | Re-evaluate on every base-image refresh and move to a fixed Debian/Python base |
| CVE-2026-42496 | `perl-base` | Backend runtime image | Perl is not an application runtime dependency; image runs as UID 10001 | CIIS maintainers | 2026-09-20 | 2026-12-20 | Re-evaluate on every base-image refresh and move to a fixed Debian/Python base |
| CVE-2026-8376 | `perl-base` | Backend runtime image | Perl is not an application runtime dependency; image runs as UID 10001 | CIIS maintainers | 2026-09-20 | 2026-12-20 | Re-evaluate on every base-image refresh and move to a fixed Debian/Python base |
| CVE-2023-45853 | `zlib1g` | Backend runtime image | The advisory concerns unsupported MiniZip functionality; no MiniZip package/API is used by this service | CIIS maintainers | 2026-09-20 | 2026-12-20 | Re-evaluate on every base-image refresh and move to a fixed Debian/Python base |

These are not treated as generally safe. They are explicit, reviewable,
time-bounded exceptions because the current distribution reports no fix. If a
fixed package becomes available, the exception must be removed and the image
rebuilt immediately.

## Report handling

Reports are Jenkins artifacts and are intentionally excluded from Git. A
finding may only be added to `.trivyignore` after its exact ID, scope, owner,
expiry and remediation issue are documented here.
