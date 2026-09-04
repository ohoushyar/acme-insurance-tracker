from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_tenant_db
from app.schemas import ReminderList, ReminderOut, UserOut
from app.services import reminders as reminder_service

router = APIRouter(prefix="/api/v1/reminders", tags=["reminders"])


@router.get("", response_model=ReminderList)
async def list_reminders(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> ReminderList:
    return await reminder_service.list_reminders(session, user.id)


@router.post("/{reminder_id}/read", response_model=ReminderOut)
async def mark_reminder_read(
    reminder_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> ReminderOut:
    return await reminder_service.mark_read(session, user.id, reminder_id)


@router.post("/{reminder_id}/unread", response_model=ReminderOut)
async def mark_reminder_unread(
    reminder_id: UUID,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_tenant_db)],
) -> ReminderOut:
    return await reminder_service.mark_unread(session, user.id, reminder_id)
