# The Deploy `docker-compose.yml` — Explained

This document explains **every service** in the deploy stack, **how they connect**,
**why migrations run on startup**, and **why Prometheus matters**. Read it top to
bottom the first time; use it as a reference afterward.

---

## 1. The big picture (architecture diagram)

```mermaid
flowchart TD
    subgraph host["Your machine / server"]
        user([Browser / API client])
    end

    user -->|":80"| nginx["nginx<br/>reverse proxy"]
    user -.->|":8000 direct"| fastapi

    subgraph net["docker network: backend"]
        nginx -->|"http://fastapi:8000"| fastapi["fastapi<br/>OrionIntel API"]

        fastapi -->|"SQL :5432<br/>projects/assets/chunks"| pg[("pgvector<br/>PostgreSQL")]
        fastapi -->|"vectors :6333<br/>embeddings/search"| qdrant[("qdrant<br/>vector DB")]

        prometheus["prometheus<br/>scrape + store"] -->|"pull /metrics"| fastapi
        prometheus -->|"pull :9100"| node["node-exporter<br/>host CPU/RAM/disk"]
        prometheus -->|"pull :9187"| pgexp["postgres-exporter"]
        prometheus -->|"pull /metrics"| qdrant
        pgexp -->|"reads stats :5432"| pg

        grafana["grafana<br/>dashboards"] -->|"query :9090"| prometheus
    end

    admin([You]) -->|":3000"| grafana
    admin -.->|":9090"| prometheus
```

**Two planes, side by side:**

- **App plane** (blue path): client → nginx → fastapi → Postgres + Qdrant. This is
  what actually serves RAG requests.
- **Monitoring plane** (Prometheus/Grafana): sits *beside* the app, watching it.
  It never handles user traffic — it only observes.

Plain-text version of the same idea:

```
            ┌────────── APP PLANE (serves requests) ──────────┐
 client ──▶ nginx :80 ──▶ fastapi :8000 ──▶ pgvector :5432 (SQL: projects/assets/chunks)
                                        └──▶ qdrant   :6333 (vectors: embeddings/search)

            ┌────────── MONITORING PLANE (watches) ───────────┐
 prometheus :9090  ──pull every 15s──▶  fastapi          (/TrhBVe... request counts + latency)
                   ──pull every 15s──▶  node-exporter    (host CPU/RAM/disk)
                   ──pull every 15s──▶  postgres-exporter (DB connections/queries)
                   ──pull every 15s──▶  qdrant           (/metrics)
 grafana :3000  ──queries──▶  prometheus  ──▶  graphs & dashboards for you
```

---

## 2. How services find each other

Every service joins one Docker network: **`backend`**. On that network, the
**service name is the hostname**. So the app connects to Postgres at `pgvector:5432`,
Prometheus scrapes the app at `fastapi:8000`, and Grafana queries `prometheus:9090`.

- **`host:container` ports** (e.g. `"8000:8000"`) expose a container to *your machine*.
- **Service-name:port** (e.g. `pgvector:5432`) is how containers reach *each other*
  on the internal network — no published port needed.

This is why the app env uses `POSTGRES_HOST=pgvector` and `POSTGRES_PORT=5432`
(internal), even though on the host you'd reach the same DB at `localhost:5432`.

---

## 3. Service-by-service walkthrough

### `fastapi` — the application
```yaml
build:
  context: ..                              # repo ROOT (so it can copy src/ AND docker/orionintel/)
  dockerfile: docker/orionintel/Dockerfile
depends_on:
  pgvector: { condition: service_healthy } # don't start until Postgres accepts connections
env_file: [ ./env/.env.app ]               # all app settings (DB creds, LLM keys, vector URL)
volumes: [ fastapi_data:/app/assets ]      # uploaded files survive container restarts
```
- **`context: ..`** — the build context is the whole repo, not just `src/`, because
  the Dockerfile needs both your code (`src/`) *and* the deploy entrypoint/alembic
  config (`docker/orionintel/`).
- **`depends_on … service_healthy`** — Compose waits for Postgres's healthcheck to
  pass before starting the app, avoiding "connection refused" on boot.

### `nginx` — reverse proxy
```yaml
image: nginx:stable-alpine3.20-perl
ports: [ "80:80" ]
volumes: [ ./nginx/default.conf:/etc/nginx/conf.d/default.conf ]
```
Sits in front of the app on port 80. Forwards `/` to `http://fastapi:8000`. In
production this is where you'd add TLS, rate limiting, caching, etc. Users hit
**one** stable port (80) instead of the app port directly.

### `pgvector` — PostgreSQL (the relational database)
```yaml
image: pgvector/pgvector:0.8.0-pg17
env_file: [ ./env/.env.postgres ]
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
volumes: [ pgvector_data:/var/lib/postgresql/data ]
```
- Stores your **structured** data: projects, assets, chunks (via SQLAlchemy).
- The `pgvector` image is normal Postgres **plus** the `vector` extension — so it
  *could* also store embeddings, but in this stack Qdrant handles vectors.
- **`$$POSTGRES_USER`** — the doubled `$` tells Compose *not* to expand the variable;
  the `$` is passed literally so the **shell inside the container** expands it (where
  `POSTGRES_USER` exists, loaded from `.env.postgres`).
- **`healthcheck`** — `pg_isready` returns success only when Postgres accepts
  connections; that's what `depends_on: service_healthy` waits on.

### `qdrant` — vector database
```yaml
image: qdrant/qdrant:v1.13.6
ports: [ "6333:6333", "6334:6334" ]   # 6333 REST+dashboard+/metrics, 6334 gRPC
volumes: [ qdrant_data:/qdrant/storage ]
```
Stores the **embeddings** and does similarity search for retrieval. The app points
at it via `VECTOR_DB_URL=http://qdrant:6333`. Handily, Qdrant exposes its own
Prometheus `/metrics`, so we scrape it too.

### `prometheus` — the metrics brain
```yaml
image: prom/prometheus:v3.3.0
volumes:
  - prometheus_data:/prometheus                       # its time-series database
  - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml   # what to scrape
command: [ '--config.file=…', '--storage.tsdb.path=/prometheus', '--web.enable-lifecycle' ]
```
Reads `prometheus.yml`, then every 15s **pulls** `/metrics` from each target and
stores the numbers with timestamps. `--web.enable-lifecycle` lets you reload its
config with an HTTP call instead of a restart. (More on why it matters in §5.)

### `grafana` — dashboards
```yaml
image: grafana/grafana:11.6.0-ubuntu
env_file: [ ./env/.env.grafana ]    # admin user/password
depends_on: [ prometheus ]
```
The pretty face on top of Prometheus. You add Prometheus (`http://prometheus:9090`)
as a data source, import a dashboard, and get live graphs of latency, error rate,
CPU, DB connections, etc.

### `node-exporter` — host metrics
```yaml
image: prom/node-exporter:v1.9.1
volumes: [ /proc:/host/proc:ro, /sys:/host/sys:ro, /:/rootfs:ro ]
```
Reads the host's `/proc` and `/sys` (read-only) and turns them into metrics: CPU
load, memory, disk space, network. This answers *"is the machine itself healthy?"*

### `postgres-exporter` — database metrics
```yaml
image: prometheuscommunity/postgres-exporter:v0.17.1
env_file: [ ./env/.env.postgres-exporter ]
```
Connects to Postgres and exposes its internals as metrics: active connections,
transactions/sec, cache hit ratio, slow queries. Prometheus scrapes it at `:9187`.

### `networks` and `volumes`
```yaml
networks: { backend: { driver: bridge } }   # one private network for all services
volumes:  { fastapi_data:, pgvector_data:, qdrant_data:, prometheus_data:, grafana_data: }
```
**Named volumes** persist data across `docker compose down`/`up`. Without them, your
database and metrics history would vanish every time a container is recreated.

---

## 4. How migrations run automatically (the entrypoint)

The deploy image (`orionintel/Dockerfile`) uses an **entrypoint** so the database
schema is created/updated *before* the app serves traffic:

```
ENTRYPOINT ["/entrypoint.sh"]      # runs migrations, then...
CMD ["uvicorn", "main:app", ...]   # ...this is passed to entrypoint as "$@"
```

`entrypoint.sh` does:
```bash
cd /app/models/db_schemes/minirag/
alembic upgrade head     # 1) create/upgrade tables
exec "$@"                # 2) become uvicorn (replaces the shell as PID 1)
```

- **Why `alembic.ini` is baked into the image:** Alembic's `env.py` reads the DB URL
  from `alembic.ini` (via `engine_from_config`), *not* from environment variables.
  So the deploy image ships its own `alembic.ini` pointing at `pgvector:5432`.
- **Why `exec "$@"` matters:** without it, the shell would finish after migrations
  and the container would exit — uvicorn would never start. (mini-rag's entrypoint
  omits this line; ours fixes it.)

---

## 5. Why Prometheus matters (the point of the whole monitoring plane)

Your app already *produces* metrics (`src/utils/metrics.py` counts requests and
times them). But producing numbers is useless if nobody **collects, stores, and
watches** them. That's Prometheus's job — and it's what turns a black box into an
observable system.

### What you gain

1. **History, not just "now."**
   `/metrics` only shows the *current* counters. Prometheus scrapes every 15s and
   keeps a **timeline**, so you can ask *"what did latency look like at 2am last
   night?"* — impossible with the raw endpoint alone.

2. **Answers to real operational questions (via PromQL):**
   - Requests per second: `rate(http_requests_total[1m])`
   - Error rate: `rate(http_requests_total{status=~"5.."}[5m])`
   - p95 latency: `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))`

3. **One place, every layer.** App latency (fastapi), machine health
   (node-exporter), database load (postgres-exporter), and vector DB (qdrant) all
   land in the *same* system — so when the app is slow you can immediately see
   whether it's the code, the CPU, or the database.

4. **Alerting.** Prometheus can fire alerts ("error rate > 5% for 5 min",
   "disk > 90%") so you find out **before** users complain.

5. **Dashboards.** Grafana reads Prometheus and draws the graphs your team actually
   looks at.

### Where it fits vs. your app's metrics.py

```
 src/utils/metrics.py   ──produces──▶   /TrhBVe...  (raw current numbers)
        (counts + times each request)        │
                                              │  Prometheus PULLS every 15s
                                              ▼
                           Prometheus  ──stores timeline + runs PromQL + alerts──▶  Grafana graphs
```

### What Prometheus does *not* do
- It doesn't make the app faster — it **measures**, so *you* can fix things.
- It stores **numbers/aggregates**, not the text of prompts or responses. For
  *"why did this RAG answer come out wrong?"* you need LLM tracing (e.g. Langfuse),
  which is a different tool. Prometheus answers *"is it fast/healthy?"*, Langfuse
  answers *"is the answer good?"*.

---

## 6. Local vs deploy — quick contrast

| | `local/` (dev) | `docker/` (deploy) |
|---|---|---|
| App image | `src/Dockerfile` (uv, no migrations) | `orionintel/Dockerfile` (uv **+ migrations on start**) |
| MongoDB | present (unused) | removed |
| Reverse proxy | none | nginx |
| Monitoring | none | Prometheus + Grafana + node/postgres exporters |
| Env files | single `../../src/.env` + `local/.env` | split `env/.env.app`, `.env.postgres`, `.env.grafana`, `.env.postgres-exporter` |
| Postgres host port | 5433 | 5432 |
| Intended use | fast iteration on your machine | production-shaped run |

---

## 7. Env-file relationships (keep these in sync!)

The **same Postgres credentials** appear in four places and must match exactly,
or migrations / the app / the exporter will fail to connect:

```
env/.env.postgres            POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
        │  must equal
env/.env.app                 POSTGRES_USERNAME / POSTGRES_PASSWORD / POSTGRES_MAIN_DATABASE
        │  must equal
env/.env.postgres-exporter   DATA_SOURCE_USER / DATA_SOURCE_PASS  (+ DATA_SOURCE_URI db name)
        │  must equal
orionintel/alembic.ini       sqlalchemy.url = postgresql+psycopg2://USER:PASS@pgvector:5432/DB
```

> Note the different variable *names* for the same value: the Postgres image wants
> `POSTGRES_USER`, but your app's `config.py` wants `POSTGRES_USERNAME`. Same
> credential, different key — a classic source of "why won't it connect?".
