from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings
from app.storage import document_storage_key
from tests.test_policies import _owner_id


async def _insert_policy_full(
    user_id: UUID,
    *,
    named_insured: str,
    coverage_type: str,
    effective_date: str,
    total_premium: str,
    property_id: UUID | None = None,
) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    policy_id = uuid4()
    document_id = uuid4()
    async with engine.begin() as conn:
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
                "uid": user_id,
                "key": document_storage_key(user_id, document_id),
            },
        )
        await conn.execute(
            text("""
                INSERT INTO policies (
                    id, user_id, source_document_id, named_insured,
                    coverage_type, effective_date, total_premium,
                    carriers, deductibles, locations, extraction_confidence
                )
                VALUES (
                    :id, :uid, :doc_id, :named_insured,
                    :coverage_type, :effective_date,
                    :total_premium,
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb
                )
                """),
            {
                "id": policy_id,
                "uid": user_id,
                "doc_id": document_id,
                "named_insured": named_insured,
                "coverage_type": coverage_type,
                "effective_date": date.fromisoformat(effective_date),
                "total_premium": Decimal(total_premium),
            },
        )
        if property_id is not None:
            await conn.execute(
                text("""
                    INSERT INTO policy_properties (policy_id, property_id, user_id)
                    VALUES (:policy_id, :property_id, :uid)
                    """),
                {
                    "policy_id": policy_id,
                    "property_id": property_id,
                    "uid": user_id,
                },
            )
    await engine.dispose()
    return policy_id


async def _insert_property(user_id: UUID, label: str = "Cove Plaza") -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    property_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO properties (id, user_id, label)
                VALUES (:id, :uid, :label)
                """),
            {"id": property_id, "uid": user_id, "label": label},
        )
    await engine.dispose()
    return property_id


async def test_link_history_and_yoy(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    property_id = await _insert_property(user_id)
    older_id = await _insert_policy_full(
        user_id,
        named_insured="Harbor 2023",
        coverage_type="Property",
        effective_date="2023-01-01",
        total_premium="100000",
        property_id=property_id,
    )
    newer_id = await _insert_policy_full(
        user_id,
        named_insured="Harbor 2024",
        coverage_type="Property",
        effective_date="2024-01-01",
        total_premium="120000",
        property_id=property_id,
    )

    detail = await client.get(f"/api/v1/policies/{newer_id}")
    assert detail.status_code == 200
    suggestions = detail.json()["link_suggestions"]
    assert any(item["policy_id"] == str(older_id) for item in suggestions)

    linked = await client.post(
        f"/api/v1/policies/{newer_id}/link",
        json={"peer_policy_id": str(older_id)},
    )
    assert linked.status_code == 200
    body = linked.json()
    assert body["series_id"] is not None
    assert body["previous_premium"] == "100000.00" or Decimal(
        body["previous_premium"]
    ) == Decimal(100000)
    assert body["yoy_change_pct"] == 20.0
    assert body["yoy_flagged"] is True

    history = await client.get(f"/api/v1/policies/{newer_id}/history")
    assert history.status_code == 200
    years = [item["year"] for item in history.json()["items"]]
    assert years == [2023, 2024]

    listed = await client.get("/api/v1/policies")
    flagged = [item for item in listed.json()["items"] if item["yoy_flagged"]]
    assert len(flagged) == 1

    unlinked = await client.delete(f"/api/v1/policies/{newer_id}/link")
    assert unlinked.status_code == 200
    assert unlinked.json()["series_id"] is None
    assert unlinked.json()["yoy_flagged"] is False


async def test_cross_user_link_is_404(client: AsyncClient) -> None:
    owner_id = await _owner_id(client, "owner-yoy@example.com")
    own_id = await _insert_policy_full(
        owner_id,
        named_insured="Mine",
        coverage_type="Property",
        effective_date="2024-01-01",
        total_premium="100",
    )

    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        other = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'other-yoy@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
    await engine.dispose()
    other_id = await _insert_policy_full(
        other,
        named_insured="Theirs",
        coverage_type="Property",
        effective_date="2023-01-01",
        total_premium="90",
    )

    response = await client.post(
        f"/api/v1/policies/{own_id}/link",
        json={"peer_policy_id": str(other_id)},
    )
    assert response.status_code == 404

    history = await client.get(f"/api/v1/policies/{other_id}/history")
    assert history.status_code == 404


async def test_unauthenticated_history_is_401(client: AsyncClient) -> None:
    response = await client.get(f"/api/v1/policies/{uuid4()}/history")
    assert response.status_code == 401
