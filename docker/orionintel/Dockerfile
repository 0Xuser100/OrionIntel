# ── builder ─────────────────────────────────────────────────────────
# Reuses your uv + pyproject setup (same as src/Dockerfile) but the build
# context here is the REPO ROOT, so it can also copy docker/orionintel/*.
FROM python:3.12-slim AS builder

# bring in the uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# install dependencies first (layer cached unless lock/manifest change)
COPY src/pyproject.toml src/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ── runtime ─────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# system deps: bash for the entrypoint, curl for optional healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    bash curl \
    && rm -rf /var/lib/apt/lists/*

# non-root user
RUN useradd -m -u 1000 appuser

# prebuilt virtualenv from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# application source
COPY src/ /app

# deploy-specific Alembic config (points at the pgvector SERVICE, not localhost).
# alembic env.py reads the DB URL from this .ini, so it must exist in the image.
COPY docker/orionintel/alembic.ini /app/models/db_schemes/minirag/alembic.ini

# entrypoint runs migrations, then hands off to the CMD (uvicorn)
COPY docker/orionintel/entrypoint.sh /entrypoint.sh

# /app/celerybeat is the mount point for the celery_beat_data volume. It must
# exist and be owned by appuser BEFORE the volume is attached: Docker copies the
# directory's ownership into a new named volume, and if the path is missing the
# volume is created root-owned and beat (running as appuser) can't write its
# schedule file.
RUN mkdir -p /app/assets/files /app/celerybeat \
    && chmod +x /entrypoint.sh \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
