# Insurance Tracker

CRE insurance renewal tracker. This repository is at **build-order step 4**:
accounts, sessions, a user-scoped data boundary, PDF upload/extraction, an
editable review/confirm screen, and confirmed policies stored per user. See
[docs/plans/01-auth-foundation.md](docs/plans/01-auth-foundation.md),
[docs/plans/02-upload-extraction.md](docs/plans/02-upload-extraction.md),
[docs/plans/03-review-confirm.md](docs/plans/03-review-confirm.md), and
[docs/plans/04-confirmed-policies.md](docs/plans/04-confirmed-policies.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker (for Postgres, Redis, MinIO, and optional full-stack Compose)
- An [OpenRouter](https://openrouter.ai/) API key for live extraction (not
  required for tests; CI uses a fake LLM)

## Local development

Copy environment defaults and start Postgres, Redis, and MinIO:

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env for live extraction.
docker compose up -d postgres redis minio minio-init
```

Apply migrations (uses `ADMIN_DATABASE_URL` from `.env`):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal, the Dramatiq worker (Redis **DB 2**; sessions stay on
DB 0):

```bash
cd backend
uv run dramatiq app.queue.actors --processes 1 --threads 2
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the API on port 8000 so the
session cookie stays first-party.

Uploaded PDFs go to MinIO (`insurance-docs` bucket) under
`{user_id}/{document_id}.pdf`. From the host, MinIO is at
http://localhost:9100 (console http://localhost:9101). Extraction jobs
are queued on Redis DB 2 (`DRAMATIQ_REDIS_URL`).

## Tests

```bash
# backend (needs Compose Postgres + Redis)
cd backend && uv run pytest

# frontend
cd frontend && npm test
```

Lint and format checks:

```bash
cd backend && uv run ruff check app tests alembic && uv run black --check app tests alembic
cd frontend && npm run lint && npm run format:check
```

GitHub Actions runs the same lint, tests, frontend production build, and Docker image builds on every pull request and on pushes to `main`.

## Docker Compose (API + frontend images)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- API docs: http://localhost:8000/docs

The frontend image is nginx + a Vite production build. It proxies `/api` to the
`api` service. Kubernetes Ingress does the same job in a cluster; Vite is not
in the production path.

Compose also runs MinIO (S3-compatible PDF store) and a Dramatiq worker on
Redis DB 2. Set `OPENROUTER_API_KEY` in the environment for live extraction.

## Kubernetes

Manifests live in `k8s/`. Copy `k8s/secret.yaml.example` to `k8s/secret.yaml`,
fill in credentials, and apply ConfigMap, Secret, Postgres, Redis, MinIO, API,
worker, frontend, and Ingress. Images are `insurance-tracker-api:latest` and
`insurance-tracker-frontend:latest` (build from `backend/Dockerfile` and
`frontend/Dockerfile`). The worker uses the API image with
`dramatiq app.queue.actors`. Production can replace the in-cluster
Postgres/Redis/MinIO with managed services by changing `DATABASE_URL`,
`REDIS_URL`, `DRAMATIQ_REDIS_URL`, and `S3_ENDPOINT`.
