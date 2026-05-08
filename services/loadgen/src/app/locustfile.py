"""Kate platform load generator.

Simulates the browse → buy → report flow continuously.
Locust env vars control behaviour: LOCUST_HOST, LOCUST_USERS, LOCUST_SPAWN_RATE.
"""

import random
import string
import uuid

from faker import Faker
from locust import HttpUser, between, task
from requests import Response

fake = Faker()

PRODUCTS = [str(uuid.uuid4()) for _ in range(20)]
REQUEST_TIMEOUT = 5
AUTH_ATTEMPTS = 3
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

    def on_start(self) -> None:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        self._username = f"load_{suffix}"
        self._password = "L0adG3n!pw"
        self._token = ""
        self._ensure_token()

    def _register(self) -> Response:
        return self.client.post(
            "/api/auth/register",
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
            data={"username": self._username, "password": self._password},
            name="/api/auth/token",
            timeout=REQUEST_TIMEOUT,
        )

    def _ensure_token(self) -> bool:
        if self._token:
            return True

        for _ in range(AUTH_ATTEMPTS):
            self._register()
            r = self._login()
            if r.status_code == 200:
                self._token = r.json().get("access_token", "")
                return bool(self._token)
        return False

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

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
