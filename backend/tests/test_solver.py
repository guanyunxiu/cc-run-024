"""求解器可行性测试（硬约束必须 100% 满足）+ 属性测试。"""
from collections import Counter

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import Dish, Resident, Rule
from app.solver import SLOT_LINES, solve_menu

DAYS = 7


@pytest.fixture
def ctx():
    with Session(engine) as s:
        yield (s,
               s.exec(select(Dish).where(Dish.active == True)).all(),  # noqa: E712
               s.exec(select(Rule)).all())


def _solve(ctx, resident, **kw):
    s, dishes, rules = ctx
    targets = resident.targets["targets"]
    kw.setdefault("days", DAYS)
    kw.setdefault("budget_per_day", 40)
    kw.setdefault("time_limit_sec", 10)
    return solve_menu(resident, dishes, rules, targets, **kw)


def test_all_seed_residents_feasible(ctx):
    s, _, _ = ctx
    for r in s.exec(select(Resident)).all():
        for days in (1, 7):
            res = _solve(ctx, r, days=days)
            assert res["status"] == "success", f"{r.name} {days}天失败: {res.get('error')}"
            assert res["score"]["avg_attainment_pct"] >= 75


def test_no_hard_violations_in_solution(ctx):
    """方案里每道菜都必须对老人合规（过敏/慢病/吞咽/宗教）。"""
    s, dishes, rules = ctx
    r = s.exec(select(Resident).where(Resident.name == "张桂芳")).first()
    res = _solve(ctx, r)
    id_map = {d.id: d for d in dishes}
    for it in res["items"]:
        d = id_map[it["dish_id"]]
        assert d.iddsi_level <= r.swallowing_level
        assert not (set(d.allergens) & set(r.allergies))
        assert "egg" not in d.allergens  # 鸡蛋过敏
        # CKD：不能含高钾/高磷硬标签
        assert "high_potassium" not in d.tags
        assert not ({"high_phosphorus", "organ_meat"} & set(d.tags))


def test_slot_coverage(ctx):
    s, _, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == "王秀兰")).first()
    res = _solve(ctx, r)
    items = res["items"]
    # 每天每个槽线恰好一项
    cnt = Counter((i["day_index"], i["slot"], i["line"]) for i in items)
    expected = sum(len(lines) for lines in SLOT_LINES.values()) * DAYS
    assert len(cnt) == expected
    assert all(v == 1 for v in cnt.values())


def test_budget_hard_constraint(ctx):
    s, _, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == "李建国")).first()
    res = _solve(ctx, r, budget_per_day=25)
    for d, t in res["day_totals"].items():
        assert t["cost"] <= 25.01


def test_locks_respected(ctx):
    s, dishes, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == "赵德福")).first()
    target_dish = next(d for d in dishes if d.name == "清蒸鲈鱼")
    locks = {(0, "lunch", "entree"): target_dish.id}
    res = _solve(ctx, r, locks=locks)
    chosen = next(i for i in res["items"]
                  if i["day_index"] == 0 and i["slot"] == "lunch"
                  and i["line"] == "entree")
    assert chosen["dish_id"] == target_dish.id
    assert chosen["locked"] is True


def test_partial_resolve_keeps_other_days(ctx):
    s, dishes, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == "王秀兰")).first()
    full = _solve(ctx, r)
    # 把第 0-1、3-6 天全部锁定，仅重算第 2 天
    locks = {(i["day_index"], i["slot"], i["line"]): i["dish_id"]
             for i in full["items"] if i["day_index"] != 2}
    res = _solve(ctx, r, locks=locks, allowed_days={2})
    kept = {(i["day_index"], i["slot"], i["line"]): i["dish_id"]
            for i in res["items"] if i["day_index"] != 2}
    assert kept == {k: v for k, v in locks.items()}


def test_tight_budget_relaxes_with_warning(ctx):
    s, _, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == "陈广明")).first()
    # 极低预算：应触发松弛或返回明确失败，而不是异常
    res = _solve(ctx, r, budget_per_day=1)
    assert res["status"] in ("success", "failed")
    if res["status"] == "success":
        assert any("预算" in w or "放宽" in w for w in res["warnings"])


@pytest.mark.parametrize("resident_name", ["王秀兰", "李建国", "张桂芳",
                                           "赵德福", "刘慧敏", "陈广明"])
def test_attainment_reasonable(ctx, resident_name):
    s, _, _ = ctx
    r = s.exec(select(Resident).where(Resident.name == resident_name)).first()
    res = _solve(ctx, r)
    # 能量与蛋白质达标率不应过低
    att = res["score"]["attainment"]
    assert att["energy_kcal"] >= 70
    assert att["protein_g"] >= 70
