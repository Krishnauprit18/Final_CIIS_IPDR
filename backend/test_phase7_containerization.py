from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_backend_container_is_pinned_multistage_and_non_root():
    dockerfile = (REPO_ROOT / "backend" / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.10.15-slim-bookworm AS builder" in dockerfile
    assert "FROM python:3.10.15-slim-bookworm AS runtime" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "app.main:app" in dockerfile


def test_backend_docker_context_excludes_secrets_and_local_state():
    dockerignore = (REPO_ROOT / "backend" / ".dockerignore").read_text(encoding="utf-8")

    assert ".env" in dockerignore
    assert ".venv" in dockerignore
    assert "*.sqlite" in dockerignore
    assert "uploads" in dockerignore


def test_frontend_container_is_multistage_pinned_and_unprivileged():
    dockerfile = (REPO_ROOT / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    nginx = (REPO_ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")

    assert "FROM node:20.18.1-alpine3.20 AS build" in dockerfile
    assert "FROM nginxinc/nginx-unprivileged:1.27.3-alpine AS runtime" in dockerfile
    assert "REACT_APP_API_BASE_URL" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "listen 8080;" in nginx
    assert "proxy_pass http://api:8000/;" in nginx
