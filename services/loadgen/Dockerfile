# syntax=docker/dockerfile:1.7
# Three-stage build: builder → dev | production
# Locust is configured entirely via LOCUST_* env vars (set in Helm values).

ARG PYTHON_VERSION=3.14

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

RUN uv sync --no-dev --no-editable

# ── Dev ──────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS dev

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

RUN uv sync

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

CMD ["locust", "-f", "/app/src/app/locustfile.py"]

# ── Production ───────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS production

RUN useradd -r -u 1001 -s /bin/false appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

CMD ["locust", "-f", "/app/src/app/locustfile.py"]
