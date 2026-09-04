# Step 7: Policy detail view

This plan covers **PRD Section 8 item 7** only: a read-only view of all
confirmed fields for one policy. Dashboard grouping is step 6
([docs/plans/06-dashboard-list.md](06-dashboard-list.md)); edit/delete stay as
built in step 5. **No YoY, PolicyHistory, charts, slide-up panel, or
`POST /policies`.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Detail UX | Dedicated `/policies/:id` page (not slide-up) | Deep-linkable; step 5 foreshadowed this route; edit stays at `/policies/:id/edit`. |
| Data source | Existing `GET /api/v1/policies/{id}` + `listProperties` for attached labels | No new API. |
| Fields shown | Full `PolicyOut`: scalars, carriers, deductibles, locations, attached properties, confidence summary, source-document link | PRD: “all extracted fields for one policy.” |
| YoY / prev premium | Omit | Step 8. |
| Home navigation | **View** link on cards → detail; keep Edit + Delete on cards | Parity with step 5 actions. |
| Delete on detail | Two-step confirm; on success navigate Home | Same pattern as Home cards. |
| Dependencies | None new | — |

## Architecture

```
Home (urgency card)
  → View → /policies/:id → GET /api/v1/policies/{id}
  → Edit → /policies/:id/edit
Detail
  → Edit → /policies/:id/edit
  → Delete → DELETE /api/v1/policies/{id} → Home
  → source doc → /documents/{source_document_id}/review (when present)
```

**Isolation (unchanged):** cross-user detail → **404**. Unauthenticated →
redirect to login (frontend) / 401 (API).

## Data model / API

None new.

## Frontend

- [frontend/src/pages/PolicyDetail.tsx](../../frontend/src/pages/PolicyDetail.tsx)
  read-only detail lines for every field.
- Route in [frontend/src/App.tsx](../../frontend/src/App.tsx):
  `/policies/:id` alongside `/policies/:id/edit`.
- [frontend/src/pages/Home.tsx](../../frontend/src/pages/Home.tsx):
  **View** link on policy cards.

## Tests

Write failing tests first.

- Detail renders Harbor Cove–shaped deductibles/carriers/locations.
- API 404 → plain-language error.
- Edit link targets `/policies/:id/edit`.
- Unauthenticated → login redirect.
- Home View link reaches detail.

## Out of this PR

Slide-up panel, YoY, recharts, PATCH from detail, manual create,
reminders.
