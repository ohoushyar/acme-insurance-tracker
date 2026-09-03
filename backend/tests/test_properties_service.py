from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.errors import AppError
from app.repositories.users import create
from app.security import hash_password
from app.services import properties as property_service


async def test_get_property_not_found_is_404(db_session: AsyncSession) -> None:
    owner = await create(db_session, "owner@example.com", hash_password("pw-owner1"))
    await set_tenant(db_session, str(owner.id))
    with pytest.raises(AppError) as exc:
        await property_service.get_property(db_session, owner.id, uuid4())
    assert exc.value.status_code == 404
    assert exc.value.code == "NOT_FOUND"
