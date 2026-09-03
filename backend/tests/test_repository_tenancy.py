from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.repositories import policies as policies_repo
from app.repositories import policy_properties as policy_properties_repo
from tests.test_policies import _insert_document, _insert_policy


async def _insert_user(email: str) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("""
                    INSERT INTO users (id, email, password_hash)
                    VALUES (gen_random_uuid(), :email, 'x')
                    RETURNING id
                    """),
                {"email": email},
            )
        ).scalar_one()
    await engine.dispose()
    return user_id


async def _insert_property(user_id: UUID) -> UUID:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    property_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO properties (id, user_id, label)
                VALUES (:id, :uid, 'Harbor Ave')
                """),
            {"id": property_id, "uid": user_id},
        )
    await engine.dispose()
    return property_id


async def _insert_link(user_id: UUID, policy_id: UUID, property_id: UUID) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    async with engine.begin() as conn:
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


async def test_join_queries_filter_by_user_id(app) -> None:
    _ = app
    user_a = await _insert_user("tenancy-a@example.com")
    user_b = await _insert_user("tenancy-b@example.com")
    doc_a = await _insert_document(user_a, "reviewed")
    doc_b = await _insert_document(user_b, "reviewed")
    policy_a = await _insert_policy(user_a, doc_a)
    policy_b = await _insert_policy(user_b, doc_b)
    prop_a = await _insert_property(user_a)
    prop_b = await _insert_property(user_b)
    await _insert_link(user_a, policy_a, prop_a)
    await _insert_link(user_b, policy_b, prop_b)

    settings = get_settings()
    engine = create_async_engine(settings.admin_database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        policy_ids = await policies_repo.ids_by_source_document_ids(
            session, user_a, [doc_a, doc_b]
        )
        property_ids = await policy_properties_repo.property_ids_for_policies(
            session, user_a, [policy_a, policy_b]
        )
        linked_policies = await policy_properties_repo.policy_ids_for_properties(
            session, user_a, [prop_a, prop_b]
        )
    await engine.dispose()

    assert policy_ids == {doc_a: policy_a}
    assert property_ids == {policy_a: [prop_a], policy_b: []}
    assert linked_policies == {prop_a: [policy_a], prop_b: []}
