FROM python:3.10.15-slim-bookworm AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip wheel --wheel-dir /wheels -r requirements.txt

FROM python:3.10.15-slim-bookworm AS runtime

# Pull current Debian security fixes into the runtime image so CI vulnerability
# scanning is evaluating the application on patched base packages.
RUN apt-get update && \
    apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    CIIS_ROLE=api

RUN groupadd --gid 10001 ciis && \
    useradd --uid 10001 --gid ciis --create-home --shell /usr/sbin/nologin ciis

WORKDIR /app

COPY --from=builder /wheels /wheels
COPY requirements.txt ./
RUN python -m pip install --no-index --find-links=/wheels -r requirements.txt && \
    rm -rf /wheels

COPY --chown=ciis:ciis . .

RUN mkdir -p /app/uploads && \
    chown -R ciis:ciis /app/uploads

USER 10001:10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-m", "app.container_healthcheck"]

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
