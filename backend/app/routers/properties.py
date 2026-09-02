from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.errors import AppError
from app.models import Property
from app.schemas import PropertyList, PropertyOut, UserOut

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


@router.get("", response_model=PropertyList)
async def list_properties(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyList:
    result = await session.execute(
        select(Property)
        .where(Property.user_id == user.id)
        .order_by(Property.created_at)
    )
    return PropertyList(items=list(result.scalars().all()))


@router.get("/{property_id}", response_model=PropertyOut)
async def get_property(
    property_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Property:
    result = await session.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user.id)
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise AppError(404, "NOT_FOUND", "Property not found.")
    return prop
