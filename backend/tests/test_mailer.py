from unittest.mock import MagicMock, patch

import pytest

from app.mailer import MailerError, MemoryMailer, OutgoingEmail, SesMailer, SmtpMailer


async def test_memory_mailer_records_messages() -> None:
    mailer = MemoryMailer()
    message = OutgoingEmail(
        to_address="owner@example.com",
        subject="Hello",
        text_body="text",
        html_body="<p>html</p>",
    )
    await mailer.send(message)
    assert mailer.sent == [message]


async def test_memory_mailer_failure_does_not_record() -> None:
    mailer = MemoryMailer()
    mailer.fail_with = MailerError("boom")
    with pytest.raises(MailerError):
        await mailer.send(
            OutgoingEmail(
                to_address="owner@example.com",
                subject="Hello",
                text_body="text",
                html_body="<p>html</p>",
            )
        )
    assert mailer.sent == []


def test_build_mailer_unset_backend_raises() -> None:
    from unittest.mock import MagicMock

    from app.mailer import build_mailer

    settings = MagicMock()
    settings.email_backend = ""
    with pytest.raises(MailerError, match="EMAIL_BACKEND is not configured"):
        build_mailer(settings)


async def test_smtp_mailer_sends_via_aiosmtplib() -> None:
    mailer = SmtpMailer(
        host="mailpit",
        port=1025,
        from_address="noreply@example.com",
    )
    captured: dict[str, object] = {}

    async def fake_send(payload, **kwargs):
        captured["payload"] = payload
        captured["kwargs"] = kwargs

    with patch("app.mailer.aiosmtplib.send", fake_send):
        await mailer.send(
            OutgoingEmail(
                to_address="owner@example.com",
                subject="Hello",
                text_body="text",
                html_body="<p>html</p>",
            )
        )
    assert captured["kwargs"]["hostname"] == "mailpit"
    assert captured["payload"]["To"] == "owner@example.com"
    assert captured["payload"]["From"] == "noreply@example.com"


async def test_ses_mailer_calls_stubbed_send_email() -> None:
    client = MagicMock()
    mailer = SesMailer(
        from_address="noreply@example.com",
        region="us-east-1",
        client=client,
    )
    await mailer.send(
        OutgoingEmail(
            to_address="owner@example.com",
            subject="Hello",
            text_body="text",
            html_body="<p>html</p>",
        )
    )
    client.send_email.assert_called_once()
    kwargs = client.send_email.call_args.kwargs
    assert kwargs["FromEmailAddress"] == "noreply@example.com"
    assert kwargs["Destination"]["ToAddresses"] == ["owner@example.com"]
    assert kwargs["Content"]["Simple"]["Subject"]["Data"] == "Hello"
