# 8 — Flower: the Celery dashboard

> tut-017.

## 8.1 What it gives you

Flower is a read-only web UI over the same broker and result backend your code
uses. Until now, "is the queue healthy?" meant reading `docker compose logs` and
`rabbitmqctl list_queues`. Flower answers it in a browser:

| Tab | Shows |
|---|---|
| **Dashboard** | Every live worker, its concurrency, and processed/active/failed counts |
| **Tasks** | Task history — name, args, state, runtime, and the traceback on failure |
| **Broker** | Queue depth per queue: is anything backing up? |
| **Monitor** | Throughput and runtime charts |
| Worker detail | The worker's active/reserved tasks, registered task list, and live config |

It also exposes a small HTTP API (`/api/workers`, `/api/tasks`) that's convenient
for scripted checks.

Two things Flower is **not**:

* **Not a database.** `max_tasks` history lives in memory; restart Flower and it's
  gone. The durable records are Celery's results in Redis and the
  `celery_task_executions` table ([§5](./05-idempotency-and-task-records.md)).
* **Not authoritative about the past.** It only sees events from while it was
  running. A task that ran before Flower started won't appear.

## 8.2 The config — `src/flowerconfig.py`

```python
port = 5555
max_tasks = 10000
auto_refresh = True
basic_auth = [f"admin:{_setting('CELERY_FLOWER_PASSWORD', 'admin')}"]
```

| Setting | Meaning |
|---|---|
| `port` | 5555, Flower's convention |
| `max_tasks` | How many completed tasks to keep in memory. 10 000 is plenty; higher just costs RAM. |
| `auto_refresh` | The UI polls for updates instead of needing a manual reload |
| `basic_auth` | HTTP basic auth, `admin` plus `CELERY_FLOWER_PASSWORD` |

**Authentication is not optional here.** The Tasks tab shows every task's
arguments — project ids, file names, whatever you pass — and lets you revoke and
terminate tasks. An unauthenticated Flower on a public port is a control plane for
your queue.

### The environment-vs-file fix

```python
_file_config = dotenv_values(".env")

def _setting(name: str, default: str = "") -> str:
    return os.environ.get(name) or _file_config.get(name) or default
```

The reference does:

```python
config = dotenv_values(".env")
basic_auth = [f'admin:{config["CELERY_FLOWER_PASSWORD"]}']
```

That works when you run from `src/` with a `.env` file present. In Docker there
**is no** `.env` in the image — settings arrive as real environment variables via
compose `env_file:` — so `dotenv_values(".env")` returns `{}` and the subscript
raises `KeyError`, killing the container at startup. Reading the environment first
and falling back to the file makes one config work in both places.

Note this is a plain Python config file that Flower `exec`s — it isn't parsed by
pydantic, which is why it reads `os.environ` directly rather than going through
`helpers.config.Settings`.

## 8.3 The container — `docker/docker-compose.yml`

```yaml
  flower:
    build:
      context: ..
      dockerfile: docker/orionintel/Dockerfile
    container_name: orionintel_flower
    ports:
      - "5555:5555"
    depends_on:
      rabbitmq: {condition: service_healthy}
      redis:    {condition: service_healthy}
    env_file:
      - ./env/.env.app
    environment:
      - RUN_MIGRATIONS=0
    command: ["celery", "-A", "celery_app", "flower", "--conf=flowerconfig.py"]
```

* Same image again — Flower needs `-A celery_app` to discover the broker, the
  backend and the task names, so it has to be able to import your app.
* `RUN_MIGRATIONS=0`, same reason as beat and the worker
  ([§3.5](./03-docker-rabbitmq-redis.md)).
* `--conf=flowerconfig.py` is resolved relative to `WORKDIR /app`, where the
  source lives.
* No `pgvector` dependency — Flower never touches the application database.

The dependency in `src/pyproject.toml` is `flower>=2.0.1`, added with `uv add
flower`.

## 8.4 Using it

<http://localhost:5555> — user `admin`, password from `CELERY_FLOWER_PASSWORD`
in `docker/env/.env.app` (`orionintel_flower_2222` in the template).

Verified: no credentials returns **401**; with credentials the API reports the
worker and all three of its queues:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5555/
# 401

curl -s -u admin:orionintel_flower_2222 "http://localhost:5555/api/workers?refresh=1"
# {"celery@374cb84be57b": {"active_queues": [
#     {"name": "file_processing", ...}, {"name": "data_indexing", ...},
#     {"name": "default", ...}], ...}}
```

Useful checks once you're in:

* **Broker tab** — if `file_processing` shows a growing depth while
  `data_indexing` is empty, your bottleneck is chunking, not embedding.
* **Tasks tab, filtered to FAILURE** — the traceback is right there, no log
  grepping.
* Follow a chain: search the launcher id, read `workflow_id` out of its result,
  then search that ([§6.6](./06-workflows-and-chains.md)).

## 8.5 Expected startup noise

For the first few seconds Flower logs:

```
[W inspector:44] Inspect method conf failed
[W inspector:44] Inspect method registered failed
[W inspector:44] Inspect method active_queues failed
...
```

Flower starts before the worker finishes booting and its inspect broadcasts get
no reply. They stop once a worker answers. Warnings that **persist** mean
something real: no worker running, or Flower pointed at a different broker than
the worker.

## 8.6 Flower vs. the RabbitMQ UI

Both are running; they answer different questions.

| | Flower (:5555) | RabbitMQ management (:15672) |
|---|---|---|
| Perspective | Celery tasks | AMQP messages, queues, exchanges |
| Best for | which task failed and why; per-worker throughput | is a queue backing up; does it have consumers; connection health |
| Sees task names | yes | no — messages are opaque payloads |
| Survives restart | no (in-memory) | yes (broker state is in `rabbitmq_data`) |

Rule of thumb: **Flower for tasks, RabbitMQ for plumbing.** "Which task raised
that exception" is Flower. "Why is nothing being consumed" is RabbitMQ — a queue
with `consumers = 0` is a missing entry in the worker's `-Q` list.

**Back to:** [README](./README.md) · **Run everything:** [04 — Run & verify](./04-run-and-verify.md)
