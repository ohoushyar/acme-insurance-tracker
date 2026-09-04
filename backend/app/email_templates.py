from __future__ import annotations

from uuid import UUID

from app.email_tokens import escape
from app.mailer import OutgoingEmail
from app.models import Policy, Reminder, User


def _base_url(public_url: str) -> str:
    return public_url.rstrip("/")


def verify_email_message(user: User, token: str, public_url: str) -> OutgoingEmail:
    link = f"{_base_url(public_url)}/verify-email?token={token}"
    return OutgoingEmail(
        to_address=user.email,
        subject="Verify your Insurance Tracker email",
        text_body=(
            "Confirm this email address so we can send renewal reminders.\n\n"
            f"{link}\n"
        ),
        html_body=(
            "<p>Confirm this email address so we can send renewal reminders.</p>"
            f'<p><a href="{escape(link)}">Verify email</a></p>'
        ),
    )


def reset_password_message(user: User, token: str, public_url: str) -> OutgoingEmail:
    link = f"{_base_url(public_url)}/reset-password?token={token}"
    return OutgoingEmail(
        to_address=user.email,
        subject="Reset your Insurance Tracker password",
        text_body=f"Use this link to choose a new password.\n\n{link}\n",
        html_body=(
            "<p>Use this link to choose a new password.</p>"
            f'<p><a href="{escape(link)}">Reset password</a></p>'
        ),
    )


def reminder_digest_message(
    user: User,
    reminders: list[Reminder],
    policies: dict[UUID, Policy],
    public_url: str,
) -> OutgoingEmail:
    lines: list[str] = []
    items_html: list[str] = []
    for reminder in reminders:
        policy: Policy | None = policies.get(reminder.policy_id)
        label = (
            (policy.named_insured if policy is not None else None)
            or (policy.coverage_type if policy is not None else None)
            or "Policy"
        )
        renewal = reminder.renewal_date.isoformat()
        detail = f"{_base_url(public_url)}/policies/{reminder.policy_id}"
        lines.append(
            f"- {label}: renews {renewal} "
            f"({reminder.threshold_days} days). {detail}"
        )
        items_html.append(
            "<li>"
            f"{escape(label)}: renews {escape(renewal)} "
            f"({reminder.threshold_days} days). "
            f'<a href="{escape(detail)}">View policy</a>'
            "</li>"
        )
    count = len(reminders)
    subject = (
        "Insurance renewal coming up"
        if count == 1
        else f"{count} insurance renewals coming up"
    )
    return OutgoingEmail(
        to_address=user.email,
        subject=subject,
        text_body="Upcoming renewals:\n\n" + "\n".join(lines) + "\n",
        html_body="<p>Upcoming renewals:</p><ul>" + "".join(items_html) + "</ul>",
    )
