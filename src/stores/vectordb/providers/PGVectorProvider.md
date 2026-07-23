# PGVectorProvider — Function Reference

`PGVectorProvider` implements the `VectorDBInterface` on top of **PostgreSQL + the `pgvector` extension**. It stores document chunks and their embedding vectors in regular Postgres tables (one table per "collection") and runs similarity search using pgvector operators.

File: `src/stores/vectordb/providers/PGVectorProvider.py`

---

## Imports & class setup — lines 1–8

- **Lines 1–3** — Import the interface (`VectorDBInterface`) it must implement, and the enums used for table column names, distance methods, and index types.
- **Line 4** — `from loguru import logger` — project-wide logger (matches `QdrantDBProvider` and the LLM providers).
- **Line 6** — `RetrievedDocument` is the Pydantic schema returned by search.
- **Line 7** — `sql_text` wraps raw SQL strings so SQLAlchemy can execute them.
- **Line 8** — `json` is used to serialize the `metadata` dict into a JSONB column.

---

## `__init__` — lines 12–29

Constructor. Stores config and prepares helpers.

- **Line 15** — `self.db_client` — the SQLAlchemy async `sessionmaker` (a callable that opens a session).
- **Line 16** — `self.default_vector_size` — default embedding dimension.
- **Line 18** — `self.index_threshold` — minimum row count before a vector index is auto-created (default `100`).
- **Lines 20–23** — Translate the generic distance method (`COSINE`/`DOT`) into pgvector's specific operator name.
- **Line 25** — `self.pgvector_table_prefix` — prefix used to identify this provider's collection tables.
- **Line 28** — `self.logger = logger` — bind loguru.
- **Line 29** — `self.default_index_name` — a lambda that builds the index name as `<collection>_vector_idx`.

---

## `connect` — lines 32–38

Opens a session and runs `CREATE EXTENSION IF NOT EXISTS vector` (**line 36**) so pgvector is available. Committed on **line 38**. This is the one-time setup that must run before any vector column can be created.

---

## `disconnect` — lines 40–41

No-op. The engine/session lifecycle is owned by the app (`main.py` disposes the engine), so there is nothing per-provider to close.

---

## `is_collection_existed` — lines 43–52

Checks whether a table named `collection_name` exists.

- **Lines 48–49** — Query `pg_tables` for the given table name (parameterized to avoid SQL injection).
- **Line 50** — `scalar_one_or_none()` returns the row or `None`.
- **Line 52** — Returns the record (truthy if the table exists).

---

## `list_all_collections` — lines 54–62

Returns all collection tables.

- **Lines 58–59** — Select `tablename` from `pg_tables` where the name matches the provider prefix.
- **Line 60** — `scalars().all()` collects the names into a list.

---

## `get_collection_info` — lines 64–92

Returns metadata + row count for one collection.

- **Lines 68–72** — SQL to pull `schemaname`, `tablename`, `tableowner`, `tablespace`, `hasindexes` from `pg_tables`.
- **Line 74** — Separate `COUNT(*)` query for the row count.
- **Lines 79–81** — If the table doesn't exist, return `None`.
- **Lines 83–92** — Assemble a dict with `table_info` and `record_count`.

> ⚠️ Note: `count_sql` on **line 74** interpolates `collection_name` directly into the SQL string (`f'...FROM {collection_name}'`). This is common throughout this class for table names (which can't be bound as parameters), so `collection_name` must always come from trusted/validated input — never from raw user input.

---

## `delete_collection` — lines 94–103

Drops the collection table.

- **Line 97** — Logs the deletion.
- **Line 99** — `DROP TABLE IF EXISTS <collection_name>`.
- **Line 103** — Returns `True`.

---

## `create_collection` — lines 105–132

Creates a new collection table if it doesn't already exist.

- **Lines 109–110** — If `do_reset=True`, drop the table first.
- **Line 112** — Skip creation if the table already exists.
- **Lines 117–126** — `CREATE TABLE` with columns: `id` (bigserial PK), `text`, `vector(embedding_size)`, `metadata` (jsonb), and `chunk_id` with a **foreign key to `chunks(chunk_id)`**.
- **Line 130** — Returns `True` when created; **line 132** returns `False` when it already existed.

---

## `is_index_existed` — lines 134–146

Checks whether the vector index for a collection exists.

- **Line 135** — Builds the expected index name.
- **Lines 138–144** — Query `pg_indexes` for that `tablename` + `indexname`.
- **Line 146** — Returns `True`/`False`.

---

## `create_vector_index` — lines 148–173

Creates the vector similarity index — but only when worthwhile.

- **Lines 150–152** — Bail out if the index already exists.
- **Lines 156–158** — Count rows in the table.
- **Lines 160–161** — If row count is below `index_threshold`, skip (small tables search fine without an index).
- **Line 163** — Log start.
- **Lines 166–169** — `CREATE INDEX ... USING <index_type> (vector <distance_method>)` — default index type is **HNSW** (see the parameter default on **line 149**).
- **Line 173** — Log completion.

---

## `reset_vector_index` — lines 175–184

Drops the existing index (**lines 181–182**) then rebuilds it via `create_vector_index` (**line 184**). Used when you want to force a fresh index.

---

## `insert_one` — lines 187–218

Inserts a single record.

- **Lines 191–194** — Fail (log error, return `False`) if the collection doesn't exist.
- **Lines 196–198** — Fail if no `record_id` (used as `chunk_id`).
- **Lines 202–205** — `INSERT INTO` statement targeting the text/vector/metadata/chunk_id columns.
- **Line 207** — Serialize `metadata` to JSON (or `"{}"`).
- **Lines 208–213** — Execute the insert. The vector list is formatted as a pgvector literal `"[v1,v2,...]"` (**line 210**).
- **Line 216** — After inserting, attempt to (re)build the vector index.
- **Line 218** — Returns `True`.

---

## `insert_many` — lines 221–268

Batch insert, more efficient for many rows.

- **Lines 225–228** — Fail if the collection doesn't exist.
- **Lines 230–232** — Fail if `vectors` and `record_ids` lengths mismatch.
- **Lines 234–235** — If no metadata provided, fill with `None` placeholders.
- **Lines 239–243** — Loop over the data in slices of `batch_size` (default 50, **line 223**).
- **Lines 247–255** — Build a list of parameter dicts for the batch (same vector-literal + JSON-metadata formatting as `insert_one`).
- **Lines 257–264** — One `INSERT` executed with the whole batch of values (executemany).
- **Line 266** — Rebuild the index once after all batches.
- **Line 268** — Returns `True`.

---

## `search_by_vector` — lines 270–296

Similarity search: given a query vector, return the top-`limit` closest chunks.

- **Lines 272–275** — Fail if the collection doesn't exist.
- **Line 277** — Format the query vector as a pgvector literal.
- **Lines 280–284** — SQL selecting `text` and a `score` computed as `1 - (vector <=> :vector)` (cosine distance operator `<=>` turned into a similarity score), ordered by score descending, limited to `limit`.
- **Line 288** — Fetch all rows.
- **Lines 290–296** — Map each row into a `RetrievedDocument(text=..., score=...)`.

---

## Cross-cutting notes

- **Logging (line 4, 28):** uses `loguru`, consistent with the rest of the project. In Docker, loguru writes to `stderr` and is captured by `docker logs`; set `PYTHONUNBUFFERED=1` so lines aren't buffered.
- **Table names are string-interpolated, values are bound.** Column *values* (`:vector`, `:collection_name`, etc.) use safe parameter binding; table *names* are interpolated because SQL can't bind identifiers. Keep `collection_name` values trusted.
- **Auto-indexing:** both insert paths call `create_vector_index`, which is a cheap no-op until the table crosses `index_threshold` rows.
