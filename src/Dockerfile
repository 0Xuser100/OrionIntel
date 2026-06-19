# ---------- builder ----------
FROM python:3.12-slim AS builder

# bring in the uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# install dependencies first (this layer is cached unless lock/manifest change)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# ---------- runtime ----------
FROM python:3.12-slim

WORKDIR /app

# run as a non-root user
RUN useradd -m -u 1000 appuser

# copy the prebuilt virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# copy the application source
COPY . /app

# ensure the uploaded-files dir exists and is owned by the app user
RUN mkdir -p /app/assets/files && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
