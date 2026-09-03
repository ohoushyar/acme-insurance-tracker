# Step 6: Repository and service layers

This plan is a layering refactor, not a PRD feature. FastAPI routers become
HTTP adapters only. Application use cases live in services. All SQLAlchemy
reads and writes live in repositories.

No new Python dependencies. No schema or API contract changes. Existing
HTTP integration tests stay the contract.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Layers | Router → service → repository | Routers must not load rows; services own use cases and `AppError`; repositories own SQLAlchemy. |
| Style | Function modules, not classes | Matches `sessions.py` / `policy_mapping.py`. No generic `Repository[T]` or unit-of-work class. |
| Session | Inject `AsyncSession` in the router, pass it down | FastAPI `get_db` / `get_tenant_db` already commit/rollback. |
| Workers | Dramatiq actors call repositories | They are not HTTP adapters; they still must not inline `select()`. |
| Mapping | Keep `policy_mapping.py` for ORM → API models | Query helpers move out; `apply_extracted` / `*_to_out` stay. |

## Layering

```
router (HTTP, cookies, status codes)
  → service (use case, AppError)
    → repository (select / add / delete / flush)
      → PostgreSQL
```

Queue workers call repositories directly.

Routers may type-hint `AsyncSession` (`sqlalchemy.ext.asyncio` only). They
must not import `sqlalchemy.select`, DML constructs, or `sqlalchemy.exc`,
and must not call `session.execute` / `session.add` / `session.delete`.

Repositories return ORM models or `None` / collections. They do not raise
`AppError`. Persistence conflicts (e.g. duplicate email) use a small
repository exception that the service maps to `AppError`.

Per-user isolation stays in repository `user_id` filters in addition to RLS.

## Target layout

```
backend/app/repositories/
  users.py
  documents.py
  policies.py
  properties.py
  policy_properties.py
  transactions.py
backend/app/services/
  auth.py
  documents.py
  policies.py
  properties.py
```

## Tests

- Router import guard: `app/routers/*.py` must not import SQLAlchemy query/DML/exc APIs.
- Repository tests: `users.get_by_email` / `create` / duplicate; owned get returns `None` for another user’s id.
- Service tests: invalid login, duplicate register, not-found get, document confirm conflict.
- Existing HTTP tests stay green.

## Out of this change

Password reset, RLS/schema changes, session-cookie changes, API route
changes, a repository/service framework, class-based unit of work, moving
Redis session helpers (`app/sessions.py`).
