from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app import yoy
from app.errors import AppError
from app.extraction.schema import ExtractedPolicy
from app.models import Document, Policy, PolicySeries
from app.policy_mapping import apply_extracted, extracted_from_policy, policy_to_out
from app.repositories import policies as policies_repo
from app.repositories import policy_properties as policy_properties_repo
from app.repositories import policy_series as policy_series_repo
from app.repositories import properties as properties_repo
from app.repositories import transactions
from app.schemas import (
    LinkSuggestion,
    PolicyHistory,
    PolicyHistoryPoint,
    PolicyList,
    PolicyOut,
    PolicyPatch,
)


async def _require_owned(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> Policy:
    policy = await policies_repo.get_for_user(session, policy_id, user_id)
    if policy is None:
        raise AppError(404, "NOT_FOUND", "Policy not found.")
    return policy


def _policy_label(policy: Policy) -> str:
    return policy.named_insured or policy.policy_number or "Untitled policy"


async def _enrich_policy(
    session: AsyncSession,
    user_id: UUID,
    policy: Policy,
    property_ids: list[UUID],
    *,
    include_suggestions: bool,
    series_members_cache: dict[UUID, list[Policy]] | None = None,
    all_policies: list[Policy] | None = None,
    all_links: dict[UUID, list[UUID]] | None = None,
) -> PolicyOut:
    previous = None
    change = None
    flagged = False
    if policy.series_id is not None:
        if (
            series_members_cache is not None
            and policy.series_id in series_members_cache
        ):
            members = series_members_cache[policy.series_id]
        else:
            members = await policy_series_repo.members_for_series(
                session, policy.series_id, user_id
            )
        previous = yoy.previous_premium_for(policy, members)
        change = yoy.yoy_change_pct(policy.total_premium, previous)
        flagged = yoy.yoy_flagged(change)

    suggestions: list[LinkSuggestion] = []
    if include_suggestions:
        candidates_policies = all_policies
        links = all_links
        if candidates_policies is None:
            candidates_policies = await policies_repo.list_for_user(session, user_id)
            links = await policy_properties_repo.property_ids_for_policies(
                session, user_id, [item.id for item in candidates_policies]
            )
        assert links is not None
        suggestion_ids = yoy.suggest_link_ids(
            policy,
            set(property_ids),
            [
                (candidate, set(links.get(candidate.id, [])))
                for candidate in candidates_policies
            ],
        )
        by_id = {item.id: item for item in candidates_policies}
        suggestions = [
            LinkSuggestion(policy_id=sid, label=_policy_label(by_id[sid]))
            for sid in suggestion_ids
            if sid in by_id
        ]

    return policy_to_out(
        policy,
        property_ids,
        previous_premium=previous,
        yoy_change_pct=change,
        yoy_flagged=flagged,
        link_suggestions=suggestions,
    )


async def list_policies(session: AsyncSession, user_id: UUID) -> PolicyList:
    items = await policies_repo.list_for_user(session, user_id)
    links = await policy_properties_repo.property_ids_for_policies(
        session, user_id, [item.id for item in items]
    )
    series_ids = [item.series_id for item in items if item.series_id is not None]
    series_members = await policy_series_repo.list_by_series_ids(
        session, user_id, series_ids
    )
    return PolicyList(
        items=[
            await _enrich_policy(
                session,
                user_id,
                item,
                links.get(item.id, []),
                include_suggestions=False,
                series_members_cache=series_members,
            )
            for item in items
        ]
    )


async def get_policy(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> PolicyOut:
    policy = await _require_owned(session, user_id, policy_id)
    all_policies = await policies_repo.list_for_user(session, user_id)
    links = await policy_properties_repo.property_ids_for_policies(
        session, user_id, [item.id for item in all_policies]
    )
    return await _enrich_policy(
        session,
        user_id,
        policy,
        links.get(policy.id, []),
        include_suggestions=True,
        all_policies=all_policies,
        all_links=links,
    )


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
    return await get_policy(session, user_id, policy.id)


async def delete_policy(session: AsyncSession, user_id: UUID, policy_id: UUID) -> None:
    policy = await _require_owned(session, user_id, policy_id)
    series_id = policy.series_id
    await policies_repo.delete(session, policy)
    if series_id is not None:
        await _cleanup_series_if_empty(session, user_id, series_id)


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


async def get_history(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> PolicyHistory:
    policy = await _require_owned(session, user_id, policy_id)
    if policy.series_id is None:
        return PolicyHistory(items=[])
    members = await policy_series_repo.members_for_series(
        session, policy.series_id, user_id
    )
    return PolicyHistory(
        items=[
            PolicyHistoryPoint(
                year=point["year"],
                premium=point["premium"],
                policy_id=point["policy_id"],
            )
            for point in yoy.history_points(members)
        ]
    )


async def _cleanup_series_if_empty(
    session: AsyncSession, user_id: UUID, series_id: UUID
) -> None:
    count = await policy_series_repo.member_count(session, series_id, user_id)
    if count == 0:
        series = await policy_series_repo.get_for_user(session, series_id, user_id)
        if series is not None:
            await policy_series_repo.delete(session, series)


async def link_policies(
    session: AsyncSession,
    user_id: UUID,
    policy_id: UUID,
    peer_policy_id: UUID,
) -> PolicyOut:
    if policy_id == peer_policy_id:
        raise AppError(422, "VALIDATION_ERROR", "Cannot link a policy to itself.")
    policy = await _require_owned(session, user_id, policy_id)
    peer = await _require_owned(session, user_id, peer_policy_id)

    target_series_id = peer.series_id or policy.series_id
    if target_series_id is None:
        series = PolicySeries(user_id=user_id, label=None)
        await policy_series_repo.add(session, series)
        target_series_id = series.id

    orphan_ids: list[UUID] = []
    for member in (policy, peer):
        if member.series_id is not None and member.series_id != target_series_id:
            orphan_ids.append(member.series_id)
        member.series_id = target_series_id

    await transactions.flush(session)
    for orphan_id in orphan_ids:
        await _cleanup_series_if_empty(session, user_id, orphan_id)
    return await get_policy(session, user_id, policy.id)


async def unlink_policy(
    session: AsyncSession, user_id: UUID, policy_id: UUID
) -> PolicyOut:
    policy = await _require_owned(session, user_id, policy_id)
    series_id = policy.series_id
    policy.series_id = None
    await transactions.flush(session)
    if series_id is not None:
        await _cleanup_series_if_empty(session, user_id, series_id)
    return await get_policy(session, user_id, policy.id)
