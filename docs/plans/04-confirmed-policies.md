# Step 4: Confirmed policy storage

This plan covers **PRD Section 8 item 4** only: store confirmed policies,
scoped to the logged-in user, structured per PRD Section 7. Review/confirm
already writes `documents.extracted` and `status=reviewed`
([docs/plans/03-review-confirm.md](03-review-confirm.md)).
**No property CRUD, dashboard grouping, policy detail route, YoY, or
reminders.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Insert path | `POST /api/v1/documents/{id}/confirm` upserts a `policies` row keyed by `source_document_id` | Confirm stays the only write. Independent `POST /policies` is step 5. |
| Re-confirm | Updates the same policy in place | Unique `source_document_id` prevents duplicates. Review remains the editor until step 5 adds PATCH. |
| Property linking | Do not auto-create `properties` from locations | Avoids duplicates on next year’s upload; matching is PRD §10. Locations stay JSONB on the policy. `propertyIds[]` waits for step 5. |
| PolicyHistory | Defer to step 8 | Linking heuristic is an open question. Policies keep `policy_number`, `coverage_type`, `effective_date` for later matching. |
| UI | Thin **Saved policies** list on Home | Not urgency-grouped (step 6). No `/policies/:id` page (step 7). Button copy stays **Looks right — confirm**. |
| Dependencies | None new | Reuse existing Pydantic extraction schema. |

## Architecture

```
Home (completed job)
  → /documents/{id}/review
  → POST /api/v1/documents/{id}/confirm  { ConfirmExtractedPolicy }
  → documents.extracted JSON + status reviewed
  → upsert policies by source_document_id
  → DocumentOut + policy_id
  → navigate Home
  → GET /api/v1/policies
```

**Isolation (unchanged):** `get_current_user` + `get_tenant_db` + RLS.
User A listing or fetching user B’s policy id returns **404**.
Unauthenticated → 401. RLS must still hide rows if a handler forgets
`WHERE user_id`.

## Data model

Alembic `0004_confirmed_policies.py`. `policies` table:

- `id`, `user_id` (FK users, indexed)
- `source_document_id` (FK documents, unique) — one document, one policy
- Nullable scalars: `policy_number`, `named_insured`, `broker`,
  `effective_date`, `renewal_date`, `term_premium`, `policy_fee`,
  `total_premium`, `limit_of_insurance`, `coverage_type`
- Money: `Numeric`. Dates: `Date`.
- JSONB: `carriers`, `deductibles` (`{peril, amount}` with string amount),
  `locations` (`{label, address}`), `extraction_confidence`
- `created_at`, `updated_at`

Index `renewal_date` for step 6. Text columns for names/coverage so confirm
cannot 500 on long commercial named-insured strings. Backfill policies from
existing `reviewed` documents with non-null `extracted`.

`ExtractedPolicy` / `ConfirmExtractedPolicy` remains the field contract.
One helper maps that model onto the `policies` row.

## API

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/documents/{id}/confirm` | Existing 409/404/422 rules. Also upsert `policies`. Return `DocumentOut` with `policy_id`. |
| `GET` | `/api/v1/policies` | Current user’s policies, newest `created_at` first. |
| `GET` | `/api/v1/policies/{id}` | One row or **404**. |

`PolicyOut`: identity fields plus `ExtractedPolicy` fields (money as JSON
strings). No create/update/delete policy endpoints.

## Frontend

- `Policy` type, `listPolicies()`, `getPolicy()`. `DocumentJob.policy_id`.
- Home fetches policies and shows a **Saved policies** section (named
  insured, policy number, coverage type, renewal date, total premium,
  location labels). Lede copy: confirm now saves into the portfolio.
- No new routes.

## Tests

Backend (auth boundary + multi-deductible): unauthenticated 401; cross-user
404; RLS without application filter; confirm inserts Harbor Cove-shaped
deductibles and locations; re-confirm updates in place; confirm is the only
insert path; confirm response includes `policy_id`.

Frontend: confirm then Home lists the saved policy; other-user policies
never appear in the mock.

## Out of this PR

Property create/edit/delete and attach-to-policy, `policy_properties` M2M,
PolicyHistory / YoY matching, dashboard urgency groups, policy detail page,
PATCH/DELETE policies, vision OCR, password reset.
