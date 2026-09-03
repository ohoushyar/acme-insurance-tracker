# Step 5: Portfolio management

This plan covers **PRD Section 8 item 5** only: add/edit/delete properties
and edit/delete confirmed policies, with manual `propertyIds[]` attach.
Confirm remains the only policy insert path
([docs/plans/04-confirmed-policies.md](04-confirmed-policies.md)).
**No dashboard urgency groups, policy detail route, YoY, reminders, or
`POST /policies`.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Manual policy create | Not this step. Policies still come from review/confirm. Add **PRD §8 item 10**: “Manual policy create (no PDF).” | That later step will need `source_document_id` nullable. |
| Property fields | Add PRD §7 columns `address` (text, nullable) and `stated_value` (`Numeric`, nullable) to the existing `properties` table (today only `label`). | Matches the draft schema. |
| Linking | `policy_properties` M2M. No auto-create from extracted `locations` (still JSONB on the policy). | User creates properties on `/properties`, then attaches them on policy edit. |
| Delete property | Remove the row and its M2M links. Policies stay. | Confirm copy names how many policies will be unlinked. |
| Delete policy | Delete the policy row and its M2M links. Keep the source `documents` row and MinIO PDF. | Re-confirm upserts a new policy (existing unique `source_document_id`). |
| PATCH vs confirm | `PATCH /policies/{id}` updates the portfolio row only — it does not rewrite `documents.extracted`. | Re-confirm still overwrites policy scalars via `apply_extracted` and **must preserve** existing property links. |
| UI | `/properties` for property CRUD (Home will become the urgency dashboard in step 6). `/policies/:id/edit` for field edit + attach — not the step 7 detail page. Home **Saved policies** cards get Edit + Delete. | Keeps this step off the dashboard and detail routes. |
| Dependencies | None new | Reuse existing Pydantic extraction schema. |

## Architecture

```
Home (saved policies)
  → Edit → /policies/:id/edit → PATCH /api/v1/policies/{id}  { fields, property_ids }
  → Delete → DELETE /api/v1/policies/{id}
/properties
  → POST/PATCH/DELETE /api/v1/properties
```

**Isolation (unchanged):** `get_current_user` + `get_tenant_db` + RLS on
`properties`, `policies`, and `policy_properties`. User A mutating user
B’s id returns **404**. Unauthenticated → 401. Attaching another user’s
property id → **404** (no existence leak). RLS must still hide join rows
if a handler forgets `WHERE user_id`.

## Data model

Alembic `0006_portfolio_management.py` (revises `0005`, which already
widened policy text columns).

- `properties`: add `address` (Text, nullable), `stated_value`
  (Numeric, nullable), `updated_at` (timestamptz).
- `policy_properties`: `policy_id` (FK policies, CASCADE),
  `property_id` (FK properties, CASCADE), `user_id` (FK users,
  indexed), unique `(policy_id, property_id)`. RLS identical in shape
  to `policies_isolation`. Grant `app` DML. Extend `RLS_STATEMENTS` in
  [backend/app/db.py](../../backend/app/db.py).

`upsert_policy` in
[backend/app/policy_mapping.py](../../backend/app/policy_mapping.py)
stays field-only — do not clear M2M on re-confirm.

## API

| Method | Path | Behavior |
|---|---|---|
| `POST` | `/api/v1/properties` | `{ label, address?, stated_value? }`. Empty label → **422**. |
| `PATCH` | `/api/v1/properties/{id}` | Same body, partial. |
| `DELETE` | `/api/v1/properties/{id}` | **204**. Unlinks then deletes. |
| `PATCH` | `/api/v1/policies/{id}` | `ConfirmExtractedPolicy` fields + `property_ids: UUID[]` (replace set; empty unlinks all). Strict money → **422**. |
| `DELETE` | `/api/v1/policies/{id}` | **204**. Document/PDF remain. |

Existing `GET` list/detail stay. `PropertyOut` adds `address`,
`stated_value`, `updated_at`, `policy_ids[]`. `PolicyOut` adds
`property_ids[]`. No `POST /api/v1/policies`.

## Frontend

- Types + `listProperties` / `createProperty` / `updateProperty` /
  `deleteProperty` / `updatePolicy` / `deletePolicy` in
  [frontend/src/api.ts](../../frontend/src/api.ts).
- Route `/properties` → property list + create/edit form + two-step
  delete (not `window.confirm`).
- Route `/policies/:id/edit` → reuse Review field-editor patterns
  (strict money, list add/remove) plus checkboxes of the user’s
  properties. Cancel returns Home with no write.
- [frontend/src/components/Shell.tsx](../../frontend/src/components/Shell.tsx):
  nav **Properties**.
- [frontend/src/pages/Home.tsx](../../frontend/src/pages/Home.tsx)
  `PolicyCard`: Edit link, Delete with confirm, show attached property
  labels (not only extracted location labels).

## Tests

Write failing tests first.

Backend (auth boundary + multi-deductible): unauthenticated 401 on
writes; cross-user property/policy PATCH/DELETE 404; attach other-user
property 404; RLS on `policy_properties` without application filter;
Harbor Cove-shaped deductibles survive PATCH; delete property unlinks
and leaves the policy; delete policy leaves the document; re-confirm
keeps `property_ids`.

Frontend: create a property and see it on `/properties`; attach it on
policy edit and see the label on Home; delete property/policy only after
the second confirm click; other-user properties never appear in the
mock.

## PRD updates (with this step)

- §8 add item **10. Manual policy create (no PDF)**.
- §10: `propertyIds` are a manual attach in step 5; auto-match from
  locations stays a step 8 risk.

## Out of this PR

`POST /policies`, auto-creating properties from locations, PolicyHistory
/ YoY, dashboard urgency groups, `/policies/:id` detail, vision OCR,
password reset.
