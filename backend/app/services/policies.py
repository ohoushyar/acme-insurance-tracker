from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.extraction.schema import ExtractedPolicy
from app.models import Document, Policy
from app.policy_mapping import apply_extracted, extracted_from_policy, policy_to_out
from app.repositories import policies as policies_repo
from app.repositories import policy_properties as policy_properties_repo
from app.repositories import properties as properties_repo
from app.repositories import transactions
from app.schemas import PolicyList, PolicyOut, PolicyPatch


async def _require_owned(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> Policy:
    policy = await policies_repo.get_for_user(session, policy_id, user_id)
    if policy is None:
        raise AppError(404, "NOT_FOUND", "Policy not found.")
    return policy


async def list_policies(session: AsyncSession, user_id: UUID) -> PolicyList:
    items = await policies_repo.list_for_user(session, user_id)
    links = await policy_properties_repo.property_ids_for_policies(
        session, user_id, [item.id for item in items]
    )
    return PolicyList(
        items=[policy_to_out(item, links.get(item.id, [])) for item in items]
    )


async def get_policy(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> PolicyOut:
    policy = await _require_owned(session, user_id, policy_id)
    links = await policy_properties_repo.property_ids_for_policies(
        session, user_id, [policy.id]
    )
    return policy_to_out(policy, links.get(policy.id, []))


async def replace_property_links(
    session: AsyncSession,
    user_id: UUID,
    policy_id: UUID,
    property_ids: list[UUID],
) -> None:
    unique_ids = list(dict.fromkeys(property_ids))
    if unique_ids:
        found = await properties_repo.ids_owned_by_user(session, user_id, unique_ids)
        if found != set(unique_ids):
            raise AppError(404, "NOT_FOUND", "Property not found.")
    await policy_properties_repo.replace_links(session, user_id, policy_id, unique_ids)


async def patch_policy(
    session: AsyncSession,
    user_id: UUID,
    policy_id: UUID,
    body: PolicyPatch,
) -> PolicyOut:
    policy = await _require_owned(session, user_id, policy_id)
    updates = body.model_dump(exclude_unset=True, exclude={"property_ids"})
    if updates:
        current = extracted_from_policy(policy).model_dump()
        current.update(updates)
        apply_extracted(policy, ExtractedPolicy.model_validate(current))
    if "property_ids" in body.model_fields_set:
        await replace_property_links(
            session, user_id, policy.id, body.property_ids or []
        )
    await transactions.flush(session)
    links = await policy_properties_repo.property_ids_for_policies(
        session, user_id, [policy.id]
    )
    return policy_to_out(policy, links.get(policy.id, []))


async def delete_policy(session: AsyncSession, user_id: UUID, policy_id: UUID) -> None:
    policy = await _require_owned(session, user_id, policy_id)
    await policies_repo.delete(session, policy)


async def upsert_from_extracted(
    session: AsyncSession,
    user_id: UUID,
    document: Document,
    extracted: ExtractedPolicy,
) -> Policy:
    policy = await policies_repo.get_by_source_document(session, document.id, user_id)
    if policy is None:
        policy = Policy(
            user_id=user_id,
            source_document_id=document.id,
        )
        await policies_repo.add(session, policy)
    apply_extracted(policy, extracted)
    await transactions.flush(session)
    return policy
