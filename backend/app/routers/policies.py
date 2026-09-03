from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.errors import AppError
from app.extraction.schema import ExtractedPolicy
from app.models import Policy
from app.policy_mapping import (
    apply_extracted,
    extracted_from_policy,
    policy_to_out,
    property_ids_for_policies,
    replace_property_links,
)
from app.schemas import PolicyList, PolicyOut, PolicyPatch, UserOut

router = APIRouter(prefix="/api/v1/policies", tags=["policies"])


async def _get_owned_policy(
    policy_id: UUID,
    user: UserOut,
    session: AsyncSession,
) -> Policy:
    result = await session.execute(
        select(Policy).where(Policy.id == policy_id, Policy.user_id == user.id)
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise AppError(404, "NOT_FOUND", "Policy not found.")
    return policy


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
    policies = list(result.scalars().all())
    links = await property_ids_for_policies(session, [item.id for item in policies])
    return PolicyList(
        items=[policy_to_out(item, links.get(item.id, [])) for item in policies]
    )


@router.get("/{policy_id}", response_model=PolicyOut)
async def get_policy(
    policy_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyOut:
    policy = await _get_owned_policy(policy_id, user, session)
    links = await property_ids_for_policies(session, [policy.id])
    return policy_to_out(policy, links.get(policy.id, []))


@router.patch("/{policy_id}", response_model=PolicyOut)
async def patch_policy(
    policy_id: UUID,
    body: PolicyPatch,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> PolicyOut:
    policy = await _get_owned_policy(policy_id, user, session)
    updates = body.model_dump(exclude_unset=True, exclude={"property_ids"})
    if updates:
        current = extracted_from_policy(policy).model_dump()
        current.update(updates)
        apply_extracted(policy, ExtractedPolicy.model_validate(current))
    if "property_ids" in body.model_fields_set:
        await replace_property_links(
            session, user.id, policy.id, body.property_ids or []
        )
    await session.flush()
    links = await property_ids_for_policies(session, [policy.id])
    return policy_to_out(policy, links.get(policy.id, []))


@router.delete("/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> Response:
    policy = await _get_owned_policy(policy_id, user, session)
    await session.delete(policy)
    return Response(status_code=204)
