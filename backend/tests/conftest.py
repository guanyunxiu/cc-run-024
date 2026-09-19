"""pytest 公共夹具：临时数据库 + TestClient。"""
import os
import tempfile

import pytest

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp.close()
os.environ["MEALPLAN_DB"] = _tmp.name

from fastapi.testclient import TestClient  # noqa: E402

from app.database import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed_all  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()
    seed_all()
    yield
    engine.dispose()
    try:
        os.unlink(_tmp.name)
    except OSError:
        pass


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def auth(client, username="dietitian", password="Nutri@2026") -> dict:
    r = client.post("/api/auth/login",
                    json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}
