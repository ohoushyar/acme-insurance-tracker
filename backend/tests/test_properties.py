from decimal import Decimal
from uuid import UUID, uuid4

from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Property


async def _seed_users_and_properties() -> tuple[UUID, UUID, UUID, UUID]:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_a = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'a@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        user_b = (await conn.execute(text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), 'b@example.com', 'x')
                    RETURNING id
                    """))).scalar_one()
        prop_a = (
            await conn.execute(
                text("""
                    INSERT INTO properties (id, user_id, label)
                    VALUES (gen_random_uuid(), :uid, 'Harbor Ave')
                    RETURNING id
                    """),
                {"uid": user_a},
            )
        ).scalar_one()
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
    return user_a, user_b, prop_a, prop_b


async def _login(client: AsyncClient, email: str, password: str) -> None:
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": password}
    )


async def test_unauthenticated_properties_is_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/properties")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_list_properties_omits_other_users_rows(client: AsyncClient) -> None:
    _, _, prop_a, prop_b = await _seed_users_and_properties()
    await _login(client, "viewer@example.com", "correct-horse")
    # Re-seed viewer's own row via register user... list should not include A/B
    response = await client.get("/api/v1/properties")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(prop_a) not in ids
    assert str(prop_b) not in ids


async def test_user_cannot_fetch_another_users_property(client: AsyncClient) -> None:
    _, _, _, prop_b = await _seed_users_and_properties()
    await _login(client, "viewer@example.com", "correct-horse")
    response = await client.get(f"/api/v1/properties/{prop_b}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_user_can_list_and_fetch_own_property(client: AsyncClient) -> None:
    settings = get_settings()
    await _login(client, "owner@example.com", "correct-horse")
    me = (await client.get("/api/v1/auth/me")).json()
    owner_id = me["id"]

    admin = create_async_engine(settings.admin_database_url)
    async with admin.begin() as conn:
        prop_id = (
            await conn.execute(
                text("""
                    INSERT INTO properties (id, user_id, label)
                    VALUES (gen_random_uuid(), :uid, 'Sundale Apartments')
                    RETURNING id
                    """),
                {"uid": owner_id},
            )
        ).scalar_one()
    await admin.dispose()

    listed = await client.get("/api/v1/properties")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["label"] == "Sundale Apartments"
    assert items[0]["user_id"] == owner_id

    detail = await client.get(f"/api/v1/properties/{prop_id}")
    assert detail.status_code == 200
    assert detail.json()["id"] == str(prop_id)


async def test_rls_hides_other_rows_without_application_filter(
    client: AsyncClient,
) -> None:
    """If a handler forgets WHERE user_id = ..., RLS must still isolate."""
    user_a, user_b, _, _ = await _seed_users_and_properties()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_a)},
        )
        rows = (await session.execute(text("SELECT user_id FROM properties"))).all()
        assert {row[0] for row in rows} == {user_a}

    async with factory() as session:
        await session.execute(
            text("SELECT set_config('app.user_id', :uid, true)"),
            {"uid": str(user_b)},
        )
        result = await session.execute(text("SELECT label FROM properties"))
        assert [row[0] for row in result] == ["Fenmore Park"]

    await engine.dispose()
    assert client  # keep fixture wired so schema exists


async def test_rls_errors_without_user_setting(client: AsyncClient) -> None:
    await _seed_users_and_properties()
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        try:
            await session.execute(text("SELECT * FROM properties"))
            raised = False
        except DBAPIError:
            raised = True
    await engine.dispose()
    assert raised
    assert client


async def test_unknown_property_is_404(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    missing_id = uuid4()
    response = await client.get(f"/api/v1/properties/{missing_id}")
    assert response.status_code == 404
    deleted = await client.delete(f"/api/v1/properties/{missing_id}")
    assert deleted.status_code == 404
    assert deleted.json()["error"]["code"] == "NOT_FOUND"


async def test_unauthenticated_property_writes_are_401(client: AsyncClient) -> None:
    created = await client.post("/api/v1/properties", json={"label": "Harbor Ave"})
    assert created.status_code == 401
    assert created.json()["error"]["code"] == "UNAUTHENTICATED"

    patched = await client.patch(
        f"/api/v1/properties/{uuid4()}", json={"label": "Harbor Ave"}
    )
    assert patched.status_code == 401
    assert patched.json()["error"]["code"] == "UNAUTHENTICATED"

    deleted = await client.delete(f"/api/v1/properties/{uuid4()}")
    assert deleted.status_code == 401
    assert deleted.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_user_cannot_patch_or_delete_another_users_property(
    client: AsyncClient,
) -> None:
    _, _, _, prop_b = await _seed_users_and_properties()
    await _login(client, "viewer@example.com", "correct-horse")

    patched = await client.patch(
        f"/api/v1/properties/{prop_b}", json={"label": "Stolen"}
    )
    assert patched.status_code == 404
    assert patched.json()["error"]["code"] == "NOT_FOUND"

    deleted = await client.delete(f"/api/v1/properties/{prop_b}")
    assert deleted.status_code == 404
    assert deleted.json()["error"]["code"] == "NOT_FOUND"


async def test_create_property_empty_label_is_422(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    response = await client.post("/api/v1/properties", json={"label": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_patch_property_empty_label_is_422(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    created = await client.post("/api/v1/properties", json={"label": "Harbor Ave"})
    property_id = created.json()["id"]

    for payload in ({"label": ""}, {"label": "   "}):
        patched = await client.patch(f"/api/v1/properties/{property_id}", json=payload)
        assert patched.status_code == 422
        assert patched.json()["error"]["code"] == "VALIDATION_ERROR"

    kept = await client.get(f"/api/v1/properties/{property_id}")
    assert kept.json()["label"] == "Harbor Ave"


async def test_stated_value_accepts_formatted_money_and_rejects_junk(
    client: AsyncClient,
) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    created = await client.post(
        "/api/v1/properties",
        json={"label": "Harbor Cove", "stated_value": "$25,000,000"},
    )
    assert created.status_code == 201
    assert Decimal(created.json()["stated_value"]) == Decimal(25000000)

    junk = await client.post(
        "/api/v1/properties",
        json={"label": "Fenmore", "stated_value": "approx 25M"},
    )
    assert junk.status_code == 422
    assert junk.json()["error"]["code"] == "VALIDATION_ERROR"
    assert "must be a money amount" in junk.json()["error"]["message"]

    patched_ok = await client.patch(
        f"/api/v1/properties/{created.json()['id']}",
        json={"stated_value": "$1,250,000.50"},
    )
    assert patched_ok.status_code == 200
    assert Decimal(patched_ok.json()["stated_value"]) == Decimal("1250000.50")

    patched_junk = await client.patch(
        f"/api/v1/properties/{created.json()['id']}",
        json={"stated_value": "approx 25M"},
    )
    assert patched_junk.status_code == 422
    assert "must be a money amount" in patched_junk.json()["error"]["message"]


async def test_create_and_patch_own_property(client: AsyncClient) -> None:
    await _login(client, "owner@example.com", "correct-horse")
    created = await client.post(
        "/api/v1/properties",
        json={
            "label": "Harbor Cove",
            "address": "100 Harbor Cove Drive, Tampa, FL",
            "stated_value": "25000000.00",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["label"] == "Harbor Cove"
    assert body["address"] == "100 Harbor Cove Drive, Tampa, FL"
    assert body["stated_value"] == "25000000.00"
    assert body["policy_ids"] == []
    assert body["updated_at"]

    patched = await client.patch(
        f"/api/v1/properties/{body['id']}",
        json={"label": "Harbor Cove HOA"},
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Harbor Cove HOA"
    assert patched.json()["address"] == "100 Harbor Cove Drive, Tampa, FL"
    assert patched.json()["stated_value"] == "25000000.00"


# Keep Property imported so a missing model fails collection, not a surprise later.
assert Property.__tablename__ == "properties"
