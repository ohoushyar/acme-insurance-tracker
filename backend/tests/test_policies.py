import json
from datetime import date
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
    renewal_date: str | None = None,
) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    policy_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO policies (
                    id, user_id, source_document_id, named_insured,
                    renewal_date,
                    carriers, deductibles, locations, extraction_confidence
                )
                VALUES (
                    :id, :uid, :doc_id, :named_insured,
                    :renewal_date,
                    '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '{}'::jsonb
                )
                """),
            {
                "id": policy_id,
                "uid": user_id,
                "doc_id": source_document_id,
                "named_insured": named_insured,
                "renewal_date": (
                    None if renewal_date is None else date.fromisoformat(renewal_date)
                ),
            },
        )
    await engine.dispose()
    return policy_id


async def test_list_policies_orders_by_renewal_date_nulls_last(
    client: AsyncClient,
) -> None:
    user_id = await _owner_id(client)
    doc_later = await _insert_document(user_id, "reviewed")
    doc_earlier = await _insert_document(user_id, "reviewed")
    doc_null = await _insert_document(user_id, "reviewed")
    later_id = await _insert_policy(
        user_id, doc_later, named_insured="Later", renewal_date="2027-06-01"
    )
    earlier_id = await _insert_policy(
        user_id, doc_earlier, named_insured="Earlier", renewal_date="2026-10-01"
    )
    null_id = await _insert_policy(
        user_id, doc_null, named_insured="NoDate", renewal_date=None
    )

    listed = await client.get("/api/v1/policies")
    assert listed.status_code == 200
    ids = [item["id"] for item in listed.json()["items"]]
    assert ids == [str(earlier_id), str(later_id), str(null_id)]


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
    missing_id = uuid4()
    response = await client.get(f"/api/v1/policies/{missing_id}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
    deleted = await client.delete(f"/api/v1/policies/{missing_id}")
    assert deleted.status_code == 404
    assert deleted.json()["error"]["code"] == "NOT_FOUND"


async def test_unauthenticated_policy_writes_are_401(client: AsyncClient) -> None:
    patched = await client.patch(
        f"/api/v1/policies/{uuid4()}", json={"named_insured": "Harbor Cove LLC"}
    )
    assert patched.status_code == 401
    assert patched.json()["error"]["code"] == "UNAUTHENTICATED"

    deleted = await client.delete(f"/api/v1/policies/{uuid4()}")
    assert deleted.status_code == 401
    assert deleted.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_user_cannot_patch_or_delete_another_users_policy(
    client: AsyncClient,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'pol-write-b@example.com', 'x')
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
    patched = await client.patch(
        f"/api/v1/policies/{policy_b}",
        json={"named_insured": "Stolen"},
    )
    assert patched.status_code == 404
    assert patched.json()["error"]["code"] == "NOT_FOUND"

    deleted = await client.delete(f"/api/v1/policies/{policy_b}")
    assert deleted.status_code == 404
    assert deleted.json()["error"]["code"] == "NOT_FOUND"

    admin = create_async_engine(settings.admin_database_url)
    async with admin.begin() as conn:
        named = (
            await conn.execute(
                text("SELECT named_insured FROM policies WHERE id = :id"),
                {"id": policy_b},
            )
        ).scalar_one()
        exists = (
            await conn.execute(
                text("SELECT 1 FROM policies WHERE id = :id"),
                {"id": policy_b},
            )
        ).scalar_one_or_none()
    await admin.dispose()
    assert named == "Fenmore Park LLC"
    assert exists == 1


async def test_attach_other_users_property_is_404(client: AsyncClient) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'prop-b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        prop_b = (
            await conn.execute(
                text("""
                    INSERT INTO properties (id, user_id, label)
                    VALUES (gen_random_uuid(), :uid, 'Fenmore Park')
                    RETURNING id
                    """),
                {"uid": user_b},
            )
        ).scalar_one()
    await engine.dispose()

    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]

    attached = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": [str(prop_b)]},
    )
    assert attached.status_code == 404
    assert attached.json()["error"]["code"] == "NOT_FOUND"

    policy = await client.get(f"/api/v1/policies/{policy_id}")
    assert policy.status_code == 200
    assert policy.json()["property_ids"] == []


async def test_rls_hides_other_policy_properties_without_application_filter(
    client: AsyncClient,
) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_a = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'pp-rls-a@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'pp-rls-b@example.com', 'x')
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
            prop_id = (
                await conn.execute(
                    text("""
                        INSERT INTO properties (id, user_id, label)
                        VALUES (gen_random_uuid(), :uid, :label)
                        RETURNING id
                        """),
                    {
                        "uid": uid,
                        "label": "Harbor Ave" if uid == user_a else "Fenmore Park",
                    },
                )
            ).scalar_one()
            policy_id = uuid4()
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
                    "uid": uid,
                    "doc_id": doc_id,
                    "named_insured": (
                        "Owner A LLC" if uid == user_a else "Owner B LLC"
                    ),
                },
            )
            await conn.execute(
                text("""
                    INSERT INTO policy_properties (policy_id, property_id, user_id)
                    VALUES (:policy_id, :property_id, :uid)
                    """),
                {"policy_id": policy_id, "property_id": prop_id, "uid": uid},
            )
    await engine.dispose()

    app_engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(app_engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_a)},
        )
        rows = (
            await session.execute(text("SELECT user_id FROM policy_properties"))
        ).all()
        assert {row[0] for row in rows} == {user_a}

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_b)},
        )
        result = await session.execute(text("SELECT user_id FROM policy_properties"))
        assert [row[0] for row in result] == [user_b]

    await app_engine.dispose()
    assert client


async def test_patch_policy_keeps_harbor_cove_deductibles(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]

    patched = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"named_insured": "Harbor Cove HOA"},
    )
    assert patched.status_code == 200
    body = patched.json()
    assert body["named_insured"] == "Harbor Cove HOA"
    assert body["deductibles"] == [
        {"peril": "Named Hurricane", "amount": "3% (min $50,000)"},
        {"peril": "All Other Perils", "amount": "$5,000 per occurrence"},
    ]
    assert body["locations"][1]["label"] == "Building 3"

    junk = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"term_premium": "185000 approx"},
    )
    assert junk.status_code == 422
    assert junk.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_delete_property_unlinks_and_leaves_the_policy(
    client: AsyncClient,
) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]

    created = await client.post(
        "/api/v1/properties",
        json={"label": "Harbor Cove", "address": "100 Harbor Cove Drive, Tampa, FL"},
    )
    assert created.status_code == 201
    property_id = created.json()["id"]

    attached = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": [property_id]},
    )
    assert attached.status_code == 200
    assert attached.json()["property_ids"] == [property_id]

    listed_prop = await client.get(f"/api/v1/properties/{property_id}")
    assert listed_prop.status_code == 200
    assert listed_prop.json()["policy_ids"] == [policy_id]

    deleted = await client.delete(f"/api/v1/properties/{property_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/properties/{property_id}")
    assert missing.status_code == 404

    policy = await client.get(f"/api/v1/policies/{policy_id}")
    assert policy.status_code == 200
    assert policy.json()["property_ids"] == []
    assert policy.json()["named_insured"] == "Harbor Cove Condominium Association"


async def test_delete_policy_leaves_the_document(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]
    assert confirmed.json()["id"] == str(document_id)

    deleted = await client.delete(f"/api/v1/policies/{policy_id}")
    assert deleted.status_code == 204

    missing = await client.get(f"/api/v1/policies/{policy_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "NOT_FOUND"

    document = await client.get(f"/api/v1/documents/{document_id}")
    assert document.status_code == 200
    body = document.json()
    assert body["status"] == "reviewed"
    assert body["extracted"]["named_insured"] == "Harbor Cove Condominium Association"
    assert body["policy_id"] is None


async def test_patch_omitting_property_ids_keeps_links(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]
    created = await client.post("/api/v1/properties", json={"label": "Harbor Cove"})
    property_id = created.json()["id"]
    attached = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": [property_id]},
    )
    assert attached.status_code == 200
    assert attached.json()["property_ids"] == [property_id]

    renamed = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"named_insured": "Harbor Cove HOA"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["named_insured"] == "Harbor Cove HOA"
    assert renamed.json()["property_ids"] == [property_id]

    cleared = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": []},
    )
    assert cleared.status_code == 200
    assert cleared.json()["property_ids"] == []

    null_ids = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": None},
    )
    assert null_ids.status_code == 422
    assert null_ids.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_reconfirm_keeps_property_ids(client: AsyncClient) -> None:
    user_id = await _owner_id(client)
    document_id = await _insert_document(
        user_id, "completed", extracted=HARBOR_COVE_EXTRACTED
    )
    confirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=_edited_extraction(),
    )
    policy_id = confirmed.json()["policy_id"]

    created = await client.post("/api/v1/properties", json={"label": "Harbor Cove"})
    property_id = created.json()["id"]
    attached = await client.patch(
        f"/api/v1/policies/{policy_id}",
        json={"property_ids": [property_id]},
    )
    assert attached.status_code == 200
    assert attached.json()["property_ids"] == [property_id]

    edited = _edited_extraction()
    edited["named_insured"] = "Harbor Cove HOA"
    edited["confidence"]["named_insured"] = 1.0
    reconfirmed = await client.post(
        f"/api/v1/documents/{document_id}/confirm",
        json=edited,
    )
    assert reconfirmed.status_code == 200
    assert reconfirmed.json()["policy_id"] == policy_id

    policy = await client.get(f"/api/v1/policies/{policy_id}")
    assert policy.status_code == 200
    assert policy.json()["named_insured"] == "Harbor Cove HOA"
    assert policy.json()["property_ids"] == [property_id]


assert Policy.__tablename__ == "policies"
