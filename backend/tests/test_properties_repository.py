from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.models import Property
from app.repositories import properties as properties_repo
from app.repositories.users import create
from app.security import hash_password


async def test_get_for_user_returns_none_for_another_users_id(
    db_session: AsyncSession,
) -> None:
    owner = await create(db_session, "owner@example.com", hash_password("pw-owner1"))
    viewer = await create(db_session, "viewer@example.com", hash_password("pw-viewer"))
    await set_tenant(db_session, str(owner.id))
    prop = Property(user_id=owner.id, label="Harbor Ave")
    await properties_repo.add(db_session, prop)

    owned = await properties_repo.get_for_user(db_session, prop.id, owner.id)
    assert owned is not None
    assert owned.id == prop.id

    await set_tenant(db_session, str(viewer.id))
    assert await properties_repo.get_for_user(db_session, prop.id, viewer.id) is None
    assert await properties_repo.get_for_user(db_session, uuid4(), owner.id) is None
