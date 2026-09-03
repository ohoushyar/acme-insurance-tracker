from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.schemas import (
    PropertyCreate,
    PropertyList,
    PropertyOut,
    PropertyPatch,
    UserOut,
)
from app.services import properties as property_service

router = APIRouter(prefix="/api/v1/properties", tags=["properties"])


@router.get("", response_model=PropertyList)
async def list_properties(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyList:
    return await property_service.list_properties(session, user.id)


@router.post("", response_model=PropertyOut, status_code=201)
async def create_property(
    body: PropertyCreate,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    return await property_service.create_property(session, user.id, body)


@router.get("/{property_id}", response_model=PropertyOut)
async def get_property(
    property_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    return await property_service.get_property(session, user.id, property_id)


@router.patch("/{property_id}", response_model=PropertyOut)
async def patch_property(
    property_id: UUID,
    body: PropertyPatch,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PropertyOut:
    return await property_service.patch_property(session, user.id, property_id, body)


@router.delete("/{property_id}", status_code=204)
async def delete_property(
    property_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Response:
    await property_service.delete_property(session, user.id, property_id)
    return Response(status_code=204)
