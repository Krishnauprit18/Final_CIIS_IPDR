from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_helm_configmap_contains_no_credential_values():
    source = (
        PROJECT_ROOT / "deploy" / "helm" / "ciis" / "templates" / "configmap.yaml"
    ).read_text(encoding="utf-8")

    assert "STORAGE_ACCESS_KEY" not in source
    assert "STORAGE_SECRET_KEY" not in source
    assert "SQS_ACCESS_KEY" not in source
    assert "SQS_SECRET_KEY" not in source


def test_workloads_require_the_runtime_secret():
    for name in ("api-deployment.yaml", "worker-deployment.yaml"):
        source = (
            PROJECT_ROOT / "deploy" / "helm" / "ciis" / "templates" / name
        ).read_text(encoding="utf-8")
        assert "name: ciis-runtime-secrets" in source
        assert "optional: false" in source


def test_bootstrap_and_sync_cover_all_runtime_secret_keys():
    bootstrap = (PROJECT_ROOT / "scripts" / "bootstrap-secrets.sh").read_text(
        encoding="utf-8"
    )
    sync = (
        PROJECT_ROOT / "scripts" / "phase14-sync-k8s-secrets.sh"
    ).read_text(encoding="utf-8")

    required = {
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "AUTH_SECRET",
        "STORAGE_ACCESS_KEY",
        "STORAGE_SECRET_KEY",
        "SQS_ACCESS_KEY",
        "SQS_SECRET_KEY",
    }

    for key in required:
        assert key in bootstrap
        assert key in sync


def test_terraform_declares_secret_containers_without_values():
    source = (
        PROJECT_ROOT / "infra" / "terraform" / "modules" / "secrets" / "main.tf"
    ).read_text(encoding="utf-8")

    assert "aws_secretsmanager_secret" in source
    assert "secret_string" not in source


def test_secret_client_is_config_driven():
    source = (
        PROJECT_ROOT / "backend" / "app" / "secrets" / "client.py"
    ).read_text(encoding="utf-8")

    assert "SECRETS_MANAGER_ENDPOINT_URL" in source
    assert "AWS_REGION" in source
    assert "AWS_ACCESS_KEY_ID" in source
    assert "AWS_SECRET_ACCESS_KEY" in source
    assert "os.getenv" not in source
