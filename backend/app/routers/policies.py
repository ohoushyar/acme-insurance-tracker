from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.errors import AppError
from app.models import Policy
from app.policy_mapping import policy_to_out
from app.schemas import PolicyList, PolicyOut, UserOut

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


@router.get("", response_model=PolicyList)
async def list_policies(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyList:
    result = await session.execute(
        select(Policy)
        .where(Policy.user_id == user.id)
        .order_by(Policy.created_at.desc())
    )
    return PolicyList(items=[policy_to_out(row) for row in result.scalars().all()])


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyOut:
    result = await session.execute(
        select(Policy).where(Policy.id == policy_id, Policy.user_id == user.id)
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise AppError(404, "NOT_FOUND", "Policy not found.")
    return policy_to_out(policy)
