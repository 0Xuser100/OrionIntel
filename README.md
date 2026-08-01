# OrionIntel
![OrionIntel logo](project-logo.png)
AI-powered RAG platform for analyzing company files, finance reports, and books.

## Setup
Install `uv`, then run `uv sync`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Alternatively, you can use `pip`:

```bash
pip install uv
```

Then install dependencies:

```bash
uv sync
```

### Activate the virtual environment (Windows)
```cmd
.venv\Scripts\activate
```
### Setup the environment variables
```bash
$ cp .env.example .env
```
Set your environment variables in the `.env` file. Like `OPENAI_API_KEY` value.

## Running the Project

To run the project in development mode, use the following command:

```bash
uv run fastapi dev main.py
```

To run on a specific port (e.g., 7070):

```bash
uv run fastapi dev main.py --port 7070
```
## Run with Docker (fully containerized)

The whole stack — **app + MongoDB + PostgreSQL/pgvector + Qdrant** — runs in
Docker. The app talks to the other services by their compose service names over a
private network; all state is kept in named volumes. The vector store is
selectable via `VECTOR_DB_BACKEND` (`PGVECTOR` or `QDRANT`).

### 1. Configure environment

```bash
# Service credentials for the containers (Mongo + Postgres)
$ cd docker
$ cp .env.example .env        # set MONGO_INITDB_ROOT_* and POSTGRES_USER/PASSWORD/DB

# App settings
$ cd ../src
$ cp .env.example .env
```

In `src/.env`, set the Docker-internal addresses and pick a vector backend:

```ini
MONGODB_URL="mongodb://<user>:<pass>@mongodb:27017"   # service name + internal port

# --- vector store selection ---
VECTOR_DB_BACKEND="PGVECTOR"                          # or "QDRANT"

# PostgreSQL / pgvector (used when VECTOR_DB_BACKEND=PGVECTOR)
POSTGRES_USERNAME="<user>"                            # must match docker/.env POSTGRES_USER
POSTGRES_PASSWORD="<pass>"                            # must match docker/.env POSTGRES_PASSWORD
POSTGRES_HOST="pgvector"                              # service name (in Docker)
POSTGRES_PORT=5432                                    # internal port
POSTGRES_MAIN_DATABASE="<db>"                         # must match docker/.env POSTGRES_DB
EMBEDDING_MODEL_SIZE=1536                             # must match your embedding model's dimension

# Qdrant (used when VECTOR_DB_BACKEND=QDRANT)
VECTOR_DB_URL="http://qdrant:6333"                    # connect to the qdrant container
```

The credentials in `MONGODB_URL` and the `POSTGRES_*` values must match `docker/.env`.

### 2. Build and run

```bash
$ cd docker
$ docker compose up --build        # add -d to run in the background
```

> Rebuild with `--build` whenever `pyproject.toml`/`uv.lock` change (dependencies
> are baked into the image at build time).

### 3. Apply database migrations (required for PGVECTOR)

The relational tables (`projects`, `assets`, `chunks`) are created by Alembic and
are **not** created automatically. With the containers running, apply migrations
from the **host** (the bundled `alembic.ini` points at `localhost:5433`, the
host→pgvector port mapping):

```bash
$ cd src/models/db_schemes/minirag
$ uv run alembic upgrade head        # then `uv run alembic check` → "No new upgrade operations detected."
```

App → http://localhost:8000/docs

### Notes
- **Backend selection:** `VECTOR_DB_BACKEND=PGVECTOR` stores vectors in Postgres
  (pgvector); `QDRANT` uses the Qdrant container. For QDRANT, `VECTOR_DB_URL` set →
  server mode; leave it empty for **embedded** Qdrant (local, non-Docker dev).
- **Migrations only matter for PGVECTOR** — Qdrant creates its collections on demand.
- Persisted data lives in the `mongodata`, `pgvector_data`, `qdrantdata`, and
  `app_files` volumes.
- Studio 3T still connects from your host at `localhost:27007`; Postgres is exposed
  on `localhost:5433`.

See `docs/docker-changes-and-run.md` for the full design and what changed.

## Background tasks (Celery)

File ingestion and vector indexing no longer run inside the HTTP request.
`POST /api/v1/data/process/{project_id}` publishes a message to **RabbitMQ**,
returns `202` with a `task_id`, and a **Celery worker** does the work; task state
is read back from **Redis** via `GET /api/v1/data/process/status/{task_id}`.

Also included: indexing on the queue, a `chain()` workflow that chunks **then**
indexes in one call, a Postgres-backed idempotency ledger, a **Celery Beat**
scheduled cleanup, and the **Flower** dashboard on `:5555`.

```bash
cd docker/env && cp .env.example.rabbitmq .env.rabbitmq && cp .env.example.redis .env.redis
cd .. && cp .env.example .env        # compose-level: REDIS_PASSWORD
docker compose up --build -d
docker compose logs -f celery_worker
```

| What | URL |
|---|---|
| Flower (Celery dashboard) | http://localhost:5555 — `admin` / `CELERY_FLOWER_PASSWORD` |
| RabbitMQ management | http://localhost:15672 |

### Async endpoints

| Endpoint | Returns |
|---|---|
| `POST /api/v1/data/process/{project_id}` | `202` + `task_id` — chunk the files |
| `GET  /api/v1/data/process/status/{task_id}` | task state / result / error |
| `POST /api/v1/data/process-and-push/{project_id}` | `202` + `workflow_task_id` — chunk **then** index |
| `POST /api/v1/nlp/index/push/{project_id}` | `202` + `task_id` — vector indexing |
| `GET  /api/v1/nlp/index/push/status/{task_id}` | indexing state, incl. progress |

Full documentation in [`docs/celery/`](./docs/celery/):

| Document | Covers |
|---|---|
| [README](./docs/celery/README.md) | What changed, file by file, and what was merged from `mini-rag` `tut-016` + `tut-017` |
| [01 — Celery basics](./docs/celery/01-celery-basics.md) | Broker vs. result backend, queues, task lifecycle, every config key |
| [02 — FastAPI integration](./docs/celery/02-fastapi-celery-integration.md) | How API and worker share the code, line by line |
| [03 — RabbitMQ & Redis in Docker](./docs/celery/03-docker-rabbitmq-redis.md) | Every compose service and env parameter |
| [04 — Run & verify](./docs/celery/04-run-and-verify.md) | Commands, expected output, troubleshooting |
| [05 — Idempotency](./docs/celery/05-idempotency-and-task-records.md) | The `celery_task_executions` ledger and duplicate suppression |
| [06 — Workflows & chains](./docs/celery/06-workflows-and-chains.md) | Indexing on the queue; `chain()` |
| [07 — Celery Beat](./docs/celery/07-celery-beat-scheduled-cleanup.md) | The scheduled cleanup and its two retention numbers |
| [08 — Flower](./docs/celery/08-flower-dashboard.md) | The dashboard, its auth, and Flower vs. the RabbitMQ UI |

## Linting and Code Cleaning

### Ruff (Linting)
To install Ruff:
```bash
uv tool install ruff@latest
```

To run the check:
```bash
uv run ruff check
```

To format code:
```bash
uv run ruff format
```

### Autoflake (Removing Unused Imports)
To add autoflake to the project:
```bash
uv add autoflake
```

To remove unused imports:
```bash
uv run autoflake --in-place --recursive --remove-all-unused-imports .
```

To remove autoflake from the project:
```bash
uv remove autoflake
```

### Black (Formatting)
```bash
uv run black .
```

### isort (Import Sorting)
```bash
uv run isort .
```

### Pre-commit hook
A `.pre-commit-config.yaml` runs a `python-quality` hook (autoflake → isort →
black) automatically on every commit. Enable it once per clone:

```bash
uv run pre-commit install
```

Run it against all files manually with:

```bash
uv run pre-commit run --all-files
```

## Docker Cleanup (Windows CMD)

If you need to wipe your Docker environment clean, use these commands in your Windows Command Prompt (CMD).

### Stop all running containers
```cmd
FOR /f "tokens=*" %i IN ('docker ps -aq') DO docker stop %i
```
*Stops every active container currently running on your system.*

### Remove all containers
```cmd
FOR /f "tokens=*" %i IN ('docker ps -aq') DO docker rm %i
```
*Deletes all containers (they must be stopped first).*

### Remove all images
```cmd
FOR /f "tokens=*" %i IN ('docker images -q') DO docker rmi %i
```
*Deletes all downloaded or built Docker images.*

### Remove all volumes
```cmd
FOR /f "tokens=*" %i IN ('docker volume ls -q') DO docker volume rm %i
```
*Deletes all persistent data volumes managed by Docker.*

### System Prune (Deep Clean)
```cmd
docker system prune --all
```
*A built-in Docker command that removes all unused containers, networks, and images (dangling and unreferenced) in one go.*
