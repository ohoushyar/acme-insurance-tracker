# Step 11: Profile password change

This plan covers a signed-in password change on **Profile**. It is not
email password reset (PRD recovery still waits on step 11 email infra).

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Endpoint | `POST /api/v1/auth/password` | Clearer than PATCH `/me`; cookie required. |
| Body | `{ current_password, new_password }` min 8 | Same floor as register. |
| Wrong current | 401 `INVALID_CREDENTIALS` | Matches login; message “Current password is incorrect.” |
| Session | Keep the current cookie | Redis sessions are keyed by token, not user id. |
| Email change | Out of this step | Profile shows email read-only. |

## Architecture

```
POST /api/v1/auth/password  (cookie)
  → get_current_user + get_db
  → auth_service.change_password
      → users.get_by_id
      → verify_password(current)
      → hash_password(new) + set_password_hash
  → 204
```

Users table has no RLS; hashing stays in the service (same as
login/register). Router has no SQLAlchemy query APIs.

## Frontend

- Route `/profile`, nav **Profile** after Reminders.
- Form: current, new, confirm (confirm is client-only).
- Success: “Password updated.” Stay on the page.

## Tests

Backend: change then login with new; old 401; anonymous 401; short new
422; argon2 in DB; no password fields in the body.

Frontend: logged-out redirect; POST body; mismatch skips the API; wrong
current shows the API message.
