"""Kate platform load generator.

Simulates the browse → buy → report flow continuously.
Locust env vars control behaviour: LOCUST_HOST, LOCUST_USERS, LOCUST_SPAWN_RATE.
"""

import os
import random
import re
import string
import time
import uuid

from faker import Faker
from locust import HttpUser, between, task
from requests import Response

fake = Faker()

PRODUCTS = [str(uuid.uuid4()) for _ in range(20)]
REQUEST_TIMEOUT = 5
AUTH_RETRY_BACKOFF_SECONDS = 60
MAX_REGISTER_ATTEMPTS = 2
ORDER_LIST_LABEL = "purchase list [GET]"
ORDER_CREATE_LABEL = "purchase create [POST]"
REPORT_CREATE_LABEL = "analytics create [POST]"
REPORT_POLL_LABEL = "analytics poll [GET]"


class PlatformUser(HttpUser):
    """Virtual user: register → shop → report, cycling indefinitely."""

    wait_time = between(1, 3)

    _token: str
    _username: str
    _password: str
    _client_ip: str
    _registered: bool
    _register_attempts: int
    _next_auth_attempt_at: float

    def on_start(self) -> None:
        host = re.sub(r"[^a-z0-9]+", "", os.getenv("HOSTNAME", "local").lower())[:12]
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self._username = f"load_{host}_{suffix}"
        self._password = os.environ["LOADGEN_PASSWORD"]
        self._token = ""
        self._client_ip = fake.ipv4_private()
        self._registered = False
        self._register_attempts = 0
        self._next_auth_attempt_at = 0
        self._ensure_token()

    def _headers(self) -> dict[str, str]:
        # The gateway is configured to trust X-Forwarded-For in dev, matching ingress traffic.
        return {"X-Forwarded-For": self._client_ip}

    def _register(self) -> Response:
        return self.client.post(
            "/api/auth/register",
            headers=self._headers(),
            json={
                "username": self._username,
                "email": f"{self._username}@loadgen.internal",
                "password": self._password,
            },
            name="/api/auth/register",
            timeout=REQUEST_TIMEOUT,
        )

    def _login(self) -> Response:
        return self.client.post(
            "/api/auth/token",
            headers=self._headers(),
            data={"username": self._username, "password": self._password},
            name="/api/auth/token",
            timeout=REQUEST_TIMEOUT,
        )

    def _ensure_token(self) -> bool:
        if self._token:
            return True
        if time.monotonic() < self._next_auth_attempt_at:
            return False

        if not self._registered and self._register_attempts < MAX_REGISTER_ATTEMPTS:
            self._register_attempts += 1
            register = self._register()
            if register.status_code in (201, 409):
                self._registered = True

        r = self._login()
        if r.status_code == 200:
            self._token = r.json().get("access_token", "")
            return bool(self._token)
        if r.status_code == 401 and self._register_attempts < MAX_REGISTER_ATTEMPTS:
            self._registered = False
        self._next_auth_attempt_at = time.monotonic() + AUTH_RETRY_BACKOFF_SECONDS
        return False

    def _auth(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            **self._headers(),
        }

    @task(3)
    def browse_orders(self) -> None:
        if not self._ensure_token():
            return
        self.client.get(
            "/api/orders",
            headers=self._auth(),
            name=ORDER_LIST_LABEL,
            timeout=REQUEST_TIMEOUT,
        )

    @task(2)
    def place_order(self) -> None:
        if not self._ensure_token():
            return
        self.client.post(
            "/api/orders",
            headers=self._auth(),
            json={
                "product_id": random.choice(PRODUCTS),
                "quantity": random.randint(1, 5),
                "unit_price": round(random.uniform(9.99, 199.99), 2),
            },
            name=ORDER_CREATE_LABEL,
            timeout=REQUEST_TIMEOUT,
        )

    @task(1)
    def request_and_poll_report(self) -> None:
        if not self._ensure_token():
            return
        r = self.client.post(
            "/api/reports",
            headers=self._auth(),
            name=REPORT_CREATE_LABEL,
            timeout=REQUEST_TIMEOUT,
        )
        if r.status_code != 202:
            return
        report_id = r.json().get("id")
        if not report_id:
            return
        for _ in range(4):
            poll = self.client.get(
                f"/api/reports/{report_id}",
                headers=self._auth(),
                name=REPORT_POLL_LABEL,
                timeout=REQUEST_TIMEOUT,
            )
            if poll.json().get("status") in ("completed", "failed"):
                break
