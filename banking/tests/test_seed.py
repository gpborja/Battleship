from fastapi.testclient import TestClient

from app.main import create_app
from app.seed import DEMO_ACCOUNTS, DEMO_ACTIVITY, seed


def test_seed_creates_demo_data_and_is_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'seed.db'}"
    assert seed(url) is True
    assert seed(url) is False
    assert seed(url, reset=True) is True

    with TestClient(create_app(url)) as client:
        accounts = client.get("/api/accounts").json()
        assert len(accounts) == len(DEMO_ACCOUNTS)
        assert all(a["balance"] >= 0 for a in accounts)

        txn_ids = set()
        for a in accounts:
            txn_ids |= {t["id"] for t in client.get(f"/api/accounts/{a['id']}/transactions").json()}
        assert len(txn_ids) == len(DEMO_ACCOUNTS) + len(DEMO_ACTIVITY)
