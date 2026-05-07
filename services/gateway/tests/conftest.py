import os

os.environ.setdefault("APP_JWT_SECRET", "test-secret")

from collections.abc import AsyncGenerator, Generator
from datetime import UTC

import httpx as _httpx
import pytest
import respx
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.settings import settings


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient]:
    app_instance = create_app()
    async with _httpx.AsyncClient() as upstream:
        app_instance.state.http_client = upstream
        async with AsyncClient(
            transport=ASGITransport(app=app_instance), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture
def valid_token() -> str:
    from datetime import datetime, timedelta

    import jwt

    payload = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "username": "testuser",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(hours=1),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@pytest.fixture
def mock_upstream() -> Generator[respx.MockRouter]:
    with respx.mock(assert_all_called=False) as mock:
        yield mock
