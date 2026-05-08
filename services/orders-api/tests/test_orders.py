import pytest
from httpx import AsyncClient

USER_HEADER = {"X-User-Id": "user-abc"}
OTHER_HEADER = {"X-User-Id": "user-xyz"}

ORDER_PAYLOAD = {
    "product_id": "prod-xyz",
    "quantity": 2,
    "unit_price": 9.99,
}


async def test_create_order(client: AsyncClient) -> None:
    r = await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == "user-abc"
    assert body["status"] == "pending"
    assert body["unit_price"] == 9.99
    assert isinstance(body["unit_price"], float)
    assert body["id"] >= 1


async def test_create_order_missing_auth(client: AsyncClient) -> None:
    r = await client.post("/orders", json=ORDER_PAYLOAD)
    assert r.status_code == 401


async def test_list_orders_empty(client: AsyncClient) -> None:
    r = await client.get("/orders", headers=USER_HEADER)
    assert r.status_code == 200
    assert r.json() == []


async def test_list_orders(client: AsyncClient) -> None:
    await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)
    r = await client.get("/orders", headers=USER_HEADER)
    assert len(r.json()) == 1


async def test_list_orders_isolated_by_user(client: AsyncClient) -> None:
    await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)
    await client.post("/orders", json=ORDER_PAYLOAD, headers=OTHER_HEADER)
    r = await client.get("/orders", headers=USER_HEADER)
    assert len(r.json()) == 1
    assert r.json()[0]["user_id"] == "user-abc"


async def test_list_orders_missing_auth(client: AsyncClient) -> None:
    r = await client.get("/orders")
    assert r.status_code == 401


async def test_get_order(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)).json()
    r = await client.get(f"/orders/{created['id']}", headers=USER_HEADER)
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]


async def test_get_order_not_found(client: AsyncClient) -> None:
    r = await client.get("/orders/99999", headers=USER_HEADER)
    assert r.status_code == 404


async def test_get_order_wrong_user_returns_404(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)).json()
    r = await client.get(f"/orders/{created['id']}", headers=OTHER_HEADER)
    assert r.status_code == 404


async def test_update_order_status(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)).json()
    r = await client.patch(
        f"/orders/{created['id']}", json={"status": "completed"}, headers=USER_HEADER
    )
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


async def test_update_order_wrong_user_returns_404(client: AsyncClient) -> None:
    created = (await client.post("/orders", json=ORDER_PAYLOAD, headers=USER_HEADER)).json()
    r = await client.patch(
        f"/orders/{created['id']}", json={"status": "completed"}, headers=OTHER_HEADER
    )
    assert r.status_code == 404


async def test_create_order_invalid_quantity(client: AsyncClient) -> None:
    r = await client.post("/orders", json={**ORDER_PAYLOAD, "quantity": 0}, headers=USER_HEADER)
    assert r.status_code == 422


async def test_create_order_rejects_more_than_two_decimal_places(client: AsyncClient) -> None:
    r = await client.post(
        "/orders",
        json={**ORDER_PAYLOAD, "unit_price": 9.999},
        headers=USER_HEADER,
    )
    assert r.status_code == 422


@pytest.mark.parametrize("field", ["product_id", "quantity", "unit_price"])
async def test_create_order_missing_field(client: AsyncClient, field: str) -> None:
    payload = {k: v for k, v in ORDER_PAYLOAD.items() if k != field}
    r = await client.post("/orders", json=payload, headers=USER_HEADER)
    assert r.status_code == 422
