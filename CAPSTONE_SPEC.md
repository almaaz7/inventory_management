# Capstone — Catalog & Inventory Service (REST API)

> One backend repo that lets you honestly speak to ~80% of your resume and walks
> you through Learning-Path Phases 2–5. API-first (DRF only, no templates).
> Owner: Almaaz Ahmed · Target: Info Edge SSE Backend (Python).

---

## 1. The product (what you're building)

A backend service for a small e-commerce / warehouse business to manage its
**catalog** (what's for sale) and **inventory** (how much stock exists, and
every movement of it). Think of the kind of service that sits behind an admin
panel and a storefront.

Real businesses need this to: list products, group them, track suppliers, know
current stock, log every stock change (received / sold / adjusted), run async
jobs (low-stock alerts, supplier sync), search the catalog fast, and — the
modern twist — let a user ask questions in natural language ("which suppliers
ship electronics under ₹500?").

You are building **only the API**. Consumers are Postman, your tests, the
auto-generated docs, and later an MCP client.

---

## 2. Target architecture (end state — don't build this all at once)

```
                ┌─────────────────────────────────────────────┐
   HTTP  ─────▶ │  Django + DRF  (JWT auth, RBAC, viewsets)    │
                │   - catalog app   (Category, Product, ...)   │
                │   - inventory app (StockMovement, ...)        │
                │   - accounts app  (roles/permissions)         │
                └───┬───────────┬───────────┬──────────┬───────┘
                    │           │           │          │
              ┌─────▼────┐ ┌────▼────┐ ┌────▼─────┐ ┌──▼──────────┐
              │ Postgres │ │  Redis  │ │  Kafka   │ │  Typesense  │
              │ (+pgvec) │ │ (cache/ │ │ (events) │ │  (search)   │
              │          │ │ broker) │ │          │ │             │
              └──────────┘ └────┬────┘ └────┬─────┘ └─────────────┘
                                │           │
                          ┌─────▼─────┐ ┌───▼────────────┐
                          │  Celery   │ │ Kafka consumer │
                          │ worker+   │ │ (stock events) │
                          │ beat      │ └────────────────┘
                          └───────────┘
              ┌──────────────────────────────────────────┐
              │  MCP server  →  exposes catalog as tools  │
              │  RAG endpoint → embeddings in pgvector     │
              └──────────────────────────────────────────┘
       Everything runs via  docker compose up.
```

---

## 3. Tech stack (introduced milestone by milestone — don't install all now)

| Area        | Tool                                             |
|-------------|--------------------------------------------------|
| Web/API     | Django, Django REST Framework                    |
| Auth        | djangorestframework-simplejwt (JWT) + RBAC       |
| DB          | PostgreSQL (with `pgvector` later)               |
| Cache/Broker| Redis                                            |
| Async       | Celery + Celery Beat                             |
| Messaging   | Kafka (`confluent-kafka` or `kafka-python`)      |
| Search      | Typesense (Postgres full-text as a stepping stone)|
| Tests       | pytest, pytest-django, factory_boy, coverage     |
| Docs        | drf-spectacular (OpenAPI / Swagger)              |
| AI          | Embeddings + pgvector (RAG), a custom MCP server |
| Infra       | Docker + docker compose                          |

---

## 4. Milestone roadmap

Each milestone is a real ticket. You build it, commit it, then tell me the path
and I review it against the acceptance criteria before we move on.

| #  | Milestone                         | Learning-Path phase | New muscles |
|----|-----------------------------------|---------------------|-------------|
| M0 | Pro project bootstrap             | 1 → 2 (infra)       | Postgres, docker compose, settings/env hygiene |
| M1 | Core domain + DRF CRUD + RBAC     | 1 (deepen)          | multi-model relations, JWT, roles, **N+1 / select_related** |
| M2 | Postgres performance              | 2                   | indexes, `EXPLAIN ANALYZE`, pagination, filtering |
| M3 | Celery + Redis                    | 2                   | async tasks, retries, Beat, idempotency, cache-aside |
| M4 | Kafka events                      | 3                   | producer/consumer, topics, Kafka-vs-Celery |
| M5 | Search                            | 3                   | indexing, faceting, Typesense |
| M6 | Tests + API quality               | 3                   | pytest-django, factory_boy, versioning, rate limit, OpenAPI |
| M7 | AI layer (your edge)              | 4                   | embeddings, pgvector, RAG endpoint, MCP server |
| M8 | Senior framing                    | 5                   | design patterns, architecture doc, system-design notes |

> DSA (Phase 5 coding round) runs **in parallel**, not in this repo — keep doing
> a few problems a week on the side.

Detailed tickets for **M0** and **M1** are below. M2–M8 are sketched; I'll
expand each into a full ticket with acceptance criteria when we reach it (the
later ones depend on what you learn earlier).

---

## M0 — Professional project bootstrap

**Goal:** stand up a real, production-shaped Django project running on
PostgreSQL inside Docker — the way a team actually starts a service. No app
logic yet.

**Requirements (definition of done)**
1. Repo lives in this folder. `git init`, sensible `.gitignore` (Python +
   `.env` + `__pycache__` + `db data`).
2. A virtualenv, and a `requirements.txt` (pin: `django`, `djangorestframework`,
   `djangorestframework-simplejwt`, `psycopg2-binary`, `python-dotenv` or
   `django-environ`).
3. `django-admin startproject config .` (project package named `config`), plus a
   first app: `python manage.py startapp accounts`.
4. **PostgreSQL via `docker-compose.yml`** — a `db` service (postgres:16) and a
   `web` service running Django. App connects to Postgres, **not** sqlite.
5. **Settings hygiene:** secrets (`SECRET_KEY`, DB creds) come from environment
   / `.env`, never hard-coded. `DEBUG` from env. `ALLOWED_HOSTS` configurable.
6. A trivial health endpoint: `GET /api/health/` → `{"status": "ok"}` (proves
   DRF is wired).
7. `docker compose up` brings the whole thing up; migrations run cleanly.

**🔎 Look up yourself:** how Django reads `DATABASES` from env; how a Dockerfile
for Python looks; `depends_on` + healthcheck so `web` waits for `db`.

**Acceptance criteria**
- [ ] `docker compose up` starts `db` + `web` with no errors
- [ ] `GET /api/health/` returns 200 `{"status":"ok"}`
- [ ] No secret or password is committed to git (I'll grep for it)
- [ ] `python manage.py migrate` runs against Postgres
- [ ] `requirements.txt` is pinned and complete

**Stretch:** add a `Makefile` or PowerShell script for `up`/`down`/`migrate`/
`test`; add `pre-commit` with black + ruff.

---

## M1 — Core domain, DRF CRUD, JWT + RBAC, and the N+1 fix

**Goal:** the heart of the API — your data model and secured CRUD — built the way
a senior would, including the single most likely interview question (ORM N+1).

**Domain models** (in `catalog` and `inventory` apps you create):
- `Category` — `name`, `slug`, optional self-FK `parent` (subcategories).
- `Supplier` — `name`, `email`, `lead_time_days`.
- `Product` — `name`, `sku` (unique), `description`, `price`
  (**`DecimalField`**, never float), `category` (FK), `suppliers`
  (**ManyToMany**), `is_active`, `created_at`, `updated_at`.
- `StockMovement` (in `inventory`) — `product` (FK), `change` (int, +/-),
  `reason` (choices: `received`/`sold`/`adjusted`), `created_at`, `created_by`
  (FK→User). Current stock = sum of a product's movements.

**API (ModelViewSet + DefaultRouter):**
- `/api/categories/`, `/api/suppliers/`, `/api/products/`, `/api/stock-movements/`
  — full CRUD.
- `GET /api/products/` must include each product's `current_stock` and its
  category name **without firing one query per product** (this is the N+1 test).

**Auth + RBAC (roles):**
- JWT via SimpleJWT (`/api/token/`, `/api/token/refresh/`). All write endpoints
  require auth.
- Two roles: **Manager** (full CRUD) and **Staff** (read catalog, create
  `StockMovement` only). Enforce with DRF permissions / groups.
- `StockMovement.created_by` is **server-set** (never trust the client).

**🔎 Look up yourself:** `select_related` (FK) vs `prefetch_related` (M2M /
reverse FK) and *why* each exists; annotating `current_stock` with
`Sum` at the DB level vs computing in Python; DRF custom permission classes;
how to inspect query count (`django.db.connection.queries` / `assertNumQueries`).

**Acceptance criteria**
- [ ] All four resources do full CRUD through the router
- [ ] Logged-out write → 401; Staff doing a Manager-only action → 403
- [ ] `GET /api/products/` issues a **constant** number of queries regardless of
      product count (prove it — I'll check with `assertNumQueries`)
- [ ] `current_stock` is correct and computed efficiently
- [ ] `price` is `Decimal`; `created_by` is server-set
- [ ] Migrations are clean and committed

**Stretch:** soft-delete (`is_active`) instead of hard delete; `slug`
auto-generated; nested category breadcrumb in the serializer.

---

## M2 — PostgreSQL performance

**Goal:** make the catalog fast *and measurable*. Add pagination + filtering, put
indexes where your query patterns actually need them, and **prove** the impact
with `EXPLAIN ANALYZE`. This is the milestone that earns you the right to say
"sub-100ms" in the interview and defend it.

**Requirements (definition of done)**
0. **First commit: the M1 carryover** — Staff `PATCH /api/products/` → 403.
1. **Pagination** — turn on global DRF pagination (`DEFAULT_PAGINATION_CLASS` +
   `PAGE_SIZE`). Right now list endpoints return *every* row — unbounded lists
   are a real production hazard.
2. **Filtering / search / ordering** on `/api/products/` via `django-filter` +
   DRF `SearchFilter`/`OrderingFilter`: filter by `category`, `supplier`,
   `is_active`; search by `name`/`sku`; order by `price`/`created_at`.
3. **Bulk seed** — a management command (e.g. `python manage.py seed_data
   --products 5000`) that generates enough rows that index differences are
   visible. (Small data hides everything — you must measure on volume.)
4. **Deliberate indexes** — add at least **two** via `class Meta: indexes =
   [models.Index(...)]`, each justified by a query you actually run (e.g. a
   composite for "active products in a category, newest first"; an index on
   `StockMovement(product, created_at)` for the stock rollup). 🔎 First find out
   which columns Postgres/Django **already** index (PKs, unique fields, FK
   columns) so you don't add redundant ones.
5. **Measure it** — in `docs/PERFORMANCE.md`, paste `EXPLAIN ANALYZE` for one
   realistic query **before vs after** your index on the seeded dataset. Show
   the plan flip (Seq Scan → Index Scan), the row counts, and actual times, with
   2–3 sentences explaining what changed and why.

**🔎 Look up yourself:** `models.Index` & `Meta.indexes`; `QuerySet.explain(analyze=True)`;
how to read a plan (Seq Scan vs Index Scan, "rows", "actual time"); `django-filter`
`FilterSet`; DRF `filter_backends`, `filterset_fields`, `search_fields`, `ordering_fields`.

**Acceptance criteria**
- [ ] Staff `PATCH /api/products/` → 403 (carryover closed)
- [ ] List endpoints paginated (global default)
- [ ] `/api/products/?category=<id>&search=<q>&ordering=-created_at` works
- [ ] ≥2 indexes added via `Meta.indexes`, each justified by a real query
- [ ] `seed_data` command generates bulk rows
- [ ] `docs/PERFORMANCE.md` shows EXPLAIN ANALYZE before/after (plan + timing + why)
- [ ] Index migrations clean & committed

**Stretch:** a partial index (`WHERE is_active = true`) and when it helps;
`.only()`/`.defer()` to trim columns and measure the difference; time the actual
request latency before/after to put a real number on "sub-100ms".

## M3 — Celery + Redis

**Goal:** move slow/periodic work off the request path and cache hot reads — the
"Celery + Redis async pipelines" + "Redis caching" resume claims. This is the
milestone that makes those defensible.

**Requirements (definition of done)**
0. **Carryover from M2:** commit `docs/PERFORMANCE.md` (use the captured plans),
   and add a 2nd justified index (e.g. `(category, created_at)` to kill the
   `ORDER BY created_at` heapsort in query C).
1. **Infra in `docker-compose.yml`:** add a `redis` service, a `celery` worker
   service, and a `celery-beat` service (worker/beat reuse the `web` image,
   different `command`). Broker + result backend = Redis, URLs from env.
2. **Celery wired into Django:** `config/celery.py` (the `Celery()` app +
   `autodiscover_tasks`), imported from `config/__init__.py`; settings read
   `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` from env.
3. **≥2 tasks** (use `@shared_task`):
   - **low-stock scan** — find products with `current_stock < threshold`, build a
     report (log it / store it).
   - **notify-supplier** — when a `StockMovement` pushes a product below
     threshold, enqueue a task that "emails" the supplier (use Django's
     **console email backend** — don't send real mail). Trigger it from
     `perform_create` (or a signal) via `.delay()`.
4. **Celery Beat** runs the low-stock scan on a schedule (`beat_schedule` or
   `django-celery-beat`).
5. **Retries + idempotency:** one task uses `autoretry_for` / `retry_backoff` /
   `max_retries`; make the notify task **idempotent** (don't double-notify for
   the same movement — guard with a flag/key).
6. **Cache-aside with Redis:** cache the product list (or the low-stock report)
   via Django's cache framework (`django.core.cache`) with a **TTL**, and
   **invalidate on write** (product/stock-movement create/update). Demonstrate a
   cache **miss then hit**.

**🔎 Look up yourself:** Celery + Django app setup; `@shared_task`; `.delay()` vs
`.apply_async()`; Celery Beat `beat_schedule`; Django 4+ built-in
`django.core.cache.backends.redis.RedisCache`; the cache-aside pattern;
`EMAIL_BACKEND = console`; why tasks must be idempotent (at-least-once delivery).

**Acceptance criteria**
- [ ] `docker compose up` also starts `redis` + `celery` worker + `celery-beat`
- [ ] `low_stock.delay()` runs on the worker (show the worker log)
- [ ] A threshold-crossing `StockMovement` enqueues the notify task (console email)
- [ ] Beat fires the scan on its interval
- [ ] One task demonstrates retry-with-backoff
- [ ] Product list / report cached in Redis with TTL, invalidated on write (miss→hit)
- [ ] `docs/PERFORMANCE.md` + 2nd index committed (M2 carryover)
- [ ] New services + code committed

**Stretch:** denormalize `current_stock` into a column kept fresh by a task/signal
(so reads stop aggregating); Flower for worker monitoring; a Celery `chain`/`group`;
persist the low-stock report in a model with a history.

> Heads-up: your `seed_data` creates products but **no `StockMovement`s**, so every
> product currently has `current_stock = 0`. To exercise low-stock logic, seed
> some movements (extend the command, or add a few via the API).

## M4 — Kafka events

**Goal:** event-driven messaging — produce a domain event on every stock change,
consume it in a *separate* process. This backs your "Kafka messaging" claim,
which is your **weakest required JD skill**, so this is where you earn it.

**Requirements (definition of done)**
0. **Carryovers from M3:**
   - Add **retry + backoff** to a task (`autoretry_for` / `retry_backoff` /
     `max_retries`) — natural fit: `notify_supplier`'s `send_mail`. ⚠️ This
     collides with your idempotency lock (the lock is taken *before* send, so a
     retry hits "Duplicate execution blocked" and never resends). Fix the order:
     mark "done" only *after* success.
   - **Fix stock drift:** make `StockMovement` *create* also call
     `recompute_product_stock(...)` so the ledger is the single source of truth
     on all three paths (create/update/delete). Kills both the drift *and* the
     read-modify-write race.
1. **Kafka in `docker-compose.yml`** — a single-node Kafka (KRaft mode, no
   Zookeeper) + your Python client (`confluent-kafka` or `kafka-python`) in
   requirements.
2. **Producer:** on every `StockMovement`, publish a `stock.changed` event (JSON:
   `product_id`, `sku`, `change`, `new_stock`, `reason`, `actor`, `ts`).
   **Partition by `product_id`** (key) so one product's events stay ordered.
3. **Produce on commit, not in the request body:** use
   `transaction.on_commit(...)` so you never emit an event for a rolled-back
   transaction. (This is the **dual-write problem** — be ready to explain it.)
4. **Consumer:** a *separate* compose service running a management command
   (`consume_stock_events`) that reads the topic with a **consumer group** and
   acts — e.g. append to an audit/ledger table or a read-model — committing
   offsets sensibly.
5. **Concepts:** be able to whiteboard topics / partitions / offsets / consumer
   groups / keys, and **Kafka vs RabbitMQ vs Celery** (when each).

**🔎 Look up yourself:** single-node Kafka in Docker (KRaft); `confluent-kafka`
`Producer`/`Consumer`; partition **keys** and ordering; **consumer groups** &
offset commit; `transaction.on_commit`; the **outbox pattern** (why producing to
Kafka *and* writing the DB in one request is a dual-write hazard).

**Acceptance criteria**
- [ ] Carryovers done (task retry+backoff; create recomputes stock)
- [ ] `docker compose up` also starts Kafka + a `consumer` service
- [ ] Creating a `StockMovement` produces a `stock.changed` event (show it on the topic)
- [ ] Consumer reads via a consumer group and acts (ledger/audit/log)
- [ ] Events fire **on commit**, keyed by `product_id`
- [ ] Committed

**Stretch:** the **outbox pattern** (write event to an outbox table in the same
DB txn; a relay publishes) to truly solve dual-write; a dead-letter topic for
poison messages; replay from offset 0 into a fresh read-model; write
`docs/MESSAGING.md` (Kafka vs RabbitMQ vs Celery) — your interview cheat-sheet for
the weakest JD skill.

> Kafka-in-Docker is the fiddliest infra so far. Get a single broker healthy and
> a trivial produce/consume working **first** (prove the pipe), *then* wire it to
> `StockMovement`. Don't debug Kafka config and your event logic at the same time.

## M5 — Search (Typesense)

**Goal:** fast, typo-tolerant, faceted search over the catalog — backs the
"Typesense search over 1M+ records (sub-50ms)" resume claim. You already know the
*concepts* from your PHP/KMS work; this ports them to Python.

**Requirements (definition of done)**
0. **Close any open carryovers** (task retry+backoff, stock drift) if still pending.
1. **Typesense in `docker-compose.yml`:** add a `typesense` service
   (`typesense/typesense` image) with an `--api-key` and a data volume + healthcheck.
2. **Python client:** `pip install typesense`; connection settings from env.
3. **Collection schema:** define a `products` collection — `name`, `sku`,
   `description`, `category` (facet), `suppliers` (facet), `price`, `current_stock`,
   `is_active` (facet). Choose field types + which are `facet: true`.
4. **Index + keep in sync:** a `sync_typesense` management command to bulk-index your
   10k products, **and** keep the index fresh on write (product/stock-movement
   create/update/delete) — ideally via a **Celery task** (reuse M3) so indexing is
   off the request path.
5. **Search endpoint:** `GET /api/search/?q=...&category=...&in_stock=...` returning
   typo-tolerant hits **with facet counts** (by category, supplier, in-stock).
6. **Know when to use what** — you'll now have *three* ways to find a product:
   Postgres filtering (M2, exact/structured), Typesense (M5, keyword/faceted/typo),
   vector search (M7, semantic). Be ready to explain which fits which query.

> Optional stepping stone: do **Postgres full-text search** first (`SearchVector`,
> `SearchQuery`, `SearchRank`, a `GIN` index) to understand the mechanics, then port
> to Typesense. Good for the interview ("I can do FTS in Postgres *and* knew when to
> reach for a dedicated engine").

**🔎 Look up yourself:** Typesense collection schema + `facet_by`; the
`typesense-python` client (`documents.import_`, `documents.search`); typo tolerance
& `query_by`; Django Postgres full-text (`SearchVector`/`SearchQuery`/`GIN`).

**Acceptance criteria**
- [ ] `docker compose up` starts a healthy `typesense` service
- [ ] All products indexed; index updates on write (show a create reflecting in search)
- [ ] `/api/search/?q=<typo>` returns the right product despite the typo
- [ ] Results include **facet counts** and can be filtered by category/supplier/in-stock
- [ ] Committed; Typesense key in `.env` + `.env.example`

**Stretch:** highlighted match snippets; synonyms; measure and record search latency
(aim sub-50ms); a single `/api/search/` that routes to keyword vs semantic (M7) based
on the query.

## M6 — Tests + API quality

**Goal:** prove the system works and harden the API for real use. Testing is the #1
Tier-A hireability gap, and this milestone turns every behavior I've been verifying
*by hand* into an automated suite that travels with the repo.

**Requirements (definition of done)**
0. **Close any open carryovers** (task retry+backoff, stock drift) — and write the
   test that proves each, so they can't regress.
1. **Test stack:** `pytest`, `pytest-django`, `factory_boy`, `pytest-cov` in
   requirements; a `pytest.ini`/`pyproject.toml` with `DJANGO_SETTINGS_MODULE`.
2. **Factories** (`factory_boy`) for `User`, `Category`, `Supplier`, `Product`,
   `StockMovement` — so tests build data declaratively.
3. **Cover the behaviors I verified live** (now as real tests):
   - RBAC: unauth write → 401; Staff `PATCH /products/` → 403; Staff create
     stock-movement → 201; `created_by` is server-set, not client-spoofable.
   - **N+1:** `assertNumQueries` / `django_assert_num_queries` proving the product
     list is a constant query count.
   - `current_stock` correctness **including the drift fix** (ledger = source of truth).
   - Celery tasks run under `CELERY_TASK_ALWAYS_EAGER=True`; notify-supplier
     **idempotency** (second call is a no-op); cache miss→hit→invalidation.
4. **Coverage:** a target (≥ 80% on `catalog`) via `pytest-cov`; a `make test` target.
5. **API versioning:** move routes under `/api/v1/` (DRF `URLPathVersioning`).
6. **Rate limiting:** DRF throttling — `AnonRateThrottle` + `UserRateThrottle`, and a
   scoped throttle on the expensive endpoints (`/api/ask/`, `/api/search/`).
7. **Idempotency keys** on stock-movement create: accept an `Idempotency-Key` header
   and dedupe repeated submits (don't double-apply stock).
8. **OpenAPI docs:** `drf-spectacular` — schema at `/api/schema/`, **Swagger UI** at
   `/api/docs/`.

**🔎 Look up yourself:** `pytest-django` (`db` fixture, `django_assert_num_queries`);
`factory_boy` (`SubFactory`, `post_generation` for M2M); `CELERY_TASK_ALWAYS_EAGER`;
DRF throttling scopes; `drf-spectacular` setup; DRF `URLPathVersioning`.

**Acceptance criteria**
- [ ] `pytest` runs green; coverage ≥ 80% on `catalog`
- [ ] Every behavior I verified by hand (RBAC, N+1, stock, cache, idempotency) has a test
- [ ] Routes served under `/api/v1/`
- [ ] Exceeding a throttle returns **429**
- [ ] Swagger UI renders at `/api/docs/` from the live schema
- [ ] Committed

**Stretch:** **GitHub Actions** CI running `pytest` on every push (great signal on the
repo); `hypothesis` property tests on the stock math; contract test for the OpenAPI
schema; coverage badge in the README.

## M7 — AI layer (your differentiator)  ← **PULLED FORWARD (doing this now, before M4–M6)**

**Goal:** the thing that sets your resume apart — semantic search + RAG over your
own catalog, then a custom **MCP server** that exposes the catalog as tools an LLM
can call. Built on the M1–M3 data you already have; needs nothing from M4–M6.

Two halves: **M7A — RAG endpoint**, then **M7B — MCP server**.

### Key facts (verified against the current Claude API reference, 2026-06)

- **Anthropic has no embeddings API.** Embeddings come from elsewhere — this is a
  real interview talking point. Two good choices:
  - **Local `sentence-transformers`** (e.g. `all-MiniLM-L6-v2`, 384-dim) — free, no
    API key, runs in your container. **Recommended for this milestone** (learn the
    whole pipeline at zero cost).
  - **Voyage AI** (`voyage-3` family) — Anthropic's recommended embeddings partner;
    paid, needs a key. The "production / Anthropic-aligned" answer to cite.
- **Generation = the Claude Messages API** via the official `anthropic` Python SDK.
  Model id + price per 1M tokens (input/output): `claude-opus-4-8` $5/$25 (default,
  most capable) · `claude-sonnet-4-6` $3/$15 · `claude-haiku-4-5` $1/$5 (**cheapest —
  fine for this demo**). Put the model in an env var (`ANTHROPIC_MODEL`) so it's a
  one-line switch. API key in `.env` (already gitignored) — **never commit it**.

### M7A — RAG search endpoint

1. **pgvector infra:** swap the DB image `postgres:16` → **`pgvector/pgvector:pg16`**
   (drop-in), enable the extension via a migration (`CREATE EXTENSION IF NOT EXISTS
   vector;` in a `RunSQL` migration), `pip install pgvector sentence-transformers`.
2. **Store embeddings:** add a `pgvector` `VectorField(dimensions=384)` to `Product`
   (or a `ProductEmbedding` table). Embed `name + " " + description`. Generate the
   embedding **on create/update** — ideally as a **Celery task** (reuse M3!). Add a
   `backfill_embeddings` management command for your existing 10k products.
3. **Retrieve:** embed the user's query, then top-K nearest products by **cosine
   distance** (`pgvector`'s `CosineDistance` in the ORM, `<=>` in SQL). Add an
   HNSW/IVFFlat index on the vector column for speed (ties back to M2!).
4. **Generate:** `POST /api/ask/ {"q": "..."}` → retrieve top-K → build a prompt with
   those products as context → one `client.messages.create(...)` call → return a NL
   answer (+ the cited product ids). Default `max_tokens≈1024`; stream if you want.
   Gracefully handle "no API key configured".

**🔎 Look up:** `pgvector` Django integration (`VectorField`, `CosineDistance`, HNSW
index); `sentence-transformers` quickstart; the `anthropic` SDK
`client.messages.create`; why you embed query and docs with the **same** model.

### M7B — MCP server

5. `pip install mcp`. Build `mcp_server.py` with **FastMCP**, exposing tools:
   `search_products(query)`, `get_stock(sku)`, `low_stock_report(threshold)`. Each
   tool calls your Django ORM (do `django.setup()` at startup) — the schema is
   generated from the typed function signature + docstring.
6. **Transport:** **stdio** for local testing (point the **MCP Inspector** or Claude
   Desktop at it). Note streamable-HTTP as the remote option.
7. **Be able to walk it end-to-end:** which tools are exposed, their JSON schema, and
   how an LLM discovers + calls them. *This is the rare-on-a-junior-resume talking
   point — rehearse it out loud.*

**🔎 Look up:** the **MCP Python SDK** (`FastMCP`, `@mcp.tool()`), stdio vs HTTP
transport, the **MCP Inspector** for testing a server without writing a client.

**Acceptance criteria**
- [ ] DB runs `pgvector/pgvector:pg16`; `vector` extension enabled via migration
- [ ] Products have embeddings; `backfill_embeddings` populates the 10k existing rows
- [ ] Vector similarity search returns sensible top-K for a query (with an index)
- [ ] `POST /api/ask/` returns a grounded NL answer citing real products
- [ ] API key only in `.env` (I'll grep to confirm it's not committed)
- [ ] MCP server exposes ≥3 working tools, testable via MCP Inspector
- [ ] Committed; `ANTHROPIC_MODEL` + key documented in `.env.example`

**Stretch:** embed on write via a Celery task (not inline); add `citations`/sources to
the answer; a hybrid retrieve (vector + your M2 filters); rerank top-K; expose the RAG
`ask` itself as a 4th MCP tool.

> Order: **(a)** pgvector image + extension + `VectorField` + backfill → **(b)** vector
> search proven in the shell → **(c)** `/api/ask/` with Claude → **(d)** MCP server.
> Get retrieval returning sane results **before** wiring the LLM — debug one layer at
> a time.

## M8 — Senior framing

**Goal:** make the **SSE** (senior) title defensible — show deliberate design, not
just working code, and give the whole repo a narrative an interviewer can follow in
five minutes. This is the milestone that converts "it works" into "I designed this."

**Requirements (definition of done)**
1. **Close all carryovers** — the repo should have zero known open issues.
2. **One deliberate pattern refactor** (pick one, do it well, write *why*):
   - **Service layer** — a `StockService` that owns all stock mutations + the
     `recompute` logic, so create/update/delete go through **one** path (this is also
     the clean home for the drift fix). Demonstrates Single-Responsibility + a thin
     views/fat-service split.
   - or a **Strategy** (`PricingStrategy` — e.g. regular vs discounted) / a **Factory**
     for building `StockMovement`s / a **Repository** wrapping catalog queries.
3. **SOLID write-up:** a short section in the docs pointing at where SRP / OCP / DIP
   actually show up in your code (concrete file/line references, not theory).
4. **`ARCHITECTURE.md`:** a data-model diagram (Mermaid is fine in Markdown), the
   request flow, the layers (auth/RBAC → cache → async → search → AI), a **scaling
   story** (read replicas, cache, partitioning, where Kafka decouples), and the
   **consistency trade-off** (denormalized `current_stock` = eventual consistency on
   the async path; CAP framing).
5. **Top-level `README.md`:** what it is, the stack, `docker compose up` to run it,
   the endpoint list, and a couple of `curl` examples (get a token → call `/api/v1/...`).
6. **Operational polish:** a `Makefile`/PowerShell script for `up`/`down`/`migrate`/
   `seed`/`test`; a complete `.env.example`; a tidy final commit history.

**🔎 Look up yourself:** the **service-layer** pattern in Django (fat models vs
services); Strategy/Repository/Factory in Python; SOLID-in-Python examples; **Mermaid**
diagrams in Markdown.

**Acceptance criteria**
- [ ] One pattern refactor landed, with a written rationale
- [ ] `ARCHITECTURE.md` + `README.md` present, accurate, and diagrammed
- [ ] `docker compose up` brings the **whole** stack up clean (db+pgvector, redis,
      web, celery, beat, kafka, consumer, typesense)
- [ ] All carryovers closed
- [ ] Repo pushed to **`github.com/almaaz7`**

**Stretch:** **deploy it live** (Railway/Render/Fly with managed Postgres + Redis) and
put the URL in the README; a 3-minute demo video; a load test (`locust`/`k6`) with real
latency numbers to back the "sub-100ms / sub-50ms" resume lines.

---

## 4b. Porting to a new machine (read this before you switch PCs)

git carries your **code and migrations** — but **not** three things you need to run.
On the new PC, after `git clone` (or copying the folder):

| Needs recreating | Why it's missing | How to restore |
|---|---|---|
| **`.env`** | gitignored (holds secrets) | Copy `.env.example` → `.env` and fill in real values (DB creds, `SECRET_KEY`, `ANTHROPIC_API_KEY`, Typesense key). **Move the `.env` across by hand** (USB / password manager / secure note) — never commit it. |
| **`venv/`** | gitignored, OS-specific binaries | Recreate: `python -m venv venv` → activate → `pip install -r requirements.txt`. (Inside Docker you don't need it at all.) |
| **Database data** (your 10k seeded rows) | lives in the Docker named volume `postgres_data`, which is local to this PC | On the new PC: `docker compose up -d` → `manage.py migrate` → **re-run `manage.py seed_data --products 10000`**. *Or* port the data: `docker compose exec db pg_dump -U <user> <db> > dump.sql`, copy `dump.sql`, then `psql < dump.sql` on the new machine. |

**Checklist on the new PC:**
1. `git clone …` (push from this PC first if you haven't — see M8 acceptance).
2. Create `.env` from `.env.example` with real values.
3. `docker compose build` then `docker compose up -d`.
4. `docker compose exec web python manage.py migrate`.
5. `docker compose exec web python manage.py seed_data --products 10000` (+ create the
   RBAC groups migration runs automatically; create a superuser if you want admin).
6. `curl localhost:8000/api/health/` → `{"status":"ok"}` confirms you're back.

> Everything else — `CAPSTONE_SPEC.md` (this file), all source, migrations,
> `docker-compose.yml`, `Dockerfile`, `requirements.txt`, `.dockerignore`,
> `.env.example` — **is** in git and travels automatically. Push before you leave.

---

## 5. How we work together (the working agreement)

- **You build; I review and teach.** I won't hand you whole solutions. Stuck for
  >15 min on one thing → ask me a *targeted* question.
- **One milestone at a time.** Build it, commit it (`git commit` per logical
  chunk, clear messages), then tell me: *"M1 done, path is …"*. I read your code
  and run it, then give a real review: bugs → security → "how a senior writes
  this" → score vs the acceptance checkboxes above.
- **I track progress** by ticking the boxes in this file as you pass each gate.
- **Best practices are graded**, not just "does it work": env hygiene, query
  efficiency, naming, error handling, test coverage, commit quality.
- When a milestone passes, I expand the next one into a full ticket.

---

## 6. Progress tracker

- [x] **M0** — Pro project bootstrap *(passed 2026-06-26)*
- [x] **M1** — Core domain + DRF CRUD + RBAC + N+1 fix *(passed 2026-06-27 — N+1 constant, CRUD works, created_by anti-spoof verified; carryover Staff-PATCH-403 closed in M2)*
- [x] **M2** — Postgres performance *(passed 2026-06-28; 2nd index `(created_at)` added in M3 ✅; `PERFORMANCE.md` skipped per user request — optional)*
- [x] **M3** — Celery + Redis *(passed 2026-06-29 — redis/worker/beat healthy; tasks + idempotency lock + generational cache-aside all verified; denormalized `current_stock` stretch done)* · **2 CARRYOVERS still open: (1) task retry+backoff; (2) stock drift fix — fold into whichever milestone you commit next**
- [ ] **M7** — AI layer (RAG + MCP)  ← **in progress (pulled forward at user's request)**
- [ ] **M4** — Kafka events  *(expanded & ready — deferred until after M7)*
- [ ] **M5** — Search (Typesense)  *(deferred)*
- [ ] **M6** — Tests + API quality  *(deferred)*
- [ ] **M8** — Senior framing
- [ ] Capstone pushed to `github.com/almaaz7`
