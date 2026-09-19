"""pytest 全局夹具：内存数据库 + 测试客户端。"""
import os
import pytest
from fastapi.testclient import TestClient

os.environ["NUTRITION_DB"] = ":memory:"


@pytest.fixture(name="client")
def _client():
    yield from _init_db_and_client()


def _init_db_and_client():
    # 每个测试使用独立内存库
    from app import database
    from app.models import User  # noqa: F401
    database.init_db()
    from app.seed import (seed_users, seed_foods, seed_rules, seed_elders)
    with database.new_session() as s:
        seed_users(s)
        seed_foods(s)
        seed_rules(s)
        seed_elders(s)
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _ensure_db():
    """非 API 测试（直接调用服务层）也需要内存库与种子数据。"""
    from app import database
    database.init_db()
    from app.models import User, Ingredient, Dish  # noqa: F401
    from sqlmodel import select
    with database.new_session() as s:
        seeded = s.exec(select(User)).first()
        if not seeded:
            from app.seed import (seed_users, seed_foods, seed_rules, seed_elders)
            seed_users(s)
            seed_foods(s)
            seed_rules(s)
            seed_elders(s)
    yield


@pytest.fixture(name="token")
def _token(client):
    r = client.post("/api/auth/login-json",
                    json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(name="auth")
def _auth(token):
    return {"Authorization": f"Bearer {token}"}
