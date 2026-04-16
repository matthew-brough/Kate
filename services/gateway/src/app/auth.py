from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.settings import settings


class TokenPayload(BaseModel):
    sub: str
    username: str


def require_auth(authorization: Annotated[str | None, Header()] = None) -> TokenPayload:
    if authorization is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing Authorization header")
    raw = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(raw, settings.jwt_secret, algorithms=["HS256"])
        return TokenPayload(sub=str(payload["sub"]), username=str(payload["username"]))
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


AuthDep = Annotated[TokenPayload, Depends(require_auth)]
