# Dev demo fixtures

Local-only synthetic portfolios so a contributor can log in and walk every
shipped surface (auth through reminders) without uploading PDFs.

## Decisions

| Topic | Choice | Why |
|---|---|---|
| Load command | `make load-fake-data` | Starts Postgres/MinIO, migrates, seeds. Idempotent. |
| Reminders | Dates only — no `reminders` rows | `GET /api/v1/reminders` upserts 10/30/60 from `renewal_date`. |
| Prior-year series | `effective_date` set, `renewal_date` omitted | Past renewals would flood Urgent as “days past due.” |
| `storage_key` | `{user_id}/{document_id}.pdf` | Matches `document_storage_key`. |
| Isolation | Wipe the five demo emails only | Other local users stay. |
| Tests | None new | Static data, not product behavior. |

## Accounts

Shared password: `demo-pass-1`

| Email | Persona |
|---|---|
| `casey@example.com` | Mixed CRE — full showcase + Harbor Cove |
| `alex@example.com` | Harbor Retail |
| `jordan@example.com` | Sundale Multifamily |
| `morgan@example.com` | Fenmore Industrial |
| `riley@example.com` | Meridian Office |

Primary walkthrough: **casey**.

## What the seed writes

- Users (Argon2 hash of `demo-pass-1`)
- Properties (`label`, `address`, `stated_value`) and `policy_properties`
- Stub `documents` (`reviewed` for saved policies; casey also has `completed` + `failed`)
- Policies with `renewal_offset_days` applied as `today + offset`
- `policy_series` for Harbor Cove (2022–current, YoY ≥10%), Harbor Ave (two years, ≥10%), Coldwater (under 10%)
- Optional tiny PDF in MinIO; seed continues if upload fails

Does **not** insert reminder rows. First visit to `/reminders` materializes unread 10/30/60 items.

## How to load

From the repo root (needs Docker for Postgres/MinIO):

```bash
make load-fake-data
```

Equivalent:

```bash
cd backend && uv run python scripts/seed_demo.py
```

Refuses to run unless `ADMIN_DATABASE_URL` points at localhost, 127.0.0.1, or Compose `postgres`. Never use this against production.

## Walkthrough

1. Log in as `casey@example.com` / `demo-pass-1`
2. Home — urgency groups, stats, YoY badges
3. Reminders — unread 10/30/60; mark read
4. Harbor Cove policy detail — deductibles, chart, source document
5. Properties — unattached Larkspur Parcel
6. Uploads — failed job + Review/confirm draft
7. Profile — password change
8. Log in as `alex@example.com` — different portfolio, reminder badge still set

## Files

- [backend/fixtures/demo_portfolios.json](../../backend/fixtures/demo_portfolios.json)
- [backend/scripts/seed_demo.py](../../backend/scripts/seed_demo.py)
