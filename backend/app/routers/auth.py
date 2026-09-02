from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Request, Response
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.deps import get_current_user, get_db, get_redis
from app.errors import AppError
from app.models import User
from app.schemas import Credentials, UserOut
from app.security import hash_password, verify_password
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
    user = User(email=body.email, password_hash=hash_password(body.password))
    session.add(user)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        raise AppError(409, "EMAIL_TAKEN", "An account with this email already exists.")
    await session.refresh(user)
    await _issue_session(response, redis, settings, user)
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
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(user.password_hash, body.password):
        raise AppError(401, "INVALID_CREDENTIALS", "Email or password is incorrect.")
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
async def me(user: Annotated[UserOut, Depends(get_current_user)]) -> UserOut:
    return user
