# Insurance Tracker

CRE insurance renewal tracker. This repository is at **build-order step 1**:
accounts, sessions, and a user-scoped data boundary. See
[docs/plans/01-auth-foundation.md](docs/plans/01-auth-foundation.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker (for Postgres, Redis, and optional full-stack Compose)

## Local development

Copy environment defaults and start Postgres + Redis:

```bash
cp .env.example .env
docker compose up -d postgres redis
```

Apply migrations (uses `ADMIN_DATABASE_URL` from `.env`):

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. Vite proxies `/api` to the API on port 8000 so the
session cookie stays first-party.

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

## Kubernetes

Manifests live in `k8s/`. Copy `k8s/secret.yaml.example` to `k8s/secret.yaml`,
fill in credentials, and apply ConfigMap, Secret, Postgres, Redis, API, frontend,
and Ingress. Images are `insurance-tracker-api:latest` and
`insurance-tracker-frontend:latest` (build from `backend/Dockerfile` and
`frontend/Dockerfile`). Production can replace the in-cluster Postgres/Redis
with managed services by changing `DATABASE_URL` and `REDIS_URL`.
