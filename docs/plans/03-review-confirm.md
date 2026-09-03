# Step 3: Review/confirm screen

This plan covers **PRD Section 8 item 3** only. Upload/extraction already
exists ([docs/plans/02-upload-extraction.md](02-upload-extraction.md)).
**No `policies` table** — that is step 4.

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Confirm destination | `POST /api/v1/documents/{id}/confirm` writes edited `ExtractedPolicy` to `documents.extracted` and sets `status=reviewed` | Policy rows wait for step 4. Button copy is **Looks right — confirm**. |
| Cancel | Discard local edits; LLM JSON on the row is unchanged | No draft autosave. |
| Re-confirm | Allowed on `reviewed` documents until step 4 | Lets the user fix a mistake without a Policy lock. |
| Missing fields | Do not block confirm. Warn when any scalar is null or confidence is below **0.7** | Silent drop is the failure mode the PRD forbids; blocking confirm is not. |
| Edited confidence | Client sets **1.0** on change (scalars and list collections). Null scalars still force **0** via the existing validator | Distinguishes user-corrected values from extraction guesses. |
| `Deductible.amount` | `str \| None` | Step 2 used `Decimal`, which cannot store Harbor Cove-style values (`"3.00% Cal. Yr. Aggregate (min $50,000)"`). Premiums/limits stay `Decimal`. |
| UI | Full-page route `/documents/:id/review` | Matches `insurance-dashboard-2.jsx` `Review` (not a slide-up). |
| PDF | **View original PDF** link to `GET /file` with `Content-Disposition: inline` | No side-by-side viewer. |
| Confirm money fields | `ConfirmExtractedPolicy` with strict whole-string amounts (`$185,000.00` OK). Junk or parenthetical text → **422**, not silent null/rewrite | LLM extraction still uses lenient `ExtractedPolicy` (unparseable → null). Review user edits must not drop or rewrite premiums. |

## Architecture

```
Home (completed job)
  → /documents/{id}/review
  → GET /api/v1/documents/{id}
  → edit scalars and lists locally
  → POST /api/v1/documents/{id}/confirm  { ConfirmExtractedPolicy }
  → documents.extracted JSON + status reviewed
  → navigate Home
```

**Isolation (unchanged):** `get_current_user` + `get_tenant_db` + RLS.
User A confirming user B’s id returns **404**. Unauthenticated → 401.

## Data model

`documents.status` check constraint (Alembic `0003_review_confirm.py`):

`pending | processing | completed | failed | reviewed`

Worker still only writes `completed` / `failed`. Confirm is the only path
to `reviewed`.

LangGraph uses `ExtractedPolicy` (lenient money: junk → null). Confirm uses
`ConfirmExtractedPolicy` (strict money: junk → 422). `Deductible.amount` is a
string so percentage/narrative deductibles are not dropped. Empty strings on
optional text fields coerce to `null`.

## API

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/documents/{id}/confirm` | Auth required. Body: `ConfirmExtractedPolicy`. Only `completed` or `reviewed` with non-null `extracted`. Persist JSON, `status=reviewed`, return `DocumentOut`. |
| `GET` | `/api/v1/documents/{id}/file` | `Content-Disposition: inline` so the review link can open the PDF in a tab. |

Reject `pending` / `processing` with **409** `CONFLICT` (“This document is
still extracting.”). Reject `failed` with **409** (“Extraction failed —
upload again.”). Cross-user → **404** `NOT_FOUND`. Invalid dates/decimals
→ **422** `VALIDATION_ERROR`.

## Frontend

- Route: `/documents/:id/review` → `Review` (auth redirect like Home).
- Shared `Shell` in `frontend/src/components/Shell.tsx`.
- Editable scalars (dates as `type="date"`, money as text) and add/remove
  lists for carriers, deductibles, and locations.
- Confidence next to each field; below 0.7 (and null scalars) use
  `--urgent`. Warning copy does not block confirm.
- Sparse/malformed `extracted` JSON is normalized on load (missing
  `confidence` and arrays default) so Review cannot white-screen.
- Cancel returns home with no write. Confirm `POST`s then navigates home.
- Home job cards are compact: filename, status, named insured / policy
  number, **Review extracted fields** link. No full field grid on Home.

## Tests

Backend (auth boundary + multi-deductible): unauthenticated 401; cross-user
404; confirm persists list edits and narrative amounts; re-confirm updates
JSON; pending/failed 409; empty string → null; invalid date/premium 422.

Frontend (`frontend/src/review.test.tsx`): fields + confidence; low
confidence distinguished; edit/add/remove deductible then confirm lands
on Home as `reviewed`; cancel does not POST; unauthenticated review URL
→ login; Home shows the review CTA instead of the full grid.

## Out of this PR

Policy / `policy_history` tables, property CRUD, dashboard grouping, YoY,
reminders, vision OCR, draft autosave, side-by-side PDF, password reset.
