# Development

This document explains the development requirements and setups.

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker (for Postgres, Redis, MinIO, and optional full-stack Compose)
- An [OpenRouter](https://openrouter.ai/) API key for live extraction (not
  required for tests; CI uses a fake LLM)

For **cluster** deploy (optional): a local Kubernetes (Rancher Desktop
is enough), `kubectl`, [Terraform](https://www.terraform.io/) 1.5+, and
the AWS CLI (production).

## Local Development

Copy environment defaults and start Postgres, Redis, MinIO, and Mailpit:

```bash
cp .env.example .env
# Set OPENROUTER_API_KEY in .env for live extraction.
docker compose up -d postgres redis minio minio-init mailpit
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

Mailpit (local SMTP inbox) is at http://localhost:8025. Register and password
reset enqueue Dramatiq jobs; the worker sends mail. Verify the address before
renewal reminder emails go out. Staging/production use Amazon SES (IRSA) instead
of Mailpit — set `ses_from_address` and `app_public_url` in the app tfvars, add
the DKIM records Terraform outputs, and request SES production access (leaving
the sandbox is not automated).

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
`api` service. Vite is not in the production path.

Compose also runs MinIO (S3-compatible PDF store), Mailpit, and a Dramatiq
worker on Redis DB 2. Set `OPENROUTER_API_KEY` in the environment for live
extraction. The worker also sends verification, password-reset, and renewal
emails. An hourly `scan_reminder_emails` actor re-enqueues itself; it does not
use a Kubernetes CronJob.

## Deployment

[docs/deployment.md](docs/deployment.md)