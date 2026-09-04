from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.deps import get_current_user, get_db, get_redis
from app.models import User
from app.schemas import (
    ChangePassword,
    Credentials,
    EmailTokenIn,
    ForgotPasswordIn,
    ResetPasswordIn,
    UserOut,
)
from app.services import auth as auth_service
from app.sessions import delete_session, new_session_token, store_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
log = structlog.get_logger()


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
        path="/",
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
    )


async def _issue_session(
    response: Response,
    redis: Redis,
    settings: Settings,
    user: User,
) -> None:
    token = new_session_token()
    await store_session(redis, token, user.id, user.email, user.created_at, settings)
    _set_session_cookie(response, token, settings)


@router.post("/register", status_code=201, response_model=UserOut)
async def register(
    body: Credentials,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = await auth_service.register(session, body.email, body.password)
    await _issue_session(response, redis, settings, user)
    try:
        await auth_service.enqueue_verification(session, redis, user.id)
    except Exception:  # noqa: BLE001
        log.info("verify_email_enqueue_failed", user_id=str(user.id))
    log.info("user_registered", user_id=str(user.id))
    return user


@router.post("/login", response_model=UserOut)
async def login(
    body: Credentials,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    user = await auth_service.login(session, body.email, body.password)
    await _issue_session(response, redis, settings, user)
    log.info("user_logged_in", user_id=str(user.id))
    return user


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    redis: Annotated[Redis, Depends(get_redis)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await delete_session(redis, token)
    _clear_session_cookie(response, settings)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
async def me(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await auth_service.get_user(session, user.id)


@router.post("/password", status_code=204)
async def change_password(
    body: ChangePassword,
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await auth_service.change_password(
        session, user.id, body.current_password, body.new_password
    )
    return Response(status_code=204)


@router.post("/resend-verification", status_code=204)
async def resend_verification(
    user: Annotated[UserOut, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    await auth_service.enqueue_verification(
        session, redis, user.id, require_cooldown=True
    )
    return Response(status_code=204)


@router.post("/verify-email", response_model=UserOut)
async def verify_email(
    body: EmailTokenIn,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> User:
    return await auth_service.verify_email(session, redis, body.token)


@router.post("/forgot-password", status_code=204)
async def forgot_password(
    body: ForgotPasswordIn,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    await auth_service.enqueue_password_reset(session, redis, body.email)
    return Response(status_code=204)


@router.post("/reset-password", status_code=204)
async def reset_password(
    body: ResetPasswordIn,
    session: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> Response:
    await auth_service.reset_password(session, redis, body.token, body.password)
    return Response(status_code=204)
