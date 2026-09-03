from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError
from app.models import Property
from app.policy_mapping import property_to_out
from app.repositories import policy_properties as policy_properties_repo
from app.repositories import properties as properties_repo
from app.repositories import transactions
from app.schemas import PropertyCreate, PropertyList, PropertyOut, PropertyPatch


async def _require_owned(
    session: AsyncSession, user_id: UUID, property_id: UUID
) -> Property:
    prop = await properties_repo.get_for_user(session, property_id, user_id)
    if prop is None:
        raise AppError(404, "NOT_FOUND", "Property not found.")
    return prop


async def list_properties(session: AsyncSession, user_id: UUID) -> PropertyList:
    items = await properties_repo.list_for_user(session, user_id)
    links = await policy_properties_repo.policy_ids_for_properties(
        session, user_id, [item.id for item in items]
    )
    return PropertyList(
        items=[property_to_out(item, links.get(item.id, [])) for item in items]
    )


async def get_property(
    session: AsyncSession, user_id: UUID, property_id: UUID
) -> PropertyOut:
    prop = await _require_owned(session, user_id, property_id)
    links = await policy_properties_repo.policy_ids_for_properties(
        session, user_id, [prop.id]
    )
    return property_to_out(prop, links.get(prop.id, []))


async def create_property(
    session: AsyncSession, user_id: UUID, body: PropertyCreate
) -> PropertyOut:
    prop = Property(
        user_id=user_id,
        label=body.label,
        address=body.address,
        stated_value=body.stated_value,
    )
    await properties_repo.add(session, prop)
    return property_to_out(prop, [])


async def patch_property(
    session: AsyncSession,
    user_id: UUID,
    property_id: UUID,
    body: PropertyPatch,
) -> PropertyOut:
    prop = await _require_owned(session, user_id, property_id)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(prop, field, value)
    prop.updated_at = datetime.now(UTC)
    await transactions.flush(session)
    links = await policy_properties_repo.policy_ids_for_properties(
        session, user_id, [prop.id]
    )
    return property_to_out(prop, links.get(prop.id, []))


async def delete_property(
    session: AsyncSession, user_id: UUID, property_id: UUID
) -> None:
    prop = await _require_owned(session, user_id, property_id)
    await properties_repo.delete(session, prop)
