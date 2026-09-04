# Step 11: Email renewal reminders

This plan covers **PRD Section 8 item 11** only: emailed 60/30/10
renewal reminders, plus the shared mail stack PRD §10 said to build
here (verification + password reset). **Not** PRD item 10 (manual
policy create). In-app reminders stay as built in
[09-renewal-reminders.md](09-renewal-reminders.md).

## Decisions (surfaced, not silent)

| Topic | Choice | Why |
|---|---|---|
| Local transport | Mailpit SMTP via `aiosmtplib` | Inspect mail on `:8025`; no AWS from a laptop. |
| AWS transport | SESv2 `SendEmail` + existing IRSA | Same as S3: no static keys. boto3 already in lockfile. |
| Backend switch | `EMAIL_BACKEND=smtp\|ses` | Factory like `build_document_store`. Unset raises in the worker. Tests inject `MemoryMailer`. |
| Verified address | `users.email_verified_at` | PRD §10. Login still works unverified. |
| Send path | Dramatiq on Redis DB 2 | Same as `extract_document.send`. API never talks SMTP/SES. |
| Scan | `scan_reminder_emails` actor + `send_with_options(delay=1h)` | No CronJob, no periodiq. |
| Dedup | `email_queued_at` then `emailed_at` | Claim on enqueue; mark sent after mailer succeeds. |
| Reset tokens | Redis, hashed, single-use | Matches sessions. 24h verify / 1h reset. |

## Architecture

```
POST register / resend / forgot-password
  → Redis token + send_auth_email.send
Worker boot
  → scan_reminder_emails
  → sync_due_rows, claim, send_reminder_email.send per user
  → send_with_options(delay=1h)
Worker
  → SmtpMailer (Mailpit) or SesMailer (IRSA)
GET /reminders
  → in-app sync only
```

**Isolation:** scan/send use the app DB role, `list_verified()`, then
`set_tenant` per user. No `ADMIN_DATABASE_URL`. No RLS bypass.

## Data model

Alembic `0009_email.py`:

- `users.email_verified_at` nullable timestamptz
- `reminders.emailed_at` nullable timestamptz
- `reminders.email_queued_at` nullable timestamptz

## API

| Method | Path | Behavior |
|---|---|---|
| POST | `/auth/register` | 201 + session; enqueue verify mail |
| GET | `/auth/me` | Load user from DB (`email_verified_at` current) |
| POST | `/auth/resend-verification` | Auth; 204; 429 cooldown |
| POST | `/auth/verify-email` | `{ token }`; 400 `TOKEN_INVALID` |
| POST | `/auth/forgot-password` | `{ email }`; always 204 |
| POST | `/auth/reset-password` | `{ token, password }`; verifies email |

## Frontend

- Login: Forgot password? → `/forgot-password`
- `/reset-password?token=`, `/verify-email?token=`
- Shell banner when `email_verified_at` is null + resend

## Infra

Compose Mailpit. AWS: SES domain identity + DKIM + IRSA send on the
existing app role. Optional Route53. Sandbox exit is not Terraform.

## Out of this PR

Manual policy create, snooze, unsubscribe, change-email, SMS, CronJob,
periodiq, SES production-access request.
