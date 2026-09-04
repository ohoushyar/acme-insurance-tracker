# Step 6: Dashboard list view + summary stats

This plan covers **PRD Section 8 item 6** only: urgency-grouped policy
list and portfolio summary stats. Policy detail is step 7
([docs/plans/07-policy-detail.md](07-policy-detail.md)); YoY is step 8
([docs/plans/08-yoy-trends.md](08-yoy-trends.md)).
**No PolicyHistory, recharts, detail route wiring, or reminders.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Urgency buckets | `urgent` ≤30 days, `soon` ≤90, `on_track` >90; missing `renewal_date` → `unknown` | Matches design mockup; unknown avoids hiding undated policies in “on track.” |
| Summary stats | Total `total_premium` sum; count ≤30; count ≤90 (excludes ≤30) | Mockup; YoY count waits for step 8. |
| Grouping locus | Client-side on `GET /api/v1/policies` | Small portfolios; no summary endpoint. |
| List sort | Backend `renewal_date ASC NULLS LAST`, then `created_at DESC` | Index already on `renewal_date`. |
| Home layout | Keep upload + document jobs; replace flat “Saved policies” with urgency groups + stats | Upload remains on Home. |
| Dependencies | None new | `recharts` is step 8. |

## Architecture

```
Home
  → GET /api/v1/policies (renewal_date ordered)
  → groupPolicies / portfolioStats (client)
  → Stat strip + Urgent / Soon / On track / Unknown sections
```

**Isolation (unchanged):** existing list auth + RLS.

## Backend

- [backend/app/repositories/policies.py](../../backend/app/repositories/policies.py)
  `list_for_user`: order by `renewal_date.asc().nulls_last()`,
  `created_at.desc()`.
- No migration, no new routes.

## Frontend

- [frontend/src/urgency.ts](../../frontend/src/urgency.ts): `daysUntil`,
  `urgencyOf`, `groupPolicies`, `portfolioStats`.
- [frontend/src/pages/Home.tsx](../../frontend/src/pages/Home.tsx):
  stat strip + grouped sections; keep Edit + Delete on cards.
- Urgency colors in [frontend/src/index.css](../../frontend/src/index.css)
  (`--urgent`, `--soon`).

## Tests

Write failing tests first.

- Unit: day boundaries 0/30/31/90/91; null → `unknown`; premium sum;
  empty groups omitted from section list.
- Component: Home shows three stats and group headings; upload zone
  still present; empty portfolio has no stat strip.
- Backend: list order puts earlier `renewal_date` first; nulls last.

## PRD note (with this step)

- Until step 8, portfolio summary is total premium + ≤30 + ≤90 counts.

## Out of this PR

Detail View link (step 7 if not already), YoY, PolicyHistory, recharts,
reminders, `POST /policies`.
