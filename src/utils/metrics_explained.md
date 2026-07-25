# `utils/metrics.py` — Detailed Explanation

This file adds **Prometheus monitoring** to your FastAPI app. It measures two things for every HTTP request:

1. **How many requests** you get (a counter).
2. **How long each request takes** (a latency histogram).

It then exposes those numbers at a secret URL so a Prometheus server can "scrape" (read) them.

---

## The full file, line by line

```python
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time
```

### The imports

| Import | What it is | Why it's here |
|---|---|---|
| `Counter` | A number that **only goes up** (0 → 1 → 2 …). | Count total requests. |
| `Histogram` | Buckets measurements (e.g. request durations) into ranges + tracks sum & count. | Measure request latency. |
| `generate_latest` | Serializes all your metrics into the plain-text format Prometheus understands. | Build the `/metrics` response body. |
| `CONTENT_TYPE_LATEST` | The exact MIME type string Prometheus expects (`text/plain; version=0.0.4`). | Set the response `Content-Type`. |
| `Request`, `Response` | FastAPI/Starlette request & response objects. | Read method/path, return the metrics text. |
| `BaseHTTPMiddleware` | Base class for middleware that wraps every request. | Hook into every request to time it. |
| `time` | Standard library clock. | Measure elapsed seconds. |

> **Middleware** = code that runs *around* every request: it sees the request on the way in and the response on the way out. Perfect place to start a timer before and stop it after.

---

## Defining the metrics

```python
REQUEST_COUNT = Counter(
    'http_requests_total',                 # metric name (shown in Prometheus)
    'Total HTTP Requests',                 # human description
    ['method', 'endpoint', 'status']       # labels (dimensions you can filter by)
)

REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP Request Latency',
    ['method', 'endpoint']
)
```

### What are "labels"?

Labels let you slice one metric into many. Instead of a single "total requests" number, you get a separate count for **each combination** of method + endpoint + status:

```
http_requests_total{method="GET",  endpoint="/api/data", status="200"}  = 1500
http_requests_total{method="POST", endpoint="/api/data", status="500"}  =   12
http_requests_total{method="GET",  endpoint="/api/nlp",  status="200"}  =  340
```

So later you can ask Prometheus things like *"how many 500 errors on POST /api/data?"* — that's the `12`.

> ⚠️ **Why these are defined at module level (top of the file, not inside a function):** Prometheus metrics must be created **once** for the whole process. If you created a `Counter` with the same name twice, `prometheus_client` raises a "Duplicated timeseries" error. Module-level = created a single time when Python first imports the file.

### Counter vs Histogram

- **`Counter`** — a value that only increases. You call `.inc()` to add 1. Used for *"how many times did X happen?"*
- **`Histogram`** — records a distribution of values. You call `.observe(value)`. It automatically tracks:
  - `_count` — how many observations,
  - `_sum` — total of all values,
  - `_bucket` — how many observations fell under each threshold (≤0.1s, ≤0.5s, ≤1s, …).

  From that you can compute averages and **percentiles** (e.g. "95% of requests finish in under 200ms").

---

## The middleware — timing every request

```python
class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):

        start_time = time.time()               # 1. start the stopwatch

        response = await call_next(request)    # 2. run the actual route handler

        duration = time.time() - start_time    # 3. stop the stopwatch
        endpoint = request.url.path            #    e.g. "/api/data"

        REQUEST_LATENCY.labels(
            method=request.method, endpoint=endpoint
        ).observe(duration)                    # 4. record how long it took

        REQUEST_COUNT.labels(
            method=request.method, endpoint=endpoint, status=response.status_code
        ).inc()                                # 5. add 1 to the request count

        return response                        # 6. give the response back to the client
```

### Step by step, using a real request

Say a browser sends **`GET /api/data`** and it succeeds in 0.05 seconds:

1. `start_time` is recorded (e.g. `1700000000.000`).
2. `call_next(request)` runs your actual endpoint and returns a `200` response.
3. `duration = 0.05` seconds; `endpoint = "/api/data"`.
4. `REQUEST_LATENCY.labels(method="GET", endpoint="/api/data").observe(0.05)`
   → records "a GET /api/data took 0.05s".
5. `REQUEST_COUNT.labels(method="GET", endpoint="/api/data", status=200).inc()`
   → bumps that specific counter from, say, 1499 → 1500.
6. The response is returned unchanged — the client never knows metrics were recorded.

> `.labels(...)` picks (or creates) the specific labelled series; `.observe()` / `.inc()` then update it. The middleware itself changes nothing about the response — it only **watches**.

---

## Exposing the metrics — `setup_metrics`

```python
def setup_metrics(app: FastAPI):
    """
    Setup Prometheus metrics middleware and endpoint
    """
    app.add_middleware(PrometheusMiddleware)   # 1. attach the timer to every request

    @app.get("/TrhBVe_m5gg2002_E5VVqS", include_in_schema=False)
    def metrics():                             # 2. an endpoint that dumps the numbers
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

This is the function you call from `main.py`:

```python
app = FastAPI(lifespan=lifespan)
setup_metrics(app)
```

It does **two** things:

### 1. `app.add_middleware(PrometheusMiddleware)`
Registers the middleware so it wraps *every* incoming request. From now on, every request is timed and counted.

### 2. The `/metrics` endpoint (with a weird name)
```python
@app.get("/TrhBVe_m5gg2002_E5VVqS", include_in_schema=False)
```
- `generate_latest()` renders **all** current metric values into Prometheus text format.
- `Response(..., media_type=CONTENT_TYPE_LATEST)` returns it with the header Prometheus expects.
- `include_in_schema=False` **hides this route** from your `/docs` (Swagger) and `/openapi.json`, so it doesn't clutter your public API docs.

**Why the random URL `/TrhBVe_m5gg2002_E5VVqS` instead of the usual `/metrics`?**
It's **security through obscurity**. Metrics can leak internal info (which endpoints exist, error rates, traffic volume). By using an unguessable path, a random visitor hitting `/metrics` gets a `404` and never sees your monitoring data. Only your Prometheus server (configured with the secret path) can scrape it.

> Note: this is *obscurity*, not real security. For production, prefer putting `/metrics` behind network rules / auth. But the obscure path is a cheap extra layer.

---

## What the scraped output actually looks like

If you (or Prometheus) `GET /TrhBVe_m5gg2002_E5VVqS`, you get plain text like:

```text
# HELP http_requests_total Total HTTP Requests
# TYPE http_requests_total counter
http_requests_total{method="GET",endpoint="/api/data",status="200"} 1500.0
http_requests_total{method="POST",endpoint="/api/nlp",status="200"} 87.0

# HELP http_request_duration_seconds HTTP Request Latency
# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{method="GET",endpoint="/api/data",le="0.005"} 200.0
http_request_duration_seconds_bucket{method="GET",endpoint="/api/data",le="0.01"}  650.0
http_request_duration_seconds_bucket{method="GET",endpoint="/api/data",le="0.025"} 1400.0
http_request_duration_seconds_bucket{method="GET",endpoint="/api/data",le="+Inf"}  1500.0
http_request_duration_seconds_sum{method="GET",endpoint="/api/data"}   45.2
http_request_duration_seconds_count{method="GET",endpoint="/api/data"} 1500.0
```

- `le="0.01"} 650` means **650** GET /api/data requests finished in ≤ 0.01s.
- `_sum / _count` = `45.2 / 1500` ≈ **0.03s average** latency.

Prometheus scrapes this every ~15s, stores it as time-series, and you graph it in **Grafana**.

---

## How the whole thing fits together

```
                Browser / client
                       │  GET /api/data
                       ▼
        ┌──────────────────────────────┐
        │   PrometheusMiddleware        │  ⏱ start timer
        │      (dispatch)               │
        │        │                      │
        │        ▼                      │
        │   your real endpoint          │  runs, returns 200
        │        │                      │
        │        ▼                      │
        │   record duration + count     │  ⏱ stop timer, .observe()/.inc()
        └──────────────┬───────────────┘
                       │ response
                       ▼
                Browser / client


   Prometheus server ──GET /TrhBVe_m5gg2002_E5VVqS──▶ metrics() ──▶ generate_latest()
                                                                    (dumps all numbers)
```

---

## Minimal end-to-end example you can run

```python
# app.py
from fastapi import FastAPI
from utils.metrics import setup_metrics

app = FastAPI()
setup_metrics(app)

@app.get("/hello")
def hello():
    return {"msg": "hi"}
```

```bash
uvicorn app:app --reload

# hit the endpoint a few times
curl http://localhost:8000/hello
curl http://localhost:8000/hello

# now look at the metrics
curl http://localhost:8000/TrhBVe_m5gg2002_E5VVqS
```

You'll see `http_requests_total{...endpoint="/hello"...} 2.0` and latency buckets for it.

---

## Quick reference / gotchas

| Thing | Why it matters |
|---|---|
| Metrics defined at **module level** | Created once per process; avoids "duplicated timeseries" errors. |
| `.labels(...)` before `.inc()`/`.observe()` | Selects the specific labelled series first, then updates it. |
| **High-cardinality labels are dangerous** | `endpoint = request.url.path` is fine for fixed routes, but if paths contain IDs (`/user/123`, `/user/456`), each unique path becomes a new series → memory blowup. Consider using the *route pattern* (`/user/{id}`) instead of raw path. |
| `include_in_schema=False` | Keeps the metrics route out of `/docs` and OpenAPI. |
| Obscure URL | Security-by-obscurity so randoms can't read your metrics; not a substitute for real auth/network controls. |
| Middleware only **observes** | It never modifies the response; safe to add/remove. |
