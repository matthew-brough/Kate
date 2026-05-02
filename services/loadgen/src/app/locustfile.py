"""Kate platform load generator.

Simulates the browse → buy → report flow continuously.
Locust env vars control behaviour: LOCUST_HOST, LOCUST_USERS, LOCUST_SPAWN_RATE.
"""

import random
import string
import uuid

from faker import Faker
from locust import HttpUser, between, task

fake = Faker()

PRODUCTS = [str(uuid.uuid4()) for _ in range(20)]


class PlatformUser(HttpUser):
    """Virtual user: register → shop → report, cycling indefinitely."""

    wait_time = between(1, 3)

    _token: str

    def on_start(self) -> None:
        suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
        username = f"load_{suffix}"
        password = "L0adG3n!pw"

        self.client.post(
            "/api/auth/register",
            json={
                "username": username,
                "email": f"{username}@loadgen.internal",
                "password": password,
            },
            name="/api/auth/register",
        )
        r = self.client.post(
            "/api/auth/token",
            data={"username": username, "password": password},
            name="/api/auth/token",
        )
        self._token = r.json().get("access_token", "") if r.status_code == 200 else ""

    def _auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @task(3)
    def browse_orders(self) -> None:
        self.client.get("/api/orders", headers=self._auth(), name="/api/orders [GET]")

    @task(2)
    def place_order(self) -> None:
        self.client.post(
            "/api/orders",
            headers=self._auth(),
            json={
                "product_id": random.choice(PRODUCTS),
                "quantity": random.randint(1, 5),
                "unit_price": round(random.uniform(9.99, 199.99), 2),
            },
            name="/api/orders [POST]",
        )

    @task(1)
    def request_and_poll_report(self) -> None:
        r = self.client.post(
            "/api/reports",
            headers=self._auth(),
            name="/api/reports [POST]",
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
                name="/api/reports/[id] [GET]",
            )
            if poll.json().get("status") in ("completed", "failed"):
                break
