# Step 2: Upload + extraction pipeline

This plan covers **PRD Section 8 item 2** only: prove PDF → structured
JSON on a queue, with per-user document isolation. Later items
(review/confirm editor, `policies` / `policy_history` tables, property
CRUD UI, dashboard, vision OCR for scanned PDFs) are out of this cycle
per `development-rules.md` §3. Scanned PDFs fail clearly if text is too
thin.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Queue | Dramatiq + existing Redis, **DB 2** (`DRAMATIQ_REDIS_URL=redis://…:6379/2`) | API enqueues; a **separate worker process** (same backend image, different command) runs extraction. No RabbitMQ. Sessions stay on **DB 0**; pytest already uses **DB 1**. A Redis *process* restart still drops both sessions and queued jobs; DB 2 only keeps a session `FLUSHDB` on 0 from wiping the queue. |
| LLM | LangGraph `StateGraph` + `langchain-openrouter` `ChatOpenRouter` (first-party; not `ChatOpenAI` + `base_url`) | Env: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`). |
| Storage (PRD §10) | S3-compatible object store. **MinIO** locally and in k8s; production can point `S3_ENDPOINT` at real S3 with no code change | Object key is always `{user_id}/{document_id}.pdf`. Reads/writes only through the API/worker using that constructed key — never list-bucket, never serve another user’s prefix. |
| Persistence this step | A `documents` row holding job status + extracted JSON | **No Policy table yet** (step 4 commits after review). |
| UI this step | Thin authenticated dropzone + status polling + read-only extracted fields on Home | Field editing is step 3. |

## Architecture

```
User → API (POST /api/v1/documents, PDF cookie auth)
     → MinIO put user_id/document_id.pdf
     → Postgres insert documents pending
     → Redis extract_document.send (DB 2)
     → 202 job ids

Worker consumes Redis DB 2
     → SET LOCAL app.user_id then load row
     → MinIO get only that key
     → OpenRouter LangGraph structured extract
     → Postgres status completed or failed

User → API GET /api/v1/documents/id
     → status plus extracted JSON
```

**Isolation:** RLS on `documents` (same `SET LOCAL app.user_id` pattern
as `backend/app/db.py`). Worker payload is `{document_id, user_id}`; it
sets tenant context and refuses any `storage_key` that does not start
with `{user_id}/`. User A’s `GET`/`download` of user B’s id returns
**404** (no existence leak), matching properties tests.

## Data model

New table `documents` (Alembic `0002_upload_extraction.py`):

- `id`, `user_id` (FK users, indexed)
- `original_filename`, `content_type`, `byte_size`
- `storage_key` (e.g. `{user_id}/{id}.pdf`)
- `status`: `pending` | `processing` | `completed` | `failed`
- `extracted` JSONB nullable
- `error_code`, `error_message` nullable
- `created_at`, `updated_at`

RLS policy identical in shape to `properties_isolation`. Grant `app`
DML. Extend `RLS_STATEMENTS` in `backend/app/db.py`.

**Extraction schema** (one Pydantic model, used by LangGraph structured
output, API response, and tests) matching PRD §7 Policy fields — as
*draft extraction*, not a saved policy:

- Scalars nullable: `policy_number`, `named_insured`, `broker`,
  `effective_date`, `renewal_date`, `term_premium`, `policy_fee`,
  `total_premium`, `limit_of_insurance`, `coverage_type`
- Arrays (never silently dropped): `carriers[]`, `deductibles[]`
  (`peril`, `amount`), `locations[]` (`label`, `address`)
- Per-field `confidence` 0–1 (`0` when value is null). Prompt: return
  `null` for missing fields; do not guess.

Worker does **not** create `properties` rows.

## API (`/api/v1/documents`)

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/documents` | Multipart, one or more PDFs. Auth required. Store, insert `pending`, enqueue. **202** `{ items: [DocumentOut] }` |
| `GET` | `/api/v1/documents` | List current user’s jobs |
| `GET` | `/api/v1/documents/{id}` | Job + `extracted` when complete |
| `GET` | `/api/v1/documents/{id}/file` | Stream own PDF only |

Reject non-PDF (magic `%PDF` + content type) with `UNSUPPORTED_MEDIA_TYPE`;
over **10 MiB** with `PAYLOAD_TOO_LARGE` (match k8s ingress). New error
codes: those two plus `EXTRACTION_FAILED` on the job row (GET still 200
with `status: failed`).

Nginx `frontend/nginx.conf` needs `client_max_body_size 10m` on `/api/`.

## LangGraph worker

Module layout under `backend/app/`:

- `extraction/schema.py` — Pydantic extraction model
- `extraction/graph.py` — `StateGraph`
- `queue/broker.py` — `RedisBroker(url=DRAMATIQ_REDIS_URL)` (DB 2)
- `queue/actors.py` — `@dramatiq.actor` wrapping
  `asyncio.run(run_extraction(...))`
- `storage.py` — S3 adapter (`boto3`); in-memory fake for tests

**Graph nodes:** `load_pdf` → `extract_text` (pypdf) → `select_pages` →
`extract_fields` (`ChatOpenRouter.with_structured_output`) → return
state. Persist status **outside** the graph in the actor so the graph
stays unit-testable.

**Who chooses pages:** `select_pages` is **deterministic Python**, not
the LLM and not the user. After `extract_text` has a string per page,
this node scores each page for keyword hits (`declarations`, `named
insured`, `premium`, `deductible`, `policy period`, `limit of
insurance`, and close variants). Pages above a small hit threshold
(plus immediate neighbors, so a split table is not cut in half) are
kept. If **no** page scores, fall back to the **first ~8 pages** (decls
usually sit at the front of a jacket). Only that subset is passed to
`extract_fields`. OpenRouter never sees the full 35-page ISO boilerplate
unless the fallback fires on a short doc.

This is a cost/quality heuristic from PRD §5 (Harbor Cove: decls are a
small fraction of pages). It can miss an unusual layout; step 2 accepts
that and relies on the review screen (step 3) plus `null` for missing
fields. It is **not** a second LLM “which pages matter?” call.

If combined text is below a small threshold, mark `failed` with a
plain-language “this looks scanned / no extractable text” message — do
not call the LLM on empty input.

Dramatiq: retries with backoff (max 3) for transient OpenRouter/S3
errors; validation/empty-PDF failures are non-retryable. Actor max_age
sized for a 35-page extract (order of minutes, not seconds).

Structured logs: `document_id`, `user_id`, `status`, model name —
**not** PDF text or extracted premium/address payloads.

## Frontend

On `frontend/src/pages/Home.tsx`: drag-and-drop / file picker, list
in-flight and completed jobs, poll `GET /documents/{id}` until
`completed`/`failed`, render extracted fields read-only (including
multi-deductible / multi-location / confidence). Component tests with
mocked fetch. No confirm-to-portfolio button.

## Infra

`docker-compose.yml`: existing `redis` (no new broker service), `minio`
+ one-shot bucket init (`insurance-docs`), `worker` (same API image,
`uv run dramatiq app.queue.actors --processes 1 --threads 2`).
API/worker env: `DRAMATIQ_REDIS_URL=redis://redis:6379/2`,
`S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`,
`OPENROUTER_API_KEY`, `OPENROUTER_MODEL`.

Local path stays: `docker compose up -d postgres redis minio` then
`uv run uvicorn` + `uv run dramatiq ...` + `vite`.

k8s: no RabbitMQ. Reuse Redis; MinIO+PVC; worker Deployment. Secret
fields for S3/OpenRouter. ConfigMap: `DRAMATIQ_REDIS_URL` (DB 2), model
name, bucket, endpoint.

CI: **do not** add MinIO/OpenRouter. Tests use Dramatiq `StubBroker` +
in-memory store + fake LLM (Redis service already in CI for sessions on
DB 1). No live `OPENROUTER_API_KEY` in GitHub Actions.

## Dependencies (`uv add`, called out before install)

Runtime: `python-multipart`, `dramatiq[redis]`, `langchain`,
`langgraph`, `langchain-openrouter`, `pypdf`, `boto3`.

Dev: none new required (`httpx` already present). Tests generate a tiny
synthetic PDF with pypdf — no real Harbor Cove file committed unless you
add a public fixture later.

## Tests (TDD — write these first)

Backend (priority: auth boundary + multi-deductible schema):

- Unauthenticated upload → 401
- User A cannot GET or download user B’s document → 404
- Storage key always `{user_id}/{document_id}.pdf`; worker aborts on
  prefix mismatch
- Non-PDF / oversize rejected
- Schema: missing fields are `null`; `deductibles` and `locations` are
  lists (Harbor Cove-shaped fixture JSON)
- Graph with fake chat model: given declarations-like text, returns
  structured result; empty text → failed, no LLM call
- Actor + StubBroker: `pending` → `completed` (or `failed`) on the row

Frontend: upload success starts polling; failed job shows API message;
other user’s data never appears in the list mock.

## Out of this PR

Review/confirm editor, Policy persistence, property write UI, dashboard
grouping, trends, reminders, vision OCR for scanned PDFs.
