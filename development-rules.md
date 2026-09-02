# Development Rules — CRE Insurance Renewal Tracker

These rules govern how this project gets built. They apply to any
contributor — human or AI-assisted (e.g. Claude Code) — working in
this repo.

## 1. Tech stack

- **Frontend**: React with **Vite** (dev server + build tooling).
  Kept lightweight — no meta-framework (e.g. Next.js) unless a real
  need emerges (SSR, file-based routing at scale); a single-page app
  with React Router (if/when routing is needed) is the default
  assumption.
- **Backend**: Python with **FastAPI**. Python dependencies and
  virtualenvs are managed with **uv** (see Rule 11) — not pip,
  Poetry, or a hand-maintained `requirements.txt` as the source of
  truth.
  - Async-first where I/O-bound (DB calls, PDF/LLM extraction calls)
    — FastAPI's main advantage here, so use `async def` route
    handlers and an async DB driver rather than mixing sync and async
    styles.
  - Pydantic models (already core to FastAPI) double as the request/
    response schema layer — use them directly for the extraction
    schema in PRD Section 7, don't create a parallel schema
    definition.
  - Auto-generated OpenAPI docs (`/docs`) come free with FastAPI —
    keep route definitions clean enough (proper response models,
    status codes) that these docs stay useful, rather than bypassing
    them with generic/untyped responses.
- Once chosen, stay consistent — don't mix frameworks for the same
  concern (e.g. don't introduce a second HTTP client pattern or a
  second state-management approach on the frontend without a reason
  called out in a step's plan).

## 2. Test-driven development (TDD)

- Tests are written **before** the implementation code they test, for
  every new piece of functionality — not added afterward to pad
  coverage.
- Cycle: write a failing test → write the minimum code to pass it →
  refactor → repeat.
- No feature or bugfix is considered complete without a corresponding
  test that fails without the fix and passes with it.
- Both frontend and backend need tests:
  - Backend: unit tests for business logic (extraction schema
    validation, deductible/multi-property handling, YoY calculation),
    integration tests for API endpoints, and auth boundary tests
    specifically (a logged-in user cannot fetch another user's data —
    see PRD Section 11).
  - Frontend: component tests for the review/confirm screen, dashboard
    list/grouping logic, and trend chart rendering.
- Test coverage is not itself the goal — a passing test suite that
  doesn't actually exercise the auth boundary or the multi-deductible
  data model (the two things most likely to silently break) is a
  false signal. Prioritize tests around those two risk areas
  explicitly.

## 3. Plan-then-implement workflow

- For each item in the PRD's build order, **produce a written plan
  first** — what will be built, the approach, any new dependencies,
  and how it'll be tested — and **wait for explicit confirmation**
  before writing implementation code.
- Do not bundle multiple build-order steps into one plan/confirmation
  cycle unless asked to. One step, one plan, one confirmation, then
  implement.
- If a step turns out to need a decision the PRD left open (see PRD
  Section 10, "Open questions"), surface that decision as part of the
  plan rather than picking silently and moving forward.

## 4. Infrastructure

- Backend runs on **Kubernetes**.
- Application config (API keys, DB connection strings, secrets) is
  injected via Kubernetes Secrets/ConfigMaps — never hardcoded or
  committed to the repo, including in test fixtures.
- Local development should not require a live Kubernetes cluster —
  provide a local-dev path (e.g. Docker Compose, or simply running
  `uv run uvicorn` for FastAPI and `vite dev` for the frontend
  directly against a local/dockerized DB) that mirrors the same
  containers used
  in the Kubernetes deployment, so contributors aren't blocked without
  cluster access. Reconciling the two setups is part of the
  infrastructure plan under Rule 3, not an afterthought.

## 5. Code standards

- **Python**: follow PEP 8; format with `black`; lint with `ruff`
  (stay consistent — do not add flake8). Run both via `uv run`
  (e.g. `uv run black`, `uv run ruff`). Type hints are required on
  function signatures for new code.
- **React**: functional components with hooks (matches the existing
  design-reference mockup); format with `prettier`; lint with
  `eslint`.
- Naming, structure, and formatting should match whatever is
  established in the repo once the first implementation lands — don't
  introduce a second style partway through.
- No commented-out dead code left in commits. No `console.log`/`print`
  debug statements left in committed code.

## 6. Version control & review

- Small, single-purpose commits with descriptive messages (what
  changed and why, not just "fix bug").
- One build-order step (Rule 3) roughly corresponds to one branch/PR,
  not a giant PR spanning several steps.
- Every PR includes its tests — code without tests is not
  submitted for review, per Rule 2.

## 7. Security & data handling

- Enforce the per-user data boundary (PRD Section 7) at the
  database/query layer, not only in API route handlers or the UI.
- Passwords are hashed (e.g. bcrypt/argon2), never stored or logged in
  plaintext.
- Uploaded policy documents and extracted data are sensitive
  (financial/business data) — treat storage and access the same as
  the per-user auth boundary: no shared buckets/paths without a
  user-scoped prefix or equivalent isolation.
- No secrets, API keys, or real user/policy data in test fixtures or
  example files committed to the repo. Use synthetic fixtures (the
  Harbor Cove-style test document is fine as a fixture since it's
  already public).

## 8. API design

- RESTful conventions for endpoints unless a specific case argues
  otherwise (call it out in the plan per Rule 3).
- Consistent error response shape across all endpoints (status code +
  machine-readable error code + human-readable message).
- Version the API from the start (e.g. `/api/v1/...`) even though
  there's only one version now — cheaper to do upfront than to
  retrofit.

## 9. Error handling & logging

- Extraction failures (Section 4/5 of the PRD — missing fields, low
  confidence) must be surfaced to the user, not swallowed — this
  connects directly to the required review/confirm step.
- Structured logging on the backend (not bare `print`), with enough
  context to debug an extraction or auth issue without exposing
  sensitive policy data in logs.
- User-facing errors are plain-language and actionable; internal
  errors (stack traces, DB errors) never reach the frontend response.

## 10. Documentation

- Each build-order step's plan (Rule 3) doubles as its documentation —
  keep these plans in the repo (e.g. a `/docs/plans/` folder) rather
  than only in chat history, so the reasoning behind decisions isn't
  lost.
- Update the PRD itself when a build step surfaces a decision that
  changes scope or the data model — the PRD should stay the source of
  truth, not drift out of date while plans move ahead of it.
- A minimal `README.md` (setup, how to run tests, how to run locally)
  is expected from the first commit, not deferred to the end.

## 11. Dependency management

- New dependencies (either stack) are called out explicitly in the
  step's plan (Rule 3) before being added — no silent addition of
  packages during implementation.
- Prefer well-maintained, widely-used libraries over writing custom
  solutions for solved problems (auth, PDF handling, charting), but
  justify the choice briefly in the plan.
- **Python: uv is required.** Use Astral's `uv` for the backend
  environment, installs, and lockfile. Do not introduce pip, Poetry,
  pip-tools, or a committed `requirements.txt` as a parallel source
  of truth.
  - `pyproject.toml` declares dependencies; `uv.lock` is committed
    and is the lockfile.
  - Add packages with `uv add` / `uv add --dev`; install with
    `uv sync`; run tools and the app with `uv run` (e.g.
    `uv run pytest`, `uv run uvicorn`, `uv run alembic`).
  - Docker/Kubernetes images install from `uv.lock` (copy
    `pyproject.toml` + `uv.lock`, then `uv sync --frozen`) so
    deployed deps match local.
- **Frontend** stays on its own toolchain (npm or equivalent via
  `package.json` / lockfile). uv is the Python manager only.
