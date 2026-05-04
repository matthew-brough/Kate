import os

os.environ.setdefault("CHAOS_TOKEN", "test-chaos-token")

import pytest
from starlette.testclient import TestClient

from app.main import CHAOS_TOKEN, app


@pytest.fixture
def client() -> TestClient:
    return TestClient(
        app,
        raise_server_exceptions=False,
        headers={"X-Chaos-Token": CHAOS_TOKEN},
    )
