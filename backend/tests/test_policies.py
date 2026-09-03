import json
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Policy
from app.storage import document_storage_key
from tests.test_extraction_schema import HARBOR_COVE_EXTRACTED


async def _login(client: AsyncClient, email: str, password: str) -> None:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )


async def _owner_id(client: AsyncClient, email: str = "owner@example.com") -> UUID:
    await _login(client, email, "correct-horse")
    me = await client.get("/api/v1/auth/me")
    return UUID(me.json()["id"])


async def _insert_document(
    user_id: UUID,
    status: str,
    extracted: dict[str, Any] | None = None,
) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    document_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status, extracted
                )
                VALUES (
                    :id, :uid, 'harbor.pdf', 'application/pdf', 128,
                    :key, :status, CAST(:extracted AS jsonb)
                )
                """),
            {
                "id": document_id,
                "uid": user_id,
                "key": document_storage_key(user_id, document_id),
                "status": status,
                "extracted": json.dumps(extracted) if extracted is not None else None,
            },
        )
    await engine.dispose()
    return document_id


async def _insert_policy(
    user_id: UUID,
    source_document_id: UUID,
    named_insured: str = "Harbor Cove LLC",
) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    policy_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO policies (
                    id, user_id, source_document_id, named_insured,
                    carriers, deductibles, locations, extraction_confidence
                )
                VALUES (
                    :id, :uid, :doc_id, :named_insured,
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb
                )
                """),
            {
                "id": policy_id,
                "uid": user_id,
                "doc_id": source_document_id,
                "named_insured": named_insured,
            },
        )
    await engine.dispose()
    return policy_id


def _edited_extraction() -> dict[str, Any]:
    payload = json.loads(json.dumps(HARBOR_COVE_EXTRACTED))
    payload["named_insured"] = "Harbor Cove Condominium Association"
    payload["carriers"] = ["ICAT", "Indian Harbor"]
    payload["deductibles"] = [
        {"peril": "Named Hurricane", "amount": "3% (min $50,000)"},
        {"peril": "All Other Perils", "amount": "$5,000 per occurrence"},
    ]
    payload["locations"] = [
        {"label": "Building 1", "address": "100 Harbor Cove Drive, Tampa, FL"},
        {"label": "Building 3", "address": "120 Harbor Cove Drive, Tampa, FL"},
    ]
    payload["confidence"]["named_insured"] = 1.0
    payload["confidence"]["carriers"] = 1.0
    payload["confidence"]["deductibles"] = 1.0
    payload["confidence"]["locations"] = 1.0
    return payload


async def test_unauthenticated_policies_is_401(client: AsyncClient) -> None:
    listed = await client.get("/api/v1/policies")
    assert listed.status_code == 401
    assert listed.json()["error"]["code"] == "UNAUTHENTICATED"

    fetched = await client.get(f"/api/v1/policies/{uuid4()}")
    assert fetched.status_code == 401
    assert fetched.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_user_cannot_fetch_another_users_policy(client: AsyncClient) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'pol-b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        doc_b = uuid4()
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status
                )
                VALUES (
                    :id, :uid, 'harbor-b.pdf', 'application/pdf', 128,
                    :key, 'reviewed'
                )
                """),
            {
                "id": doc_b,
                "uid": user_b,
                "key": document_storage_key(user_b, doc_b),
            },
        )
    await engine.dispose()
    policy_b = await _insert_policy(user_b, doc_b, named_insured="Fenmore Park LLC")

    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.get(f"/api/v1/policies/{policy_b}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"

    listed = await client.get("/api/v1/policies")
    assert listed.status_code == 200
    ids = {item["id"] for item in listed.json()["items"]}
    assert str(policy_b) not in ids


async def test_confirm_inserts_policy_with_multi_deductible_and_locations(
    client: AsyncClient,
) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    edited = _edited_extraction()
    response = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=edited,
    )
    assert response.status_code == 200
    policy_id = response.json()["policy_id"]
    assert policy_id is not None

    listed = await client.get("/api/v1/policies")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    policy = items[0]
    assert policy["id"] == policy_id
    assert policy["source_document_id"] == str(document_id)
    assert policy["named_insured"] == "Harbor Cove Condominium Association"
    assert policy["carriers"] == ["ICAT", "Indian Harbor"]
    assert policy["deductibles"] == [
        {"peril": "Named Hurricane", "amount": "3% (min $50,000)"},
        {"peril": "All Other Perils", "amount": "$5,000 per occurrence"},
    ]
    assert policy["locations"][1]["label"] == "Building 3"
    assert isinstance(policy["total_premium"], str)
    assert Decimal(policy["total_premium"]) == Decimal("186500.00")

    detail = await client.get(f"/api/v1/policies/{policy_id}")
    assert detail.status_code == 200
    assert detail.json()["deductibles"][0]["amount"] == "3% (min $50,000)"
    assert detail.json()["confidence"]["named_insured"] == 1.0


async def test_reconfirm_updates_same_policy_in_place(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    first = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    assert first.status_code == 200
    policy_id = first.json()["policy_id"]

    edited = _edited_extraction()
    edited["named_insured"] = "Harbor Cove HOA"
    edited["deductibles"].append({"peril": "Earthquake", "amount": "5% (min $100,000)"})
    edited["confidence"]["named_insured"] = 1.0
    edited["confidence"]["deductibles"] = 1.0
    second = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=edited,
    )
    assert second.status_code == 200
    assert second.json()["policy_id"] == policy_id

    listed = await client.get("/api/v1/policies")
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == policy_id
    assert items[0]["named_insured"] == "Harbor Cove HOA"
    assert len(items[0]["deductibles"]) == 3
    assert items[0]["deductibles"][2]["peril"] == "Earthquake"


async def test_list_policies_is_empty_until_confirm(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    await _insert_document(user_id, "completed", extracted=HARBOR_COVE_EXTRACTED)
    listed = await client.get("/api/v1/policies")
    assert listed.status_code == 200
    assert listed.json()["items"] == []


async def test_cross_user_confirm_does_not_create_policy_for_caller(
    client: AsyncClient,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'pol-owner-b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        doc_b = uuid4()
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status, extracted
                )
                VALUES (
                    :id, :uid, 'harbor-b.pdf', 'application/pdf', 128,
                    :key, 'completed', CAST(:extracted AS jsonb)
                )
                """),
            {
                "id": doc_b,
                "uid": user_b,
                "key": document_storage_key(user_b, doc_b),
                "extracted": json.dumps(HARBOR_COVE_EXTRACTED),
            },
        )
    await engine.dispose()

    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.post(
        f"/api/v1/documents/{doc_b}/confirm",
        json=HARBOR_COVE_EXTRACTED,
    )
    assert response.status_code == 404
    listed = await client.get("/api/v1/policies")
    assert listed.json()["items"] == []


async def test_rls_hides_other_policies_without_application_filter(
    client: AsyncClient,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_a = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'rls-a@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'rls-b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        doc_a = uuid4()
        doc_b = uuid4()
        for doc_id, uid, filename in (
            (doc_a, user_a, "harbor-a.pdf"),
            (doc_b, user_b, "harbor-b.pdf"),
        ):
            await conn.execute(
                text("""
                    INSERT INTO documents (
                        id, user_id, original_filename, content_type, byte_size,
                        storage_key, status
                    )
                    VALUES (
                        :id, :uid, :filename, 'application/pdf', 128,
                        :key, 'reviewed'
                    )
                    """),
                {
                    "id": doc_id,
                    "uid": uid,
                    "filename": filename,
                    "key": document_storage_key(uid, doc_id),
                },
            )
    await engine.dispose()
    await _insert_policy(user_a, doc_a, named_insured="Owner A LLC")
    await _insert_policy(user_b, doc_b, named_insured="Owner B LLC")

    app_engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_a)},
        )
        rows = (await session.execute(text("SELECT user_id FROM policies"))).all()
        assert {row[0] for row in rows} == {user_a}

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_b)},
        )
        result = await session.execute(text("SELECT named_insured FROM policies"))
        assert [row[0] for row in result] == ["Owner B LLC"]

    await app_engine.dispose()
    assert client


async def test_rls_errors_on_policies_without_user_setting(
    client: AsyncClient,
) -> None:
    user_id = uuid4()
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO users (id, email, password_hash)
                VALUES (:id, 'rls-none@example.com', 'x')
                """),
            {"id": user_id},
        )
        doc_id = uuid4()
        await conn.execute(
            text("""
                INSERT INTO documents (
                    id, user_id, original_filename, content_type, byte_size,
                    storage_key, status
                )
                VALUES (
                    :id, :uid, 'harbor.pdf', 'application/pdf', 128,
                    :key, 'reviewed'
                )
                """),
            {
                "id": doc_id,
                "uid": user_id,
                "key": document_storage_key(user_id, doc_id),
            },
        )
    await engine.dispose()
    await _insert_policy(user_id, doc_id)

    app_engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(
        app_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        try:
            await session.execute(text("SELECT * FROM policies"))
            raised = False
        except DBAPIError:
            raised = True
    await app_engine.dispose()
    assert raised
    assert client


async def test_confirm_persists_long_named_insured(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    edited = _edited_extraction()
    edited["named_insured"] = "A" * 600
    edited["confidence"]["named_insured"] = 1.0
    response = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=edited,
    )
    assert response.status_code == 200
    listed = await client.get("/api/v1/policies")
    assert listed.json()["items"][0]["named_insured"] == "A" * 600


async def test_unknown_policy_is_404(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.get(f"/api/v1/policies/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


assert Policy.__tablename__ == "policies"
