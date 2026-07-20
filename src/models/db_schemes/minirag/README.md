# Alembic Migrations (MiniRag / PostgreSQL)

This directory holds the SQLAlchemy schemes (`schemes/`) and the Alembic
migration environment (`alembic/`) for the PostgreSQL database.

> The Alembic environment was created once with `uv run alembic init alembic`
> — you do NOT need to run that again.

## 1. Configuration (first time only)

```bash
cd src/models/db_schemes/minirag
cp alembic.ini.example alembic.ini
```

Update `sqlalchemy.url` in `alembic.ini` with your database credentials:

```ini
# Sync driver (psycopg2) — Alembic runs migrations synchronously.
# NOTE: "%" must be doubled in .ini files, so "@" in a password -> "%%40".
sqlalchemy.url = postgresql+psycopg2://username:password@localhost:5433/database
```

- Run from host: `localhost:5433` (port published by docker-compose).
- Run inside Docker: `pgvector:5432` (compose service name + internal port).
- Credentials must match `docker/.env` (`POSTGRES_USER` / `POSTGRES_PASSWORD`).

`alembic.ini` contains real credentials and is gitignored — never commit it.

## 2. Create a new migration

Whenever you add or change models in `schemes/`:

```bash
cd src/models/db_schemes/minirag
uv run alembic revision --autogenerate -m "create projects, assets, chunks tables"
```

Autogenerate compares `schemes/` (via `target_metadata = SQLAlchemyBase.metadata`
in `alembic/env.py`) against the live database and writes the migration script
to `alembic/versions/`. Always review the generated file before applying it.

## 3. Apply migrations

```bash
uv run alembic upgrade head
```

## Useful commands

```bash
uv run alembic current      # show the revision applied to the database
uv run alembic history      # list all migrations
uv run alembic check        # fails if models have changes without a migration
uv run alembic downgrade -1 # roll back the last migration
```
