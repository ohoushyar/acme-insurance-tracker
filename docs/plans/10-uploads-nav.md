# Step 10: Uploads nav page

This plan covers a UI information-architecture split: upload +
extraction status leave the portfolio dashboard. No API or schema
change. Confirm still returns to `/` (saved policies).

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Route | `/uploads` | Distinct from `/documents/:id/review`. |
| Nav | **Uploads** between Portfolio and Properties | Intake is a primary action. |
| Home empty | “No saved policies yet” + link to `/uploads` | Dropzone no longer lives on Home. |

## Architecture

```
Sidebar Uploads
  → /uploads dropzone + job list + 2s poll
  → Review → /documents/:id/review → confirm → /
Home
  → GET /api/v1/policies + properties only
```

## Frontend

- [frontend/src/pages/Uploads.tsx](../../frontend/src/pages/Uploads.tsx):
  dropzone, `listDocuments`, merge + poll, `JobCard`.
- [frontend/src/pages/Home.tsx](../../frontend/src/pages/Home.tsx):
  stats + urgency groups only.
- [frontend/src/components/Shell.tsx](../../frontend/src/components/Shell.tsx):
  nav **Uploads**.

## Tests

[frontend/src/documents.test.tsx](../../frontend/src/documents.test.tsx)
renders `/uploads`. Dashboard tests: Home has no dropzone; empty Home
links to Uploads.

## PRD note

Upload and extraction status live on **Uploads**, not the portfolio list.
