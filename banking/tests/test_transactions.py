from datetime import datetime, timedelta, timezone

import pytest

from app import services
from app.models import Transaction


def balance(client, account_id):
    return client.get(f"/api/accounts/{account_id}").json()["balance"]


# --- deposit / withdrawal -------------------------------------------------------------


def test_deposit_increases_balance(client, make_account):
    acct = make_account()
    resp = client.post(f"/api/accounts/{acct['id']}/deposit", json={"amount": 100.25})
    assert resp.status_code == 200
    body = resp.json()
    assert body["account"]["balance"] == 100.25
    assert body["transaction"]["type"] == "deposit"
    assert body["transaction"]["direction"] == "in"
    assert balance(client, acct["id"]) == 100.25


def test_withdraw_decreases_balance(client, make_account):
    acct = make_account(initial_deposit=100)
    resp = client.post(f"/api/accounts/{acct['id']}/withdraw", json={"amount": 30.10})
    assert resp.status_code == 200
    assert resp.json()["account"]["balance"] == 69.90
    assert resp.json()["transaction"]["type"] == "withdrawal"


def test_withdraw_entire_balance_is_allowed(client, make_account):
    acct = make_account(initial_deposit=42)
    assert client.post(f"/api/accounts/{acct['id']}/withdraw", json={"amount": 42}).status_code == 200
    assert balance(client, acct["id"]) == 0


def test_cents_do_not_drift(client, make_account):
    acct = make_account()
    for _ in range(10):
        client.post(f"/api/accounts/{acct['id']}/deposit", json={"amount": 0.10})
    assert balance(client, acct["id"]) == 1.00


@pytest.mark.parametrize("amount", [0, -5, -0.01, 1.001, "abc"])
@pytest.mark.parametrize("op", ["deposit", "withdraw"])
def test_rejects_non_positive_or_invalid_amounts(client, make_account, op, amount):
    acct = make_account(initial_deposit=100)
    resp = client.post(f"/api/accounts/{acct['id']}/{op}", json={"amount": amount})
    assert resp.status_code == 422
    assert balance(client, acct["id"]) == 100


def test_service_layer_rejects_non_positive_amounts(db, make_account):
    acct = make_account(initial_deposit=100)
    for fn in (services.deposit, services.withdraw):
        with pytest.raises(services.InvalidAmount):
            fn(db, acct["id"], -500)
        with pytest.raises(services.InvalidAmount):
            fn(db, acct["id"], 0)


def test_deposit_to_missing_account_returns_404(client):
    assert client.post("/api/accounts/999/deposit", json={"amount": 1}).status_code == 404
    assert client.post("/api/accounts/999/withdraw", json={"amount": 1}).status_code == 404


# --- overdraft ------------------------------------------------------------------------


def test_overdraft_is_rejected(client, make_account):
    acct = make_account(initial_deposit=50)
    resp = client.post(f"/api/accounts/{acct['id']}/withdraw", json={"amount": 50.01})
    assert resp.status_code == 409
    assert "Insufficient funds" in resp.json()["detail"]
    assert balance(client, acct["id"]) == 50
    history = client.get(f"/api/accounts/{acct['id']}/transactions").json()
    assert [t["type"] for t in history] == ["deposit"]


def test_withdraw_from_empty_account_is_rejected(client, make_account):
    acct = make_account()
    assert client.post(f"/api/accounts/{acct['id']}/withdraw", json={"amount": 1}).status_code == 409
    assert balance(client, acct["id"]) == 0


# --- transfers ------------------------------------------------------------------------


def test_transfer_moves_money(client, make_account):
    a = make_account("A", 100)
    b = make_account("B", 10)
    resp = client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": 40})
    assert resp.status_code == 200
    body = resp.json()
    assert body["from_account"]["balance"] == 60
    assert body["to_account"]["balance"] == 50
    assert body["transaction"]["type"] == "transfer"
    assert body["transaction"]["related_account_id"] == b["id"]

    out = client.get(f"/api/accounts/{a['id']}/transactions").json()[0]
    inc = client.get(f"/api/accounts/{b['id']}/transactions").json()[0]
    assert out["id"] == inc["id"]
    assert (out["direction"], inc["direction"]) == ("out", "in")


def test_transfer_overdraft_changes_neither_account(client, make_account):
    a = make_account("A", 100)
    b = make_account("B", 10)
    resp = client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": 100.01})
    assert resp.status_code == 409
    assert balance(client, a["id"]) == 100
    assert balance(client, b["id"]) == 10
    assert len(client.get(f"/api/accounts/{b['id']}/transactions").json()) == 1


def test_transfer_to_missing_account_does_not_debit_source(client, make_account):
    a = make_account("A", 100)
    resp = client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": 999, "amount": 10})
    assert resp.status_code == 404
    assert balance(client, a["id"]) == 100


def test_transfer_from_missing_account(client, make_account):
    b = make_account("B", 10)
    resp = client.post("/api/transfers", json={"from_account_id": 999, "to_account_id": b["id"], "amount": 10})
    assert resp.status_code == 404
    assert balance(client, b["id"]) == 10


def test_transfer_to_same_account_is_rejected(client, make_account):
    a = make_account("A", 100)
    resp = client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": a["id"], "amount": 10})
    assert resp.status_code == 400
    assert balance(client, a["id"]) == 100


@pytest.mark.parametrize("amount", [0, -10])
def test_transfer_rejects_non_positive_amounts(client, make_account, amount):
    a = make_account("A", 100)
    b = make_account("B", 0)
    resp = client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": amount})
    assert resp.status_code == 422
    assert (balance(client, a["id"]), balance(client, b["id"])) == (100, 0)


def test_transfer_is_atomic_when_credit_side_fails(app, client, make_account, monkeypatch):
    """Simulate a crash after the source was debited: the debit must be rolled back."""
    a = make_account("A", 100)
    b = make_account("B", 10)

    def exploding_credit(*_args, **_kwargs):
        raise RuntimeError("simulated failure while crediting destination")

    monkeypatch.setattr(services, "_credit", exploding_credit)

    with app.state.session_factory() as db:
        with pytest.raises(RuntimeError):
            services.transfer(db, a["id"], b["id"], 50_00)

    assert balance(client, a["id"]) == 100
    assert balance(client, b["id"]) == 10
    with app.state.session_factory() as db:
        assert db.query(Transaction).filter_by(type="transfer").count() == 0


def test_transfer_is_atomic_when_recording_fails(app, client, make_account, monkeypatch):
    """Both balances were updated but the ledger entry fails: everything is rolled back."""
    a = make_account("A", 100)
    b = make_account("B", 10)

    def exploding_record(*_args, **_kwargs):
        raise RuntimeError("simulated failure while writing ledger entry")

    monkeypatch.setattr(services, "_record", exploding_record)

    with app.state.session_factory() as db:
        with pytest.raises(RuntimeError):
            services.transfer(db, a["id"], b["id"], 50_00)

    assert balance(client, a["id"]) == 100
    assert balance(client, b["id"]) == 10


def test_api_returns_500_and_keeps_balances_on_internal_transfer_failure(app, make_account, monkeypatch):
    from fastapi.testclient import TestClient

    a = make_account("A", 100)
    b = make_account("B", 10)
    monkeypatch.setattr(services, "_credit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with TestClient(app, raise_server_exceptions=False) as c:
        resp = c.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": 50})
        assert resp.status_code == 500
        assert balance(c, a["id"]) == 100
        assert balance(c, b["id"]) == 10


# --- history --------------------------------------------------------------------------


def test_history_is_newest_first(client, make_account):
    a = make_account("A", 100)
    b = make_account("B")
    client.post(f"/api/accounts/{a['id']}/withdraw", json={"amount": 10})
    client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": 20})
    client.post(f"/api/accounts/{a['id']}/deposit", json={"amount": 5})

    history = client.get(f"/api/accounts/{a['id']}/transactions").json()
    assert [t["type"] for t in history] == ["deposit", "transfer", "withdrawal", "deposit"]
    assert [t["amount"] for t in history] == [5, 20, 10, 100]
    timestamps = [datetime.fromisoformat(t["timestamp"]) for t in history]
    assert timestamps == sorted(timestamps, reverse=True)
    ids = [t["id"] for t in history]
    assert ids == sorted(ids, reverse=True)


def test_history_orders_by_timestamp_not_insertion(db, client, make_account):
    acct = make_account("A")
    now = datetime.now(timezone.utc)
    services.deposit(db, acct["id"], 1_00, at=now - timedelta(days=1))
    services.deposit(db, acct["id"], 3_00, at=now - timedelta(days=3))
    services.deposit(db, acct["id"], 2_00, at=now - timedelta(days=2))

    history = client.get(f"/api/accounts/{acct['id']}/transactions").json()
    assert [t["amount"] for t in history] == [1, 2, 3]


def test_history_same_timestamp_breaks_ties_by_id(db, client, make_account):
    acct = make_account("A")
    at = datetime.now(timezone.utc)
    first = services.deposit(db, acct["id"], 1_00, at=at)
    second = services.deposit(db, acct["id"], 2_00, at=at)
    history = client.get(f"/api/accounts/{acct['id']}/transactions").json()
    assert [t["id"] for t in history] == [second.id, first.id]


def test_history_includes_incoming_transfers_only_for_involved_accounts(client, make_account):
    a = make_account("A", 100)
    b = make_account("B")
    c = make_account("C", 1)
    client.post("/api/transfers", json={"from_account_id": a["id"], "to_account_id": b["id"], "amount": 25})

    b_hist = client.get(f"/api/accounts/{b['id']}/transactions").json()
    assert len(b_hist) == 1 and b_hist[0]["direction"] == "in" and b_hist[0]["account_id"] == a["id"]
    c_hist = client.get(f"/api/accounts/{c['id']}/transactions").json()
    assert [t["type"] for t in c_hist] == ["deposit"]


def test_history_limit(client, make_account):
    acct = make_account("A")
    for i in range(1, 6):
        client.post(f"/api/accounts/{acct['id']}/deposit", json={"amount": i})
    history = client.get(f"/api/accounts/{acct['id']}/transactions", params={"limit": 2}).json()
    assert [t["amount"] for t in history] == [5, 4]


def test_history_for_missing_account_returns_404(client):
    assert client.get("/api/accounts/999/transactions").status_code == 404
