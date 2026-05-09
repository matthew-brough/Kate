from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from starlette.concurrency import run_in_threadpool

from app.settings import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


async def hash_password_async(password: str) -> str:
    return await run_in_threadpool(hash_password, password)


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def verify_password_async(password: str, hashed: str) -> bool:
    return await run_in_threadpool(verify_password, password, hashed)


def create_access_token(user_id: str, username: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": user_id,
        "username": username,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")
