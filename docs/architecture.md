# Architecture

Insurance Tracker is a small multi-tenant app: a broker or owner uploads
policy PDFs, reviews extracted fields, and tracks renewals for their own
portfolio. One login owns one portfolio. Data never crosses users.

## Development

Vite proxies `/api` to the API so the session cookie stays first-party.
Postgres, Redis, MinIO, and Mailpit run in Compose; the API and worker
usually run on the host.

```mermaid
flowchart TB
  Browser -->|"http://localhost:5173"| Vite["Vite + React SPA"]
  Vite -->|"proxy /api"| API["FastAPI :8000"]

  subgraph compose["Docker Compose"]
    PG["PostgreSQL + RLS"]
    Redis["Redis<br/>sessions DB 0, Dramatiq DB 2"]
    MinIO["MinIO — policy PDFs"]
    Mailpit["Mailpit SMTP"]
  end

  API --> PG
  API --> Redis
  API --> MinIO
  Redis --> Worker["Dramatiq worker"]
  Worker --> PG
  Worker --> MinIO
  Worker --> Mailpit
  Worker --> OpenRouter["OpenRouter LLM"]
```

## Production

Staging and production are the same shape on one shared EKS cluster
(namespace per env). Cluster deploy is Terraform. CloudFront is the
HTTPS host so `/` and `/api` stay same-origin.

```mermaid
flowchart TB
  Browser --> CF["CloudFront"]
  CF -->|"/"| Web["S3 SPA bucket"]
  CF -->|"/api"| ALB["ALB"]

  subgraph eks["EKS namespace — production"]
    API1["api pod"]
    API2["api pod"]
    W1["worker pod"]
    W2["worker pod"]
    PG["postgres pod<br/>StatefulSet, 10Gi PVC"]
    RD["redis pod"]
  end

  ALB --> API1
  ALB --> API2
  API1 --> PG
  API2 --> PG
  API1 --> RD
  API2 --> RD
  W1 --> PG
  W2 --> PG
  W1 --> RD
  W2 --> RD
  API1 --> Docs["S3 docs bucket"]
  API2 --> Docs
  W1 --> Docs
  W2 --> Docs
  W1 --> SES["Amazon SES"]
  W2 --> SES
  W1 --> OR["OpenRouter LLM"]
  W2 --> OR
```

API and worker Deployments run two pods each. Postgres is a StatefulSet
(one replica); Redis is a Deployment (one replica). Pods reach S3 and
SES through IRSA on the `insurance-tracker` ServiceAccount. A migrate
Job runs Alembic once per deploy before the API pods start. Images come
from ECR.

## Components

**React SPA.** Vite + React Router. The browser talks only to relative
`/api/v1/...` with cookies. Pages cover login, uploads, review/confirm,
the portfolio dashboard, properties, policy detail, reminders, and
profile. Vite proxies `/api` in development. AWS serves the built SPA
from S3 via CloudFront.

**FastAPI API.** HTTP adapter only: cookies, status codes, Pydantic
schemas. Routers call services; services own use cases (auth, confirm
upload, reminders); repositories own SQLAlchemy. Workers skip HTTP but
still go through repositories. Auth is a Redis-backed session cookie,
not JWTs.

**PostgreSQL.** Source of truth for users, properties, documents,
policies, year-over-year series, and reminders. Row-level security
ties every owned row to `app.user_id`. Repository queries also filter
by `user_id` so a missed `WHERE` still cannot leak another user's data.

**Redis.** Two databases on one instance: DB 0 holds hashed session
tokens; DB 2 is the Dramatiq broker. Sessions last seven days.

**Object storage (MinIO / S3).** Uploaded PDFs live at
`{user_id}/{document_id}.pdf`. Local and Kubernetes use MinIO; AWS uses
a real S3 bucket with IRSA (no static keys). The worker refuses keys
that are not owned by the job's user.

**Dramatiq worker.** Pulls jobs from Redis. It extracts policy
declarations (LangGraph + LLM into a fixed JSON schema), sends
verification / password-reset / renewal emails, and hourly re-enqueues
a reminder scan. Extraction is async so the upload request can return
immediately; the user reviews fields before anything is committed to
the portfolio.

**OpenRouter.** The LLM behind extraction (`openai/gpt-4o-mini` by
default). The graph selects declaration-like pages, asks for structured
output, and stores `null` rather than guessing. Tests use a fake LLM;
CI never calls the live API.

**Email (Mailpit / SES).** Local SMTP goes to Mailpit
(http://localhost:8025). Staging and production send through Amazon SES
when `ses_from_address` is set. Renewal emails only go to verified
addresses.

**Front door.** Development uses Vite's `/api` proxy. Production uses
CloudFront (`/` → S3, `/api` → ALB → api pods).
