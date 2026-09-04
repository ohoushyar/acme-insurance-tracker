from __future__ import annotations

import asyncio
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

import aiosmtplib
import boto3

from app.config import Settings


class MailerError(Exception):
    pass


@dataclass(frozen=True)
class OutgoingEmail:
    to_address: str
    subject: str
    text_body: str
    html_body: str


class Mailer(Protocol):
    async def send(self, message: OutgoingEmail) -> None: ...


class MemoryMailer:
    def __init__(self) -> None:
        self.sent: list[OutgoingEmail] = []
        self.fail_with: Exception | None = None

    async def send(self, message: OutgoingEmail) -> None:
        if self.fail_with is not None:
            raise self.fail_with
        self.sent.append(message)


class SmtpMailer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_address: str,
        username: str = "",
        password: str = "",
        starttls: bool = False,
    ) -> None:
        if not host:
            raise MailerError("SMTP host is not configured.")
        if not from_address:
            raise MailerError("EMAIL_FROM is not configured.")
        self._host = host
        self._port = port
        self._from_address = from_address
        self._username = username
        self._password = password
        self._starttls = starttls

    async def send(self, message: OutgoingEmail) -> None:
        payload = EmailMessage()
        payload["From"] = self._from_address
        payload["To"] = message.to_address
        payload["Subject"] = message.subject
        payload.set_content(message.text_body)
        payload.add_alternative(message.html_body, subtype="html")
        try:
            await aiosmtplib.send(
                payload,
                hostname=self._host,
                port=self._port,
                username=self._username or None,
                password=self._password or None,
                start_tls=self._starttls,
            )
        except Exception as exc:
            raise MailerError("Failed to send email.") from exc


class SesMailer:
    def __init__(
        self,
        *,
        from_address: str,
        region: str,
        client: object | None = None,
    ) -> None:
        if not from_address:
            raise MailerError("EMAIL_FROM is not configured.")
        self._from_address = from_address
        self._client = client or boto3.client("sesv2", region_name=region)

    async def send(self, message: OutgoingEmail) -> None:
        try:
            await asyncio.to_thread(
                self._client.send_email,
                FromEmailAddress=self._from_address,
                Destination={"ToAddresses": [message.to_address]},
                Content={
                    "Simple": {
                        "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                        "Body": {
                            "Text": {
                                "Data": message.text_body,
                                "Charset": "UTF-8",
                            },
                            "Html": {
                                "Data": message.html_body,
                                "Charset": "UTF-8",
                            },
                        },
                    }
                },
            )
        except Exception as exc:
            raise MailerError("Failed to send email.") from exc


def build_mailer(settings: Settings) -> Mailer:
    backend = settings.email_backend.strip().lower()
    if backend == "ses":
        return SesMailer(
            from_address=settings.email_from,
            region=settings.s3_region,
        )
    if backend == "smtp":
        return SmtpMailer(
            host=settings.smtp_host,
            port=settings.smtp_port,
            from_address=settings.email_from,
            username=settings.smtp_username,
            password=settings.smtp_password,
            starttls=settings.smtp_starttls,
        )
    raise MailerError("EMAIL_BACKEND is not configured.")
