# syntax=docker/dockerfile:1.7
ARG PYTHON_VERSION=3.14

# ── Builder ───────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.11@sha256:798712e57f879c5393777cbda2bb309b29fcdeb0532129d4b1c3125c5385975a /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

RUN uv sync --no-dev --no-editable

# ── Dev ──────────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS dev

COPY --from=ghcr.io/astral-sh/uv:0.11.11@sha256:798712e57f879c5393777cbda2bb309b29fcdeb0532129d4b1c3125c5385975a /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./
COPY src/ ./src/

RUN uv sync

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# concurrency=1 for dev to keep logs readable; --reload via watchfiles is
# not used — Tilt rebuilds the image on source change instead.
CMD ["celery", "-A", "app.celery_app", "worker", \
     "--loglevel=debug", \
     "--concurrency=1", \
     "--queues=celery"]

# ── Production ───────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS production

RUN useradd -r -u 1001 -s /bin/false appuser

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER appuser

CMD ["celery", "-A", "app.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "--queues=celery"]
