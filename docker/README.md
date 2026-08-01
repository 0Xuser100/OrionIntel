# OrionIntel — Docker (Deploy Stack)

This `docker/` folder holds the **deployment** stack (full app + monitoring).
A separate **local dev** stack lives in [`local/`](./local/) and is unchanged.

| Folder | Purpose | Run from |
|---|---|---|
| `docker/` (this) | Deploy: app + celery worker/beat/flower + nginx + Postgres + Qdrant + RabbitMQ + Redis + Prometheus + Grafana + exporters | `cd docker` |
| `docker/local/` | Local dev: app + celery worker/beat/flower + mongodb + Postgres + Qdrant + RabbitMQ + Redis (no monitoring) | `cd docker/local` |

The RabbitMQ / Redis / celery worker services are explained parameter by
parameter in **[../docs/celery/03-docker-rabbitmq-redis.md](../docs/celery/03-docker-rabbitmq-redis.md)**.

## Services (deploy)

| Service | Image | Port | Role |
|---|---|---|---|
| `fastapi` | built from `orionintel/Dockerfile` | 8000 | The OrionIntel API |
| `celery_worker` | same image as `fastapi` | — | Runs background tasks (chunking, indexing, cleanup) |
| `celery_beat` | same image as `fastapi` | — | Publishes scheduled tasks on an interval (run only ONE) |
| `flower` | same image as `fastapi` | 5555 | Celery web dashboard |
| `rabbitmq` | rabbitmq:4.1.2-management | 5672/15672 | Celery broker (the task queue) + management UI |
| `redis` | redis:8.0.3-alpine | 6379 | Celery result backend (task states) |
| `nginx` | nginx:stable-alpine | 80 | Reverse proxy in front of the API |
| `pgvector` | pgvector/pgvector:pg17 | 5432 | PostgreSQL (projects/assets/chunks) |
| `qdrant` | qdrant:v1.13.6 | 6333/6334 | Vector database |
| `prometheus` | prom/prometheus | 9090 | Collects & stores metrics |
| `grafana` | grafana/grafana | 3000 | Dashboards |
| `node-exporter` | prom/node-exporter | 9100 | Host CPU/RAM/disk metrics |
| `postgres-exporter` | postgres-exporter | 9187 | PostgreSQL metrics |

MongoDB is intentionally **not** in this stack — the app doesn't use it.

## 1. Create the env files from the examples

```bash
cd docker/env
cp .env.example.app               .env.app
cp .env.example.postgres          .env.postgres
cp .env.example.grafana           .env.grafana
cp .env.example.postgres-exporter .env.postgres-exporter
cp .env.example.rabbitmq          .env.rabbitmq
cp .env.example.redis             .env.redis

cd ..
cp .env.example .env   # compose-level file: holds REDIS_PASSWORD for ${REDIS_PASSWORD}
```

`docker/.env` is separate on purpose: `docker compose` reads it for `${VAR}`
interpolation inside `docker-compose.yml` (the redis `--requirepass` flag), and
`env_file:` entries are *not* visible to that interpolation. Keep `REDIS_PASSWORD`
identical in `docker/.env`, `env/.env.redis`, and `CELERY_RESULT_BACKEND` in
`env/.env.app`.

Then edit `.env.app` and add your real `OPENAI_API_KEY` / `COHERE_API_KEY`.
Keep the Postgres user/password/db **identical** across `.env.app`,
`.env.postgres`, `.env.postgres-exporter`, and `orionintel/alembic.ini`, and the
RabbitMQ/Redis credentials identical across `.env.rabbitmq`, `.env.redis`,
`../.env` and the `CELERY_*` block of `.env.app`.

## 2. Create the deploy Alembic config

```bash
cd docker/orionintel
cp alembic.example.ini alembic.ini
```

(Its `sqlalchemy.url` already points at `pgvector:5432` with the example
credentials — change it only if you changed the Postgres user/password/db.)

## 3. Start

```bash
cd docker
docker compose up --build -d
```

Migrations (`alembic upgrade head`) run automatically on the `fastapi` container,
then uvicorn boots. The `celery_worker`, `celery_beat` and `flower` containers run
the same image with `RUN_MIGRATIONS=0` so they don't race on `alembic_version`.

## 4. Access

| What | URL | Login |
|---|---|---|
| API | http://localhost:8000 | — |
| API docs | http://localhost:8000/docs | — |
| Via nginx | http://localhost | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin_password |
| Qdrant UI | http://localhost:6333/dashboard | — |
| RabbitMQ UI | http://localhost:15672 | orionintel_user / orionintel_rabbitmq_2222 |
| Flower (Celery) | http://localhost:5555 | admin / orionintel_flower_2222 |

## Grafana dashboards to import

- FastAPI observability: https://grafana.com/grafana/dashboards/18739
- Node exporter full: https://grafana.com/grafana/dashboards/1860
- Qdrant: https://grafana.com/grafana/dashboards/23033
- PostgreSQL exporter: https://grafana.com/grafana/dashboards/12485

Add Prometheus as a data source in Grafana with URL `http://prometheus:9090`.

## Tear down

```bash
docker compose down            # stop, keep data
docker compose down -v         # stop and DELETE all volumes (fresh start)
```
