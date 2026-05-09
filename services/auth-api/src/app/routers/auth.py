from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models import User
from app.schemas import RegisterRequest, TokenResponse, UserRead, normalize_identity
from app.security import create_access_token, hash_password_async, verify_password_async

router = APIRouter(prefix="/auth", tags=["auth"])
log: structlog.stdlib.BoundLogger = structlog.get_logger()

MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _invalid_credentials() -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    session: AsyncSession = Depends(get_session),
) -> User:
    user = User(
        username=body.username,
        email=str(body.email),
        password_hash=await hash_password_async(body.password),
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Username or email already registered"
        ) from None
    log.info("user_registered", user_id=str(user.id), username=user.username)
    return user


@router.post("/token", response_model=TokenResponse)
async def token(
    form: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    username = normalize_identity(form.username)
    result = await session.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise _invalid_credentials()

    now = _now()
    if user.locked_until is not None and _as_utc(user.locked_until) > now:
        log.warning("login_rejected_locked", user_id=str(user.id), username=user.username)
        raise _invalid_credentials()

    if not await verify_password_async(form.password, user.password_hash):
        if user.locked_until is not None and _as_utc(user.locked_until) <= now:
            user.failed_login_attempts = 0
            user.locked_until = None
        user.failed_login_attempts += 1
        user.last_failed_login_at = now
        if user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS:
            user.locked_until = now + LOCKOUT_DURATION
            log.warning("account_locked", user_id=str(user.id), username=user.username)
        await session.commit()
        raise _invalid_credentials()

    user.failed_login_attempts = 0
    user.locked_until = None
    await session.commit()
    access_token = create_access_token(str(user.id), user.username)
    log.info("token_issued", user_id=str(user.id), username=user.username)
    return TokenResponse(access_token=access_token)
