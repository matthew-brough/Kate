from httpx import AsyncClient

USER_HEADER = {"X-User-Id": "user-abc-123"}


async def test_create_report_returns_202(client: AsyncClient) -> None:
    r = await client.post("/reports", headers=USER_HEADER)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["user_id"] == "user-abc-123"
    assert "id" in body


async def test_get_report_returns_200(client: AsyncClient) -> None:
    create_r = await client.post("/reports", headers=USER_HEADER)
    report_id = create_r.json()["id"]

    r = await client.get(f"/reports/{report_id}", headers=USER_HEADER)
    assert r.status_code == 200
    assert r.json()["id"] == report_id


async def test_get_report_not_found_returns_404(client: AsyncClient) -> None:
    r = await client.get(
        "/reports/00000000-0000-0000-0000-000000000000", headers=USER_HEADER
    )
    assert r.status_code == 404


async def test_get_report_wrong_user_returns_404(client: AsyncClient) -> None:
    create_r = await client.post("/reports", headers=USER_HEADER)
    report_id = create_r.json()["id"]

    r = await client.get(
        f"/reports/{report_id}", headers={"X-User-Id": "other-user"}
    )
    assert r.status_code == 404


async def test_list_reports_empty(client: AsyncClient) -> None:
    r = await client.get("/reports", headers={"X-User-Id": "nobody"})
    assert r.status_code == 200
    assert r.json() == []


async def test_list_reports_returns_own_reports(client: AsyncClient) -> None:
    await client.post("/reports", headers=USER_HEADER)
    await client.post("/reports", headers=USER_HEADER)
    await client.post("/reports", headers={"X-User-Id": "other-user"})

    r = await client.get("/reports", headers=USER_HEADER)
    assert r.status_code == 200
    reports = r.json()
    assert len(reports) == 2
    assert all(rep["user_id"] == "user-abc-123" for rep in reports)
