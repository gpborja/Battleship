from datetime import datetime


def test_create_account_defaults_to_zero_balance(client):
    resp = client.post("/api/accounts", json={"owner_name": "Ada Lovelace"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["owner_name"] == "Ada Lovelace"
    assert body["balance"] == 0
    assert isinstance(body["id"], int)
    assert datetime.fromisoformat(body["created_at"]).tzinfo is not None


def test_create_account_with_initial_deposit_records_transaction(client, make_account):
    account = make_account("Grace Hopper", 250.50)
    assert account["balance"] == 250.50

    history = client.get(f"/api/accounts/{account['id']}/transactions").json()
    assert len(history) == 1
    assert history[0]["type"] == "deposit"
    assert history[0]["amount"] == 250.50


def test_get_account(client, make_account):
    account = make_account("Alan Turing", 10)
    resp = client.get(f"/api/accounts/{account['id']}")
    assert resp.status_code == 200
    assert resp.json() == account


def test_get_missing_account_returns_404(client):
    resp = client.get("/api/accounts/999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"]


def test_list_accounts(client, make_account):
    a = make_account("A")
    b = make_account("B", 5)
    resp = client.get("/api/accounts")
    assert resp.status_code == 200
    assert [x["id"] for x in resp.json()] == [a["id"], b["id"]]


def test_create_account_rejects_invalid_input(client):
    assert client.post("/api/accounts", json={"owner_name": ""}).status_code == 422
    assert client.post("/api/accounts", json={"owner_name": "   "}).status_code == 400
    assert client.post("/api/accounts", json={"owner_name": "X", "initial_deposit": -1}).status_code == 422
    assert client.post("/api/accounts", json={"owner_name": "X", "initial_deposit": 1.234}).status_code == 422


def test_dashboard_is_served(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
