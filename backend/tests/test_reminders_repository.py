from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import set_tenant
from app.models import Document, Policy, Reminder
from app.repositories import reminders as reminders_repo
from app.repositories.users import create
from app.security import hash_password
from app.storage import document_storage_key


async def test_get_for_user_returns_none_for_another_users_id(
    db_session: AsyncSession,
) -> None:
    owner = await create(db_session, "owner-r@example.com", hash_password("pw-owner1"))
    viewer = await create(
        db_session, "viewer-r@example.com", hash_password("pw-viewer")
    )
    await set_tenant(db_session, str(owner.id))
    document_id = uuid4()
    document = Document(
        id=document_id,
        user_id=owner.id,
        original_filename="p.pdf",
        content_type="application/pdf",
        byte_size=128,
        storage_key=document_storage_key(owner.id, document_id),
        status="reviewed",
    )
    db_session.add(document)
    await db_session.flush()
    policy = Policy(
        user_id=owner.id,
        source_document_id=document.id,
        named_insured="Harbor Cove LLC",
        renewal_date=datetime.now(UTC).date() + timedelta(days=45),
        carriers=[],
        deductibles=[],
        locations=[],
        extraction_confidence={},
    )
    db_session.add(policy)
    await db_session.flush()
    reminder = Reminder(
        user_id=owner.id,
        policy_id=policy.id,
        threshold_days=60,
        renewal_date=policy.renewal_date,
    )
    await reminders_repo.add(db_session, reminder)

    owned = await reminders_repo.get_for_user(db_session, reminder.id, owner.id)
    assert owned is not None
    assert owned.id == reminder.id

    await set_tenant(db_session, str(viewer.id))
    assert await reminders_repo.get_for_user(db_session, reminder.id, viewer.id) is None


async def test_insert_if_missing_is_idempotent(db_session: AsyncSession) -> None:
    owner = await create(db_session, "owner-i@example.com", hash_password("pw-owner1"))
    await set_tenant(db_session, str(owner.id))
    document_id = uuid4()
    document = Document(
        id=document_id,
        user_id=owner.id,
        original_filename="p.pdf",
        content_type="application/pdf",
        byte_size=128,
        storage_key=document_storage_key(owner.id, document_id),
        status="reviewed",
    )
    db_session.add(document)
    await db_session.flush()
    policy = Policy(
        user_id=owner.id,
        source_document_id=document.id,
        named_insured="Harbor Cove LLC",
        renewal_date=datetime.now(UTC).date() + timedelta(days=45),
        carriers=[],
        deductibles=[],
        locations=[],
        extraction_confidence={},
    )
    db_session.add(policy)
    await db_session.flush()
    await reminders_repo.insert_if_missing(
        db_session,
        Reminder(
            user_id=owner.id,
            policy_id=policy.id,
            threshold_days=60,
            renewal_date=policy.renewal_date,
        ),
    )
    await reminders_repo.insert_if_missing(
        db_session,
        Reminder(
            user_id=owner.id,
            policy_id=policy.id,
            threshold_days=60,
            renewal_date=policy.renewal_date,
        ),
    )
    rows = await reminders_repo.list_for_user(db_session, owner.id)
    assert len(rows) == 1
