from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.schemas import PolicyList, PolicyOut, PolicyPatch, UserOut
from app.services import policies as policy_service

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


@router.get("", response_model=PolicyList)
async def list_policies(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyList:
    return await policy_service.list_policies(session, user.id)


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyOut:
    return await policy_service.get_policy(session, user.id, policy_id)


@router.patch("/{policy_id}", response_model=PolicyOut)
async def patch_policy(
    policy_id: UUID,
    body: PolicyPatch,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyOut:
    return await policy_service.patch_policy(session, user.id, policy_id, body)


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Response:
    await policy_service.delete_policy(session, user.id, policy_id)
    return Response(status_code=204)
