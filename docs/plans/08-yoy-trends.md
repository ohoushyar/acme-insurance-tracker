# Step 8: Multi-year trend chart + YoY flagging

This plan covers **PRD Section 8 item 8** only: link policies across
years, compute YoY premium change, flag increases ≥10%, and show a
premium trend chart. Dashboard urgency groups are step 6
([06-dashboard-list.md](06-dashboard-list.md)); detail is step 7
([07-policy-detail.md](07-policy-detail.md)).
**No reminders, manual policy create, or auto-match locations → properties.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Series model | `policy_series` + `policies.series_id` nullable FK `ON DELETE SET NULL` | Cleaner than JSON history; one series per policy. |
| Year for a point | `effective_date.year`, else `renewal_date.year - 1`, else skip | Term start; avoid inventing years. |
| Linking | Suggest + confirm; never silent auto-link | PRD §10. |
| Match heuristic | Same normalized `coverage_type` + ≥1 shared `property_id` | PRD “same property + coverage”; carrier ignored in V1. |
| YoY | Latest vs prior series member by year: `(curr-prev)/prev` | Need ≥2 members with premiums; `prev > 0`. |
| Flag threshold | `YOY_FLAG_THRESHOLD = 0.10` | PRD suggestion. |
| Dependency | Frontend `recharts` | Design reference uses it. |

## Data model

Alembic `0007_policy_series.py`:

- `policy_series`: id, user_id, label (nullable), created_at, updated_at
- RLS + grant `app`
- `policies.series_id` FK → policy_series ON DELETE SET NULL

## API

| Method | Path | Behavior |
|---|---|---|
| GET | `/policies/{id}/history` | `{ year, premium, policy_id }[]` |
| POST | `/policies/{id}/link` | `{ peer_policy_id }` — join series |
| DELETE | `/policies/{id}/link` | Unlink; delete empty series |

`PolicyOut` adds: `series_id`, `previous_premium`, `yoy_change_pct`,
`yoy_flagged`. Detail GET also returns `link_suggestions`.

## Frontend

- Home: 4th stat “Premium up 10%+”; YoY badge on cards
- Detail: prev premium, YoY %, recharts when ≥2 history points; link/unlink UI

## Out of this PR

Reminders, manual create, carrier-successor matching, threshold UI.
