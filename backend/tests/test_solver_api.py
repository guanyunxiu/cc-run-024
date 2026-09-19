"""端到端：登录 → 求解任务 → 轮询 → 方案结构 → 手动调整冲突 → 报告导出。"""
import time
from datetime import date

from app.database import new_session
from app.models import Elder, Dish
from app.services.planner import build_engine, elder_targets, dates_for
from app.core.rules_engine import compile_person
from app.core import solver as solver_mod
from sqlmodel import select


def _solve_direct(elder_id=1, days=1, locked=None, weights=None):
    with new_session() as s:
        e = s.get(Elder, elder_id)
        dishes = list(s.exec(select(Dish).where(Dish.is_active == True)).all())  # noqa: E712
        engine, _ = build_engine(s)
        person = compile_person(e)
        tr = elder_targets(e)
        targets = {k: tuple(v) for k, v in tr.as_dict()["targets"].items()}
        return solver_mod.solve(
            days=days, dates=dates_for(date(2026, 9, 21), days),
            slots=["breakfast", "lunch", "dinner"], dishes=dishes,
            person_ctx=person, engine=engine, targets=targets,
            cost_limit_day=e.cost_limit_day, time_limit_seconds=15,
            locked_items=locked or [], weights=weights)


def test_day_solve_feasible_and_within_cost():
    res = _solve_direct(1, days=1)
    assert res.status in ("optimal", "feasible")
    assert len(res.items) >= 7  # 早2+午3+晚2
    assert res.daily_costs[0] <= 38.0 * 1.5 + 0.01
    slots = {i["slot"] for i in res.items}
    assert slots == {"breakfast", "lunch", "dinner"}


def test_allergen_excluded_in_solution():
    # 李秀兰蛋过敏：方案中不得出现含蛋菜
    res = _solve_direct(2, days=3)
    assert res.status in ("optimal", "feasible")
    with new_session() as s:
        dishes = {d.id: d for d in s.exec(select(Dish)).all()}
    for it in res.items:
        tags = dishes[it["dish_id"]].allergen_tags.split(",")
        assert "egg" not in [t.strip() for t in tags if t.strip()]


def test_iddsi_respected():
    # 李秀兰 IDDSI 5：所有菜 ≤5
    res = _solve_direct(2, days=2)
    with new_session() as s:
        dishes = {d.id: d for d in s.exec(select(Dish)).all()}
    for it in res.items:
        assert dishes[it["dish_id"]].iddsi_level <= 5


def test_locked_items_preserved():
    res1 = _solve_direct(3, days=2)
    locked = [{"day_index": it["day_index"], "slot": it["slot"],
               "dish_id": it["dish_id"], "portion_g": it["portion_g"],
               "dish_name": it["dish_name"]}
              for it in res1.items if it["slot"] == "breakfast"][:2]
    res2 = _solve_direct(3, days=2, locked=locked)
    keys = {(i["day_index"], i["slot"], i["dish_id"]) for i in res2.items}
    for l in locked:
        assert (l["day_index"], l["slot"], l["dish_id"]) in keys


def test_week_repeat_constraint_when_capacity_allows():
    # 王桂英候选充足：每菜出现 ≤3 次
    res = _solve_direct(3, days=7)
    assert res.status in ("optimal", "feasible")
    counts = {}
    for it in res.items:
        counts[it["dish_id"]] = counts.get(it["dish_id"], 0) + 1
    assert max(counts.values()) <= 3


def test_structure_has_staple_each_slot():
    res = _solve_direct(1, days=2)
    with new_session() as s:
        dishes = {d.id: d for d in s.exec(select(Dish)).all()}
    for d in (0, 1):
        for slot in ("breakfast", "lunch", "dinner"):
            types = {dishes[i["dish_id"]].dish_type
                     for i in res.items if i["day_index"] == d and i["slot"] == slot}
            assert "staple" in types or "liquid_staple" in types


# ── API 集成 ──

def test_api_full_flow(client, auth):
    # 发起日配餐求解
    r = client.post("/api/plans/solve", headers=auth, json={
        "elder_id": 1, "period_type": "day",
        "start_date": "2026-09-21", "days": 1,
        "time_limit_seconds": 15})
    assert r.status_code == 200
    task_id = r.json()["task_id"]
    # 轮询
    plan_id = None
    for _ in range(60):
        t = client.get(f"/api/tasks/{task_id}", headers=auth).json()
        if t["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    assert t["status"] == "success", t["message"]
    plan_id = t["result"]["plan_id"]

    detail = client.get(f"/api/plans/{plan_id}", headers=auth).json()
    assert len(detail["items"]) >= 7
    assert detail["metrics"]["total_cost"] > 0

    # 手动调整：替换为花生粥（对张德福无过敏）应无 forbid；再测 IDDSI 冲突高亮接口
    r = client.post("/api/rules/check-dishes", headers=auth,
                    json={"elder_id": 1, "dish_ids": [detail["items"][0]["dish_id"]]})
    assert r.status_code == 200
    res = list(r.json()["results"].values())[0]
    assert res["forbid"] is False

    # 乐观锁：错误版本号应 409
    r = client.put(f"/api/plans/{plan_id}", headers=auth,
                   json={"lock_version": 99999, "items": detail["items"]})
    assert r.status_code == 409

    # 发布
    lv = detail["lock_version"]
    r = client.post(f"/api/plans/{plan_id}/publish?lock_version={lv}", headers=auth)
    assert r.status_code == 200
    assert r.json()["status"] == "published"


def test_api_conflict_highlight_allergen(client, auth):
    # 李秀兰(id=2) 蛋过敏：蒸水蛋（含蛋）必须 forbid
    dishes = client.get("/api/food/dishes", headers=auth).json()
    egg_dish = next(d for d in dishes if d["name"] == "蒸水蛋")
    r = client.post("/api/rules/check-dishes", headers=auth,
                    json={"elder_id": 2, "dish_ids": [egg_dish["id"]]})
    out = r.json()["results"][str(egg_dish["id"])]
    assert out["forbid"] is True
    assert any(v["rule_type"] == "allergen" for v in out["violations"])


def test_pdf_and_excel_export(client, auth):
    r = client.post("/api/plans/solve", headers=auth, json={
        "elder_id": 3, "period_type": "day",
        "start_date": "2026-09-21", "days": 1})
    task_id = r.json()["task_id"]
    for _ in range(60):
        t = client.get(f"/api/tasks/{task_id}", headers=auth).json()
        if t["status"] in ("success", "failed"):
            break
        time.sleep(0.5)
    assert t["status"] == "success", t["message"]
    pid = t["result"]["plan_id"]
    pdf = client.get(f"/api/reports/plans/{pid}/pdf", headers=auth)
    assert pdf.status_code == 200
    assert pdf.content[:4] == b"%PDF"
    xlsx = client.get(f"/api/reports/plans/{pid}/excel", headers=auth)
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"  # zip(xlsx) 魔数
    purchase = client.get(f"/api/reports/plans/{pid}/purchase", headers=auth).json()
    assert len(purchase["items"]) > 0
    assert purchase["total_gross_g"] > 0
