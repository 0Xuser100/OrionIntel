# OrionIntel — Docker (Deploy Stack)

This `docker/` folder holds the **deployment** stack (full app + monitoring).
A separate **local dev** stack lives in [`local/`](./local/) and is unchanged.

| Folder | Purpose | Run from |
|---|---|---|
| `docker/` (this) | Deploy: app + nginx + Postgres + Qdrant + Prometheus + Grafana + exporters | `cd docker` |
| `docker/local/` | Local dev: app + mongodb + Postgres + Qdrant (no monitoring) | `cd docker/local` |

See **[docker-compose-explained.md](./docker-compose-explained.md)** for a full,
line-by-line explanation, an architecture diagram, and why Prometheus matters.

## Services (deploy)

| Service | Image | Port | Role |
|---|---|---|---|
| `fastapi` | built from `orionintel/Dockerfile` | 8000 | The OrionIntel API |
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
```

Then edit `.env.app` and add your real `OPENAI_API_KEY` / `COHERE_API_KEY`.
Keep the Postgres user/password/db **identical** across `.env.app`,
`.env.postgres`, `.env.postgres-exporter`, and `orionintel/alembic.ini`.

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

Migrations (`alembic upgrade head`) run automatically on container start,
then uvicorn boots.

## 4. Access

| What | URL | Login |
|---|---|---|
| API | http://localhost:8000 | — |
| API docs | http://localhost:8000/docs | — |
| Via nginx | http://localhost | — |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / admin_password |
| Qdrant UI | http://localhost:6333/dashboard | — |

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
