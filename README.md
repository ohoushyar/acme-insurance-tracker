# Insurance Tracker

CRE insurance renewal tracker. See [docs/plans/](docs/plans/) for the
build-order writeups. Cluster deploy is documented in
[docs/plans/10-deployment.md](docs/plans/10-deployment.md).

## Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Node.js 22+
- Docker (for Postgres, Redis, MinIO, and optional full-stack Compose)
- An [OpenRouter](https://openrouter.ai/) API key for live extraction (not
  required for tests; CI uses a fake LLM)

For **cluster** deploy (optional): a local Kubernetes (Rancher Desktop
is enough), `kubectl`, [Terraform](https://www.terraform.io/) 1.5+, and
the AWS CLI (production).

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

## Demo accounts (local only)

Load five synthetic portfolios (properties, policies, YoY series, upload jobs):

```bash
make load-fake-data
```

Password for all five: `demo-pass-1`

| Email | Notes |
|---|---|
| `casey@example.com` | Full walkthrough (Harbor Cove, urgency buckets, YoY, reminders, review job) |
| `alex@example.com` | Harbor retail portfolio |
| `jordan@example.com` | Sundale multifamily |
| `morgan@example.com` | Fenmore industrial |
| `riley@example.com` | Meridian office |

Re-running wipes only these emails and reloads them. Do not run the seed against a non-local database. See [docs/plans/13-dev-demo-fixtures.md](docs/plans/13-dev-demo-fixtures.md).

Walkthrough: log in as casey → Home (groups, stats, YoY badges) → Reminders → Harbor Cove detail + chart → Properties → Uploads (failed job + Review) → Profile → log in as alex.

Uploaded PDFs go to MinIO (`insurance-docs` bucket) under
`{user_id}/{document_id}.pdf`. From the host, MinIO is at
http://localhost:9100 (console http://localhost:9101). Extraction jobs
are queued on Redis DB 2 (`DRAMATIQ_REDIS_URL`).

`make serve` and `make frontend` wrap the same inner loop.

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

Compose also runs MinIO (S3-compatible PDF store) and a Dramatiq worker on
Redis DB 2. Set `OPENROUTER_API_KEY` in the environment for live extraction.

## Local Kubernetes

One pod runs API, Dramatiq, Postgres, Redis, MinIO, and nginx on the
cluster `kubectl` currently points at (Rancher Desktop).

```bash
# Kubernetes enabled in Rancher Desktop, then:
kubectl cluster-info
make deploy-local
kubectl port-forward svc/insurance-tracker 8080:80
# http://localhost:8080
make destroy-local
```

`destroy-local` removes the workload only; it does not quit Rancher
Desktop. Requires `kubectl`, Terraform, and Docker (or the Rancher
Desktop docker/nerdctl CLI). If the cluster uses containerd, `nerdctl`
must be on `PATH` (Rancher Desktop: `~/.rd/bin/nerdctl`).

## AWS (staging / production)

Shared EKS cluster; per-env namespace, S3 buckets (SPA + PDFs), and
CloudFront. API and worker run at `replicas=2`. Postgres and Redis stay
in-cluster (1 replica).

```bash
make deploy ENV=staging
make deploy ENV=production
make destroy-aws ENV=staging
make destroy-aws ENV=production CONFIRM=yes
# optional: also tear down the shared EKS/VPC after both envs are gone
make destroy-aws ENV=staging DESTROY_CLUSTER=yes
```

Copy `infra/terraform/aws/platform/terraform.tfvars.example` and
`infra/terraform/aws/app/staging.tfvars.example` (or `production`) to
`*.tfvars` if you need non-default region or cluster name. Pass
`OPENROUTER_API_KEY` via `.env` or the environment.

Existing YAML under `k8s/` is a reference only; Terraform owns applied
resources.
