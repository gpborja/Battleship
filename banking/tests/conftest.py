import os

# Keep the module-level `app` in app.main from touching a real database file.
os.environ.setdefault("BANKING_DATABASE_URL", "sqlite://")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db(app):
    with app.state.session_factory() as session:
        yield session


@pytest.fixture
def make_account(client):
    def _make(owner_name="Test User", initial_deposit=0):
        resp = client.post("/api/accounts", json={"owner_name": owner_name, "initial_deposit": initial_deposit})
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
