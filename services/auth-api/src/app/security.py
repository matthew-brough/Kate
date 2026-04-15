from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.settings import settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(user_id: str, username: str) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": user_id,
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, object]:
    return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])  # type: ignore[no-any-return]
