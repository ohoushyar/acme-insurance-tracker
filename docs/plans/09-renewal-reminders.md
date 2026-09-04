# Step 9: In-app renewal reminders

This plan covers **PRD Section 8 item 9** only: flag/notify at 60/30/10
days before a policy’s `renewal_date`. Dashboard urgency groups stay as
built in [06-dashboard-list.md](06-dashboard-list.md).
**No SMTP, Mailpit, verified email, password reset, or CronJob.**

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Delivery | In-app persisted rows; mark as read / unread | PRD §10 left this open; email is item 11. |
| Thresholds | Fixed `(60, 30, 10)` | PRD §6.1; no settings UI (same as YoY). |
| Due window | UTC days until renewal in `1..threshold` | Still *before* the date; catch-up on first sync. |
| Day 0 / overdue | No new rows | Dashboard already treats these as urgent. |
| Dedup | Unique `(policy_id, threshold_days, renewal_date)` | New term (edited date) can fire again; read stays. |
| Scan trigger | `GET /reminders` upserts then lists | No periodic worker yet; same helper for item 11. |
| Dependencies | None new | — |

## Architecture

```
Shell /reminders
  → GET /api/v1/reminders (sync due rows, return unread first)
  → POST /api/v1/reminders/{id}/read
  → POST /api/v1/reminders/{id}/unread
  → View → /policies/:id
```

**Isolation:** `get_current_user` + `get_tenant_db` + RLS on `reminders`.
Cross-user GET/read/unread → **404**. Unauthenticated → **401**.

## Data model

Alembic `0008_reminders.py`:

- `reminders`: id, user_id, policy_id (FK CASCADE), threshold_days
  (10/30/60), renewal_date snapshot, read_at nullable, created_at
- Unique `(policy_id, threshold_days, renewal_date)`
- RLS + grant `app`

## API

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/v1/reminders` | Sync due rows; `{ items, unread_count }` |
| POST | `/api/v1/reminders/{id}/read` | Set `read_at` if unset; idempotent |
| POST | `/api/v1/reminders/{id}/unread` | Clear `read_at` if set; idempotent |

`ReminderOut`: id, policy_id, threshold_days, renewal_date, read_at,
named_insured, coverage_type.

## Frontend

- Shell nav **Reminders** with unread count
- `/reminders`: unread first; View → detail; Mark as read / unread

## Tests

Write failing tests first.

- Unit: 61 none; 60 → `[60]`; 45 → `[60]`; 30 → `[60,30]`; 10/1 all three;
  0 / negative / null → none
- API: catch-up once; no duplicate GET; new renewal_date fires a new set;
  mark-as-read sticky; mark-as-unread clears `read_at`; delete cascades;
  cross-user 404; anonymous 401
- Frontend: Shell badge; list copy; mark as read / unread; link to detail;
  anonymous → login

## PRD note (with this step)

- Item 11: email renewal reminders. Password-reset mail waits on that infra.

## Out of this PR

SMTP, Mailpit, email templates, address verification, password reset,
k8s CronJob, user-configurable lead times, snooze, extra 60-day
dashboard bucket, `POST /policies`.
