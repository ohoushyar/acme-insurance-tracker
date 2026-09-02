# Step 1: Auth foundation + project bootstrap

This plan covers **PRD build-order item 1** plus the infra/tooling required
to start. Later items (extraction, review, dashboard, trends, reminders)
are out of this cycle per `development-rules.md` §3.

Password reset is **deferred** (still in V1, not this PR). The existing
mockups (`insurance-dashboard.jsx`, `insurance-dashboard-2.jsx`) stay as
design reference; this step only extracts their visual language for auth
screens.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Database | PostgreSQL 16 + SQLAlchemy 2.0 async (`asyncpg`) + Alembic | Matches async FastAPI, Kubernetes, and DB-layer tenancy. |
| Sessions | Opaque token in an **httpOnly, SameSite=Lax** cookie; session payload stored in **Redis** (not Postgres) | Instant logout without a Postgres hit on every request. Same-origin (Vite proxy / Ingress) so CSRF tokens are unnecessary in V1. |
| Password hashing | Argon2 (`argon2-cffi`) | Allowed by rules §7; current OWASP default. |
| Password reset | Not in this step | Confirmed. |
| Auth library | No FastAPI-Users; small custom handlers | Register/login/logout is a thin surface; we own the auth-boundary tests. |
| Tenancy | **Shared tables** for all users. Isolation is `user_id` + RLS, never a table/schema/database per tenant. | One `properties` table holds every tenant’s rows. Full property CRUD/UI stays in step 5. |
| Auth UI | Login + register + logged-in shell, matching mockup tokens | No dashboard port yet. |
| Python deps | **uv** (`pyproject.toml` + committed `uv.lock`) | Required by `development-rules.md` §11. |

## Target layout

```
insurance-tracker/
  README.md
  .env.example
  docker-compose.yml
  docs/plans/01-auth-foundation.md
  backend/          FastAPI app, pyproject.toml, uv.lock, Alembic, tests, Dockerfile
  frontend/         Vite + React + TS, Vitest, Dockerfile
  k8s/              Deployment/Service/ConfigMap/Secret example/Ingress
  insurance-dashboard*.jsx   unchanged design reference
```

Local path (rules §4): `docker compose up` (Postgres + Redis + API +
frontend) **or** `uv run uvicorn` + `vite` against Compose Postgres and
Redis. Both use the **same API image** as Kubernetes.

### Dev vs production (same origin, different front door)

The Vite `/api` proxy is **local development only**. Production serves a
static Vite **build** (nginx in the frontend image). One public host
(Ingress) is the front door: `/api/*` → API, `/*` → frontend.

The SPA always calls relative URLs (`/api/v1/...`) with
`credentials: "include"`. Cookie flags: `Secure` off on local HTTP, on in
production HTTPS (`SESSION_COOKIE_SECURE`).

Authenticated API calls resolve the session on every request via Redis
`GET`. Postgres is used on login/register (password verify) and on tenant
data queries (RLS). Logout is `DEL` the Redis key + clear the cookie.

**Redis session shape**

- Cookie value: unguessable random token.
- Key: `session:{sha256(token)}`
- Value: JSON `{ user_id, email, created_at }`
- TTL: **7 days** from login/register (fixed). Cookie `Max-Age` matches.
- Redis restart with no persistence logs everyone out — acceptable for V1.

## Data model (this step only)

```
users       id, email (unique), password_hash, created_at
properties  id, user_id, label, created_at

Redis       session:{sha256(token)} -> { user_id, email, created_at }  TTL 7d
```

**Shared-table multi-tenancy:** all tenants use the same physical tables.
Isolation is `user_id` + `SET LOCAL app.user_id` + RLS
`USING (user_id = current_setting('app.user_id')::uuid)`.

## API (step 1)

- `POST /api/v1/auth/register` `{ email, password }` → 201 + session cookie
- `POST /api/v1/auth/login` → 200 + session cookie
- `POST /api/v1/auth/logout` → 204, clear cookie, `DEL` Redis session key
- `GET /api/v1/auth/me` → `{ id, email, created_at }` (401 if anonymous)
- `GET /api/v1/properties` / `GET /api/v1/properties/{id}` → 404 for other
  users’ rows (no existence leak)

Error body: `{ "error": { "code": "...", "message": "..." } }`

Codes: `VALIDATION_ERROR`, `EMAIL_TAKEN`, `INVALID_CREDENTIALS`,
`UNAUTHENTICATED`, `NOT_FOUND`.

## Out of this PR

Password reset, email, PDF upload/extraction, review UI, property
write/delete UI, dashboard grouping, trends, reminders, SSO.
