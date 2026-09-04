from contextlib import contextmanager
from datetime import timedelta
from unittest.mock import patch
from uuid import UUID

from dramatiq import Worker
from dramatiq.brokers.stub import StubBroker
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.mailer import MailerError, MemoryMailer
from tests.test_policies import _owner_id
from tests.test_reminders_api import _insert_policy_with_renewal, _today


def _broker_for(*actors):
    broker = StubBroker()
    broker.emit_after("process_boot")
    for actor in actors:
        actor.broker = broker
        broker.declare_actor(actor)
    return broker


@contextmanager
def _without_delayed_reschedule(actor):
    original = actor.send_with_options
    delayed: list[dict] = []

    def _send_with_options(*args, **kwargs):
        if kwargs.get("delay") is not None:
            delayed.append(kwargs)
            return None
        return original(*args, **kwargs)

    with patch.object(actor, "send_with_options", side_effect=_send_with_options):
        yield delayed


async def _set_verified(user_id: str) -> None:
    engine = create_async_engine(get_settings().admin_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET email_verified_at = now() WHERE id = :id"),
            {"id": user_id},
        )
    await engine.dispose()


async def _reminder_email_state(reminder_id: str) -> tuple[object, object]:
    engine = create_async_engine(get_settings().admin_database_url)
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT email_queued_at, emailed_at FROM reminders WHERE id = :id"
                ),
                {"id": reminder_id},
            )
        ).one()
    await engine.dispose()
    return row.email_queued_at, row.emailed_at


async def _set_queued(reminder_id: str) -> None:
    engine = create_async_engine(get_settings().admin_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE reminders SET email_queued_at = now() WHERE id = :id"),
            {"id": reminder_id},
        )
    await engine.dispose()


async def test_send_auth_email_actor_sends_verify_template(
    client: AsyncClient,
) -> None:
    from app.queue.email import send_auth_email

    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    me = (await client.get("/api/v1/auth/me")).json()
    mailer = MemoryMailer()
    broker = _broker_for(send_auth_email)
    with patch("app.queue.email.build_mailer", return_value=mailer):
        send_auth_email.send(me["id"], "verify", "test-token")
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(send_auth_email.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to_address == "owner@example.com"
    assert "verify-email?token=test-token" in mailer.sent[0].text_body


async def test_send_auth_email_actor_sends_reset_template(
    client: AsyncClient,
) -> None:
    from app.queue.email import send_auth_email

    await client.post(
        "/api/v1/auth/register",
        json={"email": "owner@example.com", "password": "correct-horse"},
    )
    me = (await client.get("/api/v1/auth/me")).json()
    mailer = MemoryMailer()
    broker = _broker_for(send_auth_email)
    with patch("app.queue.email.build_mailer", return_value=mailer):
        send_auth_email.send(me["id"], "reset", "reset-token")
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(send_auth_email.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert len(mailer.sent) == 1
    assert "reset-password?token=reset-token" in mailer.sent[0].text_body


async def test_send_reminder_email_skips_unverified(client: AsyncClient) -> None:
    from app.queue.email import send_reminder_email

    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    mailer = MemoryMailer()
    broker = _broker_for(send_reminder_email)
    with patch("app.queue.email.build_mailer", return_value=mailer):
        send_reminder_email.send(str(user_id), [])
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(send_reminder_email.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert mailer.sent == []


async def test_scan_enqueues_send_for_verified_only(client: AsyncClient) -> None:
    from app.queue.email import scan_reminder_emails

    verified_id = await _owner_id(client)
    await _set_verified(str(verified_id))
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        verified_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    await client.post("/api/v1/auth/logout")
    client.cookies.clear()
    await client.post(
        "/api/v1/auth/register",
        json={"email": "other@example.com", "password": "correct-horse"},
    )
    other = (await client.get("/api/v1/auth/me")).json()
    await _insert_policy_with_renewal(
        UUID(other["id"]),
        named_insured="Other LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )

    broker = _broker_for(scan_reminder_emails)
    with (
        patch("app.services.reminder_emails.send_reminder_email.send") as send,
        _without_delayed_reschedule(scan_reminder_emails),
    ):
        scan_reminder_emails.send()
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(scan_reminder_emails.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert send.call_count == 1
    assert send.call_args.args[0] == str(verified_id)


async def test_second_scan_does_not_send_while_queued(client: AsyncClient) -> None:
    from app.db import create_engine, create_session_factory, set_tenant
    from app.services.reminder_emails import enqueue_due_digest

    user_id = await _owner_id(client)
    await _set_verified(str(user_id))
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    with patch("app.services.reminder_emails.send_reminder_email.send") as send:
        async with factory() as session:
            await set_tenant(session, str(user_id))
            first = await enqueue_due_digest(session, user_id)
            second = await enqueue_due_digest(session, user_id)
            await session.commit()
    await engine.dispose()
    assert first
    assert second == []
    send.assert_called_once()


async def test_enqueue_due_digest_commits_before_send(client: AsyncClient) -> None:
    from app.db import create_engine, create_session_factory
    from app.repositories import transactions
    from app.services.reminder_emails import enqueue_due_digest

    user_id = await _owner_id(client)
    await _set_verified(str(user_id))
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    order: list[str] = []
    real_commit = transactions.commit

    async def tracking_commit(session):
        order.append("commit")
        return await real_commit(session)

    def tracking_send(*_args, **_kwargs):
        order.append("send")

    settings = get_settings()
    engine = create_engine(settings.database_url)
    factory = create_session_factory(engine)
    with (
        patch("app.services.reminder_emails.transactions.commit", tracking_commit),
        patch("app.services.reminder_emails.send_reminder_email.send", tracking_send),
    ):
        async with factory() as session:
            await enqueue_due_digest(session, user_id)
    await engine.dispose()
    assert order[:2] == ["commit", "send"]


async def test_mailer_failure_leaves_emailed_at_null(client: AsyncClient) -> None:
    from app.queue.email import send_reminder_email

    user_id = await _owner_id(client)
    await _set_verified(str(user_id))
    renewal = (_today() + timedelta(days=8)).isoformat()
    policy_id = await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    listed = await client.get("/api/v1/reminders")
    reminder_id = listed.json()["items"][0]["id"]
    await _set_queued(reminder_id)

    mailer = MemoryMailer()
    mailer.fail_with = MailerError("smtp down")
    broker = _broker_for(send_reminder_email)
    with (
        patch("app.queue.email.build_mailer", return_value=mailer),
        patch("app.queue.email._is_last_retry", return_value=True),
    ):
        send_reminder_email.send(str(user_id), [reminder_id])
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(send_reminder_email.queue_name, timeout=8000)
        finally:
            worker.stop()
    queued_at, emailed_at = await _reminder_email_state(reminder_id)
    assert emailed_at is None
    assert queued_at is None
    _ = policy_id


async def test_successful_send_sets_emailed_at(client: AsyncClient) -> None:
    from app.queue.email import send_reminder_email

    user_id = await _owner_id(client)
    await _set_verified(str(user_id))
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    listed = await client.get("/api/v1/reminders")
    ids = [item["id"] for item in listed.json()["items"]]
    mailer = MemoryMailer()
    broker = _broker_for(send_reminder_email)
    with patch("app.queue.email.build_mailer", return_value=mailer):
        send_reminder_email.send(str(user_id), ids)
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(send_reminder_email.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert len(mailer.sent) == 1
    _, emailed_at = await _reminder_email_state(ids[0])
    assert emailed_at is not None


async def test_scan_reschedules_with_delay(client: AsyncClient) -> None:
    from app.queue.email import scan_reminder_emails
    from app.services.reminder_emails import REMINDER_SCAN_DELAY_MS

    broker = _broker_for(scan_reminder_emails)
    with _without_delayed_reschedule(scan_reminder_emails) as delayed:
        scan_reminder_emails.send()
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(scan_reminder_emails.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert delayed
    assert delayed[0]["delay"] == REMINDER_SCAN_DELAY_MS


async def test_scan_reschedules_after_failure(client: AsyncClient) -> None:
    from app.queue.email import scan_reminder_emails
    from app.services.reminder_emails import REMINDER_SCAN_DELAY_MS

    broker = _broker_for(scan_reminder_emails)
    with (
        patch(
            "app.services.reminder_emails.enqueue_due_digests_for_verified",
            side_effect=RuntimeError("db down"),
        ),
        _without_delayed_reschedule(scan_reminder_emails) as delayed,
    ):
        scan_reminder_emails.send()
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(scan_reminder_emails.queue_name, timeout=5000)
        finally:
            worker.stop()
    assert delayed
    assert delayed[0]["delay"] == REMINDER_SCAN_DELAY_MS
    _ = client


async def test_scan_without_lock_does_not_reschedule(
    client: AsyncClient, redis_client: Redis
) -> None:
    from app.queue.email import scan_reminder_emails
    from app.services.reminder_emails import SCAN_LOCK_KEY

    await redis_client.set(SCAN_LOCK_KEY, "1")
    broker = _broker_for(scan_reminder_emails)
    with (
        patch("app.services.reminder_emails.send_reminder_email.send") as send,
        _without_delayed_reschedule(scan_reminder_emails) as delayed,
    ):
        scan_reminder_emails.send()
        worker = Worker(broker, worker_timeout=5000)
        worker.start()
        try:
            broker.join(scan_reminder_emails.queue_name, timeout=5000)
        finally:
            worker.stop()
    send.assert_not_called()
    assert delayed == []
    _ = client
