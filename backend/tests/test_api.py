"""API 集成测试：认证、权限、乐观锁、任务轮询、导出。"""
import time

from tests.conftest import auth


def wait_task(client, h, task_id, timeout=90):
    for _ in range(timeout):
        t = client.get(f"/api/tasks/{task_id}", headers=h).json()
        if t["status"] in ("success", "failed"):
            return t
        time.sleep(1)
    return t


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_login_wrong_password(client):
    r = client.post("/api/auth/login",
                    json={"username": "dietitian", "password": "wrong"})
    assert r.status_code == 401


def test_me_and_options(client):
    h = auth(client)
    me = client.get("/api/auth/me", headers=h).json()
    assert me["username"] == "dietitian"
    opts = client.get("/api/residents/options", headers=h).json()
    assert "chronic" in opts and len(opts["iddsi"]) == 8


def test_viewer_cannot_write(client):
    h = auth(client, "viewer", "View@2026")
    r = client.post("/api/residents", headers=h,
                    json={"name": "X", "age": 80, "height_cm": 160,
                          "weight_kg": 60, "swallowing_level": 7})
    assert r.status_code == 403


def test_resident_crud_and_targets(client):
    h = auth(client)
    r = client.post("/api/residents", headers=h, json={
        "name": "接口测试老人", "gender": "male", "age": 83, "height_cm": 170,
        "weight_kg": 65, "activity_level": "light", "swallowing_level": 6,
        "chronic_conditions": ["hypertension", "diabetes"], "allergies": [],
        "religion": "none", "medications": [], "nutrition_goal_type": "maintain"})
    assert r.status_code == 201
    rid = r.json()["id"]
    detail = client.get(f"/api/residents/{rid}", headers=h).json()
    assert detail["targets"]["tdee"] > 1000
    assert any(x["code"] == "HTN-001" for x in detail["applicable_rules"])
    assert any(x["code"] == "DM-001" for x in detail["applicable_rules"])


def test_full_plan_lifecycle(client):
    h = auth(client)
    r = client.post("/api/plans", headers=h,
                    json={"resident_id": 1, "days": 1, "budget_per_day": 40})
    pid, tid = r.json()["plan_id"], r.json()["task_id"]
    t = wait_task(client, h, tid)
    assert t["status"] == "success", t.get("error")
    plan = client.get(f"/api/plans/{pid}", headers=h).json()
    assert len(plan["items"]) == 13  # 1天共13个槽线

    # 乐观锁：旧版本号应被拒绝
    bad = client.post(f"/api/plans/{pid}/lock", headers=h,
                      json={"item_id": plan["items"][0]["id"],
                            "locked": True, "version": 999})
    assert bad.status_code == 409

    # 正常锁定
    ok = client.post(f"/api/plans/{pid}/lock", headers=h,
                     json={"item_id": plan["items"][0]["id"],
                           "locked": True, "version": plan["version"]})
    assert ok.json()["ok"]

    # 发布
    plan = client.get(f"/api/plans/{pid}", headers=h).json()
    pub = client.post(f"/api/plans/{pid}/publish", headers=h,
                      json={"version": plan["version"], "note": "测试发布"})
    assert pub.status_code == 200 and pub.json()["version_no"] == 1
    vers = client.get(f"/api/plans/{pid}/versions", headers=h).json()
    assert len(vers) == 1


def test_conflict_check_blocks_pickle_for_hypertension(client):
    h = auth(client)
    r = client.post("/api/plans", headers=h,
                    json={"resident_id": 1, "days": 1, "budget_per_day": 40})
    pid = r.json()["plan_id"]
    wait_task(client, h, r.json()["task_id"])
    dishes = client.get("/api/dishes", headers=h).json()
    pickle_d = next(d for d in dishes if d["name"] == "酱黄瓜")
    chk = client.post(f"/api/plans/{pid}/check", headers=h, json={
        "resident_id": 1,
        "items": [{"day_index": 0, "slot": "lunch", "line": "entree",
                   "dish_id": pickle_d["id"]}]}).json()
    assert any("腌制" in x["message"] for x in chk["hard"])
    assert chk["feasible"] is False


def test_reports_export(client):
    h = auth(client)
    r = client.post("/api/plans", headers=h,
                    json={"resident_id": 2, "days": 1, "budget_per_day": 40})
    pid, tid = r.json()["plan_id"], r.json()["task_id"]
    wait_task(client, h, tid)
    plan = client.get(f"/api/plans/{pid}", headers=h).json()
    client.post(f"/api/plans/{pid}/publish", headers=h,
                json={"version": plan["version"], "note": "x"})
    pdf = client.get(f"/api/reports/plan/{pid}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:5] == b"%PDF-"
    xlsx = client.get(f"/api/reports/plan/{pid}/excel", headers=h)
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    proc = client.get(f"/api/reports/plan/{pid}/procurement", headers=h).json()
    assert proc["total_cost"] > 0


def test_audit_logs_recorded(client):
    h = auth(client)
    client.get("/api/dishes", headers=h)  # 产生一些操作
    logs = client.get("/api/audit-logs?size=50", headers=h).json()
    assert logs["total"] > 0
    assert any(x["action"] == "login" for x in logs["items"])
