# syntax=docker/dockerfile:1.7
# Three-stage build: builder → dev | production
# • dev:        editable install, uvicorn --reload (used by Tilt)
# • production: non-editable wheel in .venv, minimal attack surface

ARG PYTHON_VERSION=3.14

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.11@sha256:798712e57f879c5393777cbda2bb309b29fcdeb0532129d4b1c3125c5385975a /uv /usr/local/bin/uv

WORKDIR /app

# Layer deps separately so Docker cache survives source-only changes.
COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

# Install production deps only; --no-editable bakes the package into the venv.
RUN uv sync --no-dev --no-editable

# ── Dev ──────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS dev

COPY --from=ghcr.io/astral-sh/uv:0.11.11@sha256:798712e57f879c5393777cbda2bb309b29fcdeb0532129d4b1c3125c5385975a /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

# Editable install + dev deps so pytest can run inside the container too.
RUN uv sync

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--reload"]

# ── Production ───────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS production

RUN useradd -r -u 1001 -s /bin/false appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c \
        "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--no-access-log"]
