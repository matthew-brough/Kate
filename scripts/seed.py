# /// script
# requires-python = ">=3.14"
# dependencies = ["httpx>=0.27", "faker>=30.0"]
# ///
"""Seed script — creates fake users, orders, and report requests.

Usage (gateway must be running on localhost:8080):
    uv run scripts/seed.py
    uv run scripts/seed.py --gateway http://localhost:8080 --users 20 --orders 500 --reports 50
"""

import argparse
import random
import sys
from dataclasses import dataclass

import httpx
from faker import Faker

fake = Faker()


@dataclass
class SeedConfig:
    gateway: str
    num_users: int
    num_orders: int
    num_reports: int


def parse_args() -> SeedConfig:
    p = argparse.ArgumentParser(description="Seed Kate platform with fake data")
    p.add_argument("--gateway", default="http://localhost:8080")
    p.add_argument("--users", type=int, default=10, dest="num_users")
    p.add_argument("--orders", type=int, default=200, dest="num_orders")
    p.add_argument("--reports", type=int, default=30, dest="num_reports")
    a = p.parse_args()
    return SeedConfig(
        gateway=a.gateway,
        num_users=a.num_users,
        num_orders=a.num_orders,
        num_reports=a.num_reports,
    )


def register_users(
    client: httpx.Client, cfg: SeedConfig
) -> list[dict[str, str]]:
    users: list[dict[str, str]] = []
    print(f"Creating {cfg.num_users} users...")
    for _ in range(cfg.num_users):
        username = fake.user_name() + str(random.randint(100, 9999))
        password = fake.password(length=12)
        r = client.post(
            f"{cfg.gateway}/api/auth/register",
            json={"username": username, "email": fake.email(), "password": password},
        )
        if r.status_code == 201:
            users.append({"username": username, "password": password})
        elif r.status_code == 409:
            pass  # duplicate username, skip
        else:
            print(f"  WARN register failed: {r.status_code} {r.text[:120]}")
    print(f"  Created {len(users)} users")
    return users


def get_tokens(
    client: httpx.Client, cfg: SeedConfig, users: list[dict[str, str]]
) -> list[str]:
    tokens: list[str] = []
    print("Acquiring tokens...")
    for user in users:
        r = client.post(
            f"{cfg.gateway}/api/auth/token",
            data={"username": user["username"], "password": user["password"]},
        )
        if r.status_code == 200:
            tokens.append(r.json()["access_token"])
        else:
            print(f"  WARN token failed for {user['username']}: {r.status_code}")
    print(f"  Got {len(tokens)} tokens")
    return tokens


PRODUCTS = [str(fake.uuid4()) for _ in range(20)]


def seed_orders(client: httpx.Client, cfg: SeedConfig, tokens: list[str]) -> None:
    if not tokens:
        print("No tokens — skipping orders")
        return
    print(f"Creating {cfg.num_orders} orders...")
    ok = 0
    for _ in range(cfg.num_orders):
        token = random.choice(tokens)
        r = client.post(
            f"{cfg.gateway}/api/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "user_id": str(fake.uuid4()),
                "product_id": random.choice(PRODUCTS),
                "quantity": random.randint(1, 10),
                "unit_price": round(random.uniform(5.0, 999.99), 2),
            },
        )
        if r.status_code == 201:
            ok += 1
        else:
            print(f"  WARN order failed: {r.status_code} {r.text[:80]}")
    print(f"  Created {ok}/{cfg.num_orders} orders")


def seed_reports(client: httpx.Client, cfg: SeedConfig, tokens: list[str]) -> None:
    if not tokens:
        print("No tokens — skipping reports")
        return
    print(f"Creating {cfg.num_reports} report requests...")
    ok = 0
    for _ in range(cfg.num_reports):
        token = random.choice(tokens)
        r = client.post(
            f"{cfg.gateway}/api/reports",
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 202:
            ok += 1
        else:
            print(f"  WARN report failed: {r.status_code} {r.text[:80]}")
    print(f"  Enqueued {ok}/{cfg.num_reports} report jobs (worker processes async)")


def main() -> None:
    cfg = parse_args()
    print(f"Seeding Kate platform at {cfg.gateway}")

    with httpx.Client(timeout=30.0) as client:
        # Verify gateway is reachable.
        try:
            client.get(f"{cfg.gateway}/health").raise_for_status()
        except Exception as exc:
            print(f"ERROR: gateway unreachable at {cfg.gateway}: {exc}")
            sys.exit(1)

        users = register_users(client, cfg)
        tokens = get_tokens(client, cfg, users)
        seed_orders(client, cfg, tokens)
        seed_reports(client, cfg, tokens)

    print("Done.")


if __name__ == "__main__":
    main()
