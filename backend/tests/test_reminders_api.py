import asyncio
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.storage import document_storage_key
from tests.test_policies import _insert_document, _insert_policy, _owner_id


def _today() -> date:
    return datetime.now(UTC).date()


async def _insert_policy_with_renewal(
    user_id: UUID,
    *,
    named_insured: str,
    coverage_type: str,
    renewal_date: str,
) -> UUID:
    document_id = await _insert_document(user_id, "reviewed")
    policy_id = await _insert_policy(
        user_id,
        document_id,
        named_insured=named_insured,
        renewal_date=renewal_date,
    )
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE policies SET coverage_type = :coverage WHERE id = :id"),
            {"coverage": coverage_type, "id": policy_id},
        )
    await engine.dispose()
    return policy_id


async def test_get_reminders_creates_catch_up_rows_once(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=8)).isoformat()
    policy_id = await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )

    first = await client.get("/api/v1/reminders")
    assert first.status_code == 200
    body = first.json()
    assert body["unread_count"] == 3
    thresholds = sorted(item["threshold_days"] for item in body["items"])
    assert thresholds == [10, 30, 60]
    for item in body["items"]:
        assert item["policy_id"] == str(policy_id)
        assert item["named_insured"] == "Harbor Cove LLC"
        assert item["coverage_type"] == "Property"
        assert item["renewal_date"] == renewal
        assert item["read_at"] is None

    second = await client.get("/api/v1/reminders")
    assert second.status_code == 200
    assert second.json()["unread_count"] == 3
    assert len(second.json()["items"]) == 3
    assert {item["id"] for item in second.json()["items"]} == {
        item["id"] for item in body["items"]
    }


async def test_patch_renewal_date_allows_a_new_reminder_set(
    client: AsyncClient,
) -> None:
    user_id = await _owner_id(client)
    first_renewal = (_today() + timedelta(days=45)).isoformat()
    policy_id = await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=first_renewal,
    )

    first = await client.get("/api/v1/reminders")
    assert first.status_code == 200
    assert first.json()["unread_count"] == 1
    assert first.json()["items"][0]["threshold_days"] == 60

    second_renewal = (_today() + timedelta(days=8)).isoformat()
    patched = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"renewal_date": second_renewal},
    )
    assert patched.status_code == 200

    listed = await client.get("/api/v1/reminders")
    assert listed.status_code == 200
    items = listed.json()["items"]
    dates = {item["renewal_date"] for item in items}
    assert first_renewal in dates
    assert second_renewal in dates
    assert listed.json()["unread_count"] == 4


async def test_overlapping_gets_do_not_conflict(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=8)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    first, second = await asyncio.gather(
        client.get("/api/v1/reminders"),
        client.get("/api/v1/reminders"),
    )
    assert first.status_code == 200
    assert second.status_code == 200
    first_ids = {item["id"] for item in first.json()["items"]}
    second_ids = {item["id"] for item in second.json()["items"]}
    assert first_ids == second_ids
    assert len(first_ids) == 3
    assert first.json()["unread_count"] == 3
    assert second.json()["unread_count"] == 3


async def test_mark_reminder_read_is_sticky(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=45)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    listed = await client.get("/api/v1/reminders")
    reminder_id = listed.json()["items"][0]["id"]

    marked = await client.post(f"/api/v1/reminders/{reminder_id}/read")
    assert marked.status_code == 200
    assert marked.json()["read_at"] is not None

    again = await client.post(f"/api/v1/reminders/{reminder_id}/read")
    assert again.status_code == 200
    assert again.json()["read_at"] == marked.json()["read_at"]

    relisted = await client.get("/api/v1/reminders")
    assert relisted.status_code == 200
    assert relisted.json()["unread_count"] == 0
    assert relisted.json()["items"][0]["read_at"] is not None


async def test_mark_reminder_unread_clears_read_at(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=45)).isoformat()
    await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    listed = await client.get("/api/v1/reminders")
    reminder_id = listed.json()["items"][0]["id"]
    await client.post(f"/api/v1/reminders/{reminder_id}/read")

    unmarked = await client.post(f"/api/v1/reminders/{reminder_id}/unread")
    assert unmarked.status_code == 200
    assert unmarked.json()["read_at"] is None

    again = await client.post(f"/api/v1/reminders/{reminder_id}/unread")
    assert again.status_code == 200
    assert again.json()["read_at"] is None

    relisted = await client.get("/api/v1/reminders")
    assert relisted.status_code == 200
    assert relisted.json()["unread_count"] == 1
    assert relisted.json()["items"][0]["read_at"] is None


async def test_delete_policy_cascades_reminders(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    renewal = (_today() + timedelta(days=45)).isoformat()
    policy_id = await _insert_policy_with_renewal(
        user_id,
        named_insured="Harbor Cove LLC",
        coverage_type="Property",
        renewal_date=renewal,
    )
    await client.get("/api/v1/reminders")
    deleted = await client.delete(f"/api/v1/policies/{policy_id}")
    assert deleted.status_code == 204

    listed = await client.get("/api/v1/reminders")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["unread_count"] == 0


async def test_cross_user_reminder_is_404(client: AsyncClient) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        other_id = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'other-remind@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        document_id = uuid4()
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status
                )
                VALUES (
                    :id, :uid, 'p.pdf', 'application/pdf', 128,
                    :key, 'reviewed'
                )
                """),
            {
                "id": document_id,
                "uid": other_id,
                "key": document_storage_key(other_id, document_id),
            },
        )
        policy_id = uuid4()
        reminder_id = uuid4()
        renewal = _today() + timedelta(days=45)
        await conn.execute(
            text("""
                INSERT INTO policies (
                    id, user_id, source_document_id, named_insured,
                    renewal_date,
                    carriers, deductibles, locations, extraction_confidence
                )
                VALUES (
                    :id, :uid, :doc_id, 'Other LLC',
                    :renewal,
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb
                )
                """),
            {
                "id": policy_id,
                "uid": other_id,
                "doc_id": document_id,
                "renewal": renewal,
            },
        )
        await conn.execute(
            text("""
                INSERT INTO reminders (
                    id, user_id, policy_id, threshold_days, renewal_date
                )
                VALUES (:id, :uid, :policy_id, 60, :renewal)
                """),
            {
                "id": reminder_id,
                "uid": other_id,
                "policy_id": policy_id,
                "renewal": renewal,
            },
        )
    await engine.dispose()

    await _owner_id(client)
    listed = await client.get("/api/v1/reminders")
    assert listed.status_code == 200
    assert listed.json()["items"] == []

    marked = await client.post(f"/api/v1/reminders/{reminder_id}/read")
    assert marked.status_code == 404
    assert marked.json()["error"]["code"] == "NOT_FOUND"

    unmarked = await client.post(f"/api/v1/reminders/{reminder_id}/unread")
    assert unmarked.status_code == 404
    assert unmarked.json()["error"]["code"] == "NOT_FOUND"


async def test_anonymous_reminders_are_401(client: AsyncClient) -> None:
    listed = await client.get("/api/v1/reminders")
    assert listed.status_code == 401
    marked = await client.post(f"/api/v1/reminders/{uuid4()}/read")
    assert marked.status_code == 401
    unmarked = await client.post(f"/api/v1/reminders/{uuid4()}/unread")
    assert unmarked.status_code == 401
