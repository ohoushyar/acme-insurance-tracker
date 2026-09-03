from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.errors import AppError
from app.models import Property
from app.policy_mapping import policy_ids_for_properties, property_to_out
from app.schemas import (
    PropertyCreate,
    PropertyList,
    PropertyOut,
    PropertyPatch,
    UserOut,
)

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


async def _get_owned_property(
    property_id: UUID,
    user: UserOut,
    session: AsyncSession,
) -> Property:
    result = await session.execute(
        select(Property).where(Property.id == property_id, Property.user_id == user.id)
    )
    prop = result.scalar_one_or_none()
    if prop is None:
        raise AppError(404, "NOT_FOUND", "Property not found.")
    return prop


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
    properties = list(result.scalars().all())
    links = await policy_ids_for_properties(session, [item.id for item in properties])
    return PropertyList(
        items=[property_to_out(item, links.get(item.id, [])) for item in properties]
    )


@router.post("", response_model=PropertyOut, status_code=201)
async def create_property(
    body: PropertyCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    prop = Property(
        user_id=user.id,
        label=body.label,
        address=body.address,
        stated_value=body.stated_value,
    )
    session.add(prop)
    await session.flush()
    return property_to_out(prop, [])


@router.get("/{property_id}", response_model=PropertyOut)
async def get_property(
    property_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    prop = await _get_owned_property(property_id, user, session)
    links = await policy_ids_for_properties(session, [prop.id])
    return property_to_out(prop, links.get(prop.id, []))


@router.patch("/{property_id}", response_model=PropertyOut)
async def patch_property(
    property_id: UUID,
    body: PropertyPatch,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    prop = await _get_owned_property(property_id, user, session)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(prop, field, value)
    prop.updated_at = datetime.now(UTC)
    await session.flush()
    links = await policy_ids_for_properties(session, [prop.id])
    return property_to_out(prop, links.get(prop.id, []))


@router.delete("/{property_id}", status_code=204)
async def delete_property(
    property_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Response:
    prop = await _get_owned_property(property_id, user, session)
    await session.delete(prop)
    return Response(status_code=204)
