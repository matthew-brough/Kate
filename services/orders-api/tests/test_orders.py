import pytest
from httpx import AsyncClient

ORDER_PAYLOAD = {
    "user_id": "user-abc",
    "product_id": "prod-xyz",
    "quantity": 2,
    "unit_price": 9.99,
}


async def test_create_order(client: AsyncClient) -> None:
    r = await client.post("/orders", json=ORDER_PAYLOAD)
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == "user-abc"
    assert body["status"] == "pending"
    assert body["id"] >= 1


async def test_list_orders_empty(client: AsyncClient) -> None:
    r = await client.get("/orders")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_orders(client: AsyncClient) -> None:
    await client.post("/orders", json=ORDER_PAYLOAD)
    r = await client.get("/orders")
    assert len(r.json()) == 1


async def test_get_order(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD)).json()
    r = await client.get(f"/orders/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_get_order_not_found(client: AsyncClient) -> None:
    r = await client.get("/orders/99999")
    assert r.status_code == 404


async def test_update_order_status(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD)).json()
    r = await client.patch(f"/orders/{created['id']}", json={"status": "completed"})
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_create_order_invalid_quantity(client: AsyncClient) -> None:
    r = await client.post("/orders", json={**ORDER_PAYLOAD, "quantity": 0})
    assert r.status_code == 422


@pytest.mark.parametrize("field", ["user_id", "product_id", "quantity", "unit_price"])
async def test_create_order_missing_field(client: AsyncClient, field: str) -> None:
    payload = {k: v for k, v in ORDER_PAYLOAD.items() if k != field}
    r = await client.post("/orders", json=payload)
    assert r.status_code == 422
