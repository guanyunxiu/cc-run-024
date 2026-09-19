"""配餐服务：求解任务执行、版本快照、乐观锁、局部重求解、冲突检查。"""
import json
from datetime import datetime, date, timedelta

from sqlmodel import Session, select

from ..models import (MealPlan, MealItem, PlanVersionArchive, Task, Dish, Elder,
                      RuleVersion, Rule)
from ..core import solver as solver_mod
from ..core.rules_engine import RuleEngine, compile_person, compile_dish
from ..core.nutrition import compute_targets
from ..config import SLOTS
from .foodlib import ingredient_names_for_dishes, refresh_dish_nutrition


# ───────────────── 辅助 ─────────────────

def parse_overrides(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def elder_targets(elder: Elder):
    diseases = [x.strip() for x in elder.chronic_diseases.split(",") if x.strip()]
    overrides = parse_overrides(elder.target_overrides)
    return compute_targets(
        birth_date=elder.birth_date, gender=elder.gender,
        height_cm=elder.height_cm, weight_kg=elder.weight_kg,
        activity_level=elder.activity_level,
        chronic_diseases=diseases,
        nutrition_goal=elder.nutrition_goal,
        target_overrides=overrides,
    )


def active_rules(session: Session) -> tuple[list[dict], str]:
    """取当前已发布规则版本（无则取最新草稿）。"""
    rv = session.exec(select(RuleVersion).where(RuleVersion.status == "published")
                      .order_by(RuleVersion.id.desc())).first()
    if not rv:
        rv = session.exec(select(RuleVersion).order_by(RuleVersion.id.desc())).first()
    if not rv:
        return [], ""
    rules = []
    for r in session.exec(select(Rule).where(Rule.version_id == rv.id)).all():
        rd = r.model_dump()
        rd["condition"] = json.loads(r.condition_json or "{}")
        rules.append(rd)
    return rules, rv.version


def build_engine(session: Session) -> tuple[RuleEngine, str]:
    rules, version = active_rules(session)
    return RuleEngine(rules), version


def dates_for(start: date, days: int) -> list[str]:
    return [(start + timedelta(days=i)).isoformat() for i in range(days)]


# ───────────────── 快照 / 归档 ─────────────────

def plan_snapshot(session: Session, plan: MealPlan) -> dict:
    items = session.exec(select(MealItem).where(MealItem.plan_id == plan.id)).all()
    return {
        "plan": plan.model_dump(mode="json"),
        "items": [i.model_dump(mode="json") for i in items],
    }


def archive_version(session: Session, plan: MealPlan, username: str,
                    note_status: str | None = None) -> int:
    nxt = session.exec(
        select(PlanVersionArchive).where(PlanVersionArchive.plan_id == plan.id)
    ).all()
    version_no = (max((v.version_no for v in nxt), default=0) + 1)
    snap = plan_snapshot(session, plan)
    arch = PlanVersionArchive(
        plan_id=plan.id, version_no=version_no,
        status=note_status or plan.status,
        snapshot_json=json.dumps(snap, ensure_ascii=False),
        metrics_json=plan.metrics_json, created_by=username,
    )
    session.add(arch)
    session.commit()
    return version_no


# ───────────────── 结果落库 ─────────────────

def persist_solution(session: Session, plan: MealPlan, res, username: str,
                     solver_params: dict) -> MealPlan:
    # 删除未锁定旧条目
    old = session.exec(select(MealItem).where(MealItem.plan_id == plan.id)).all()
    for it in old:
        session.delete(it)
    for it in res.items:
        session.add(MealItem(
            plan_id=plan.id, day_index=it["day_index"], meal_date=it["meal_date"],
            slot=it["slot"], dish_id=it["dish_id"], dish_name=it["dish_name"],
            portion_g=it["portion_g"], locked=it.get("locked", False),
            detail_json=json.dumps({"cost": it.get("cost"), "dish_type": it.get("dish_type")},
                                   ensure_ascii=False),
        ))
    plan.metrics_json = json.dumps({
        "daily_nutrients": res.daily_nutrients,
        "daily_costs": res.daily_costs,
        "total_cost": res.total_cost,
        "score_breakdown": res.score_breakdown,
        "relaxations": res.relaxations,
        "warnings": res.warnings,
        "status": res.status,
        "objective": res.objective,
        "candidate_count": res.candidate_count,
        "solve_seconds": res.solve_seconds,
    }, ensure_ascii=False)
    plan.solver_params = json.dumps(solver_params, ensure_ascii=False)
    plan.updated_at = datetime.now()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    archive_version(session, plan, username)
    return plan


# ───────────────── 求解任务（后台）─────────────────

def run_solve_task(task_id: int) -> None:
    # 后台线程使用独立会话
    from ..database import new_session
    session = new_session()
    try:
        task = session.get(Task, task_id)
        task.status = "running"
        task.progress = 10
        task.started_at = datetime.now()
        session.add(task)
        session.commit()

        params = json.loads(task.params_json)
        elder = session.get(Elder, params["elder_id"])
        if not elder or not elder.is_active:
            raise ValueError("老人不存在或已停用")

        start = date.fromisoformat(params["start_date"])
        days = int(params.get("days", 1))
        dates = dates_for(start, days)
        slots = list(SLOTS)
        dishes = session.exec(select(Dish).where(Dish.is_active == True)).all()  # noqa: E712

        engine, rule_ver = build_engine(session)
        person = compile_person(elder)
        tr = elder_targets(elder)

        locked = params.get("locked_items", [])
        plan_id = params.get("plan_id")
        plan = None
        if plan_id:
            plan = session.get(MealPlan, plan_id)
            if plan:
                # 局部重求解：保留锁定条目
                existing = session.exec(
                    select(MealItem).where(MealItem.plan_id == plan.id)
                ).all()
                locked = [{
                    "day_index": it.day_index, "slot": it.slot,
                    "dish_id": it.dish_id, "portion_g": it.portion_g,
                    "dish_name": it.dish_name,
                } for it in existing if it.locked]

        task.progress = 30
        session.add(task)
        session.commit()

        cost_limit = params.get("cost_limit_day") or elder.cost_limit_day
        solver_params = {
            "weights": params.get("weights") or solver_mod.DEFAULT_WEIGHTS,
            "time_limit_seconds": params.get("time_limit_seconds", 20),
            "max_repeat_week": 2,
            "unit_g": solver_mod.UNIT_G,
            "cost_limit_day": cost_limit,
            "rule_version": rule_ver,
            "targets": tr.as_dict()["targets"],
            "mode": "resolve" if plan_id else "solve",
        }
        res = solver_mod.solve(
            days=days, dates=dates, slots=slots, dishes=dishes,
            person_ctx=person, engine=engine,
            targets=tr.as_dict()["targets"] and {
                k: tuple(v) for k, v in tr.as_dict()["targets"].items()},
            cost_limit_day=cost_limit,
            weights=params.get("weights"),
            time_limit_seconds=params.get("time_limit_seconds", 20),
            random_seed=params.get("random_seed", 42),
            locked_items=locked,
        )

        task.progress = 80
        session.add(task)
        session.commit()

        if res.status == "infeasible":
            task.status = "failed"
            task.progress = 100
            task.message = "；".join(res.warnings) or "无可行解"
            task.result_json = json.dumps(
                {"infeasible": True, "warnings": res.warnings,
                 "relaxations": res.relaxations}, ensure_ascii=False)
            task.finished_at = datetime.now()
            session.add(task)
            session.commit()
            return

        if plan is None:
            plan = MealPlan(
                elder_id=elder.id,
                title=params.get("title") or
                      f"{elder.name}-{start.isoformat()}{'周配餐' if days > 1 else '日配餐'}",
                period_type="week" if days > 1 else "day",
                start_date=start.isoformat(),
                end_date=dates[-1], rule_version=rule_ver,
                created_by=task.created_by,
            )
            session.add(plan)
            session.commit()
            session.refresh(plan)

        persist_solution(session, plan, res, task.created_by, solver_params)

        task.status = "success"
        task.progress = 100
        task.message = f"求解完成（{res.status}），共 {len(res.items)} 个餐品"
        task.result_json = json.dumps({"plan_id": plan.id, "status": res.status},
                                      ensure_ascii=False)
        task.finished_at = datetime.now()
        session.add(task)
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        task = session.get(Task, task_id)
        task.status = "failed"
        task.message = f"{type(exc).__name__}: {exc}"
        task.finished_at = datetime.now()
        session.add(task)
        session.commit()
    finally:
        session.close()


# ───────────────── 手动更新（乐观锁）─────────────────

class ConflictError(Exception):
    pass


def apply_manual_update(session: Session, plan: MealPlan, items_in: list[dict],
                        username: str, lock_version: int) -> dict:
    """整体替换条目（前端提交完整清单），返回冲突映射。

    乐观锁：lock_version 不匹配 → ConflictError。
    实时冲突：每道菜跑规则引擎，forbid 仍允许保存但高亮（由前端决策），
              这里返回 conflicts；locked 菜保留。
    """
    if plan.lock_version != lock_version:
        raise ConflictError(
            f"方案已被他人修改（服务器版本 v{plan.lock_version}，客户端基于 v{lock_version}），请刷新后重试")

    elder = session.get(Elder, plan.elder_id)
    engine, _ = build_engine(session)
    person = compile_person(elder)
    ing_map = ingredient_names_for_dishes(session)
    dishes = {d.id: d for d in session.exec(select(Dish)).all()}

    conflicts: dict[str, list[dict]] = {}
    valid_items = []
    total_cost = 0.0
    for it in items_in:
        d = dishes.get(it["dish_id"])
        if not d:
            continue
        dctx = compile_dish(d, ing_map.get(d.id, []))
        viol = engine.evaluate_dish(person, dctx)
        key = f"{it['day_index']}|{it['slot']}|{it['dish_id']}"
        if viol:
            conflicts[key] = [v.to_dict() for v in viol]
        cost = (d.portion_cost or 0) * it["portion_g"] / max(d.portion_g, 1)
        total_cost += cost
        valid_items.append(MealItem(
            plan_id=plan.id, day_index=it["day_index"],
            meal_date=it.get("meal_date", ""), slot=it["slot"],
            dish_id=d.id, dish_name=d.name, portion_g=it["portion_g"],
            locked=it.get("locked", False),
            detail_json=json.dumps({"cost": round(cost, 2),
                                    "dish_type": d.dish_type}, ensure_ascii=False),
        ))

    old = session.exec(select(MealItem).where(MealItem.plan_id == plan.id)).all()
    for o in old:
        session.delete(o)
    session.add_all(valid_items)

    # 重算指标（保持与求解器指标口径一致）
    metrics = recompute_metrics(session, plan, elder, valid_items, dishes)
    plan.metrics_json = json.dumps(metrics, ensure_ascii=False)
    plan.lock_version += 1
    plan.updated_at = datetime.now()
    session.add(plan)
    session.commit()
    archive_version(session, plan, username)
    return {"conflicts": conflicts, "metrics": metrics, "lock_version": plan.lock_version}


def recompute_metrics(session: Session, plan: MealPlan, elder: Elder,
                      items: list[MealItem], dishes: dict[int, Dish]) -> dict:
    start = date.fromisoformat(plan.start_date)
    days = 1
    if plan.period_type == "week":
        days = max(1, (date.fromisoformat(plan.end_date) - start).days + 1)
    nutrient_keys = ["energy_kcal", "protein_g", "fat_g", "carbs_g", "dietary_fiber_g",
                     "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg",
                     "cholesterol_mg", "sugar_g", "purine_mg"]
    daily_n, daily_c = [], []
    for d in range(days):
        dn = {k: 0.0 for k in nutrient_keys}
        dc = 0.0
        for it in items:
            if it.day_index != d:
                continue
            dish = dishes.get(it.dish_id)
            if not dish:
                continue
            f = it.portion_g / 100.0
            for k in nutrient_keys:
                dn[k] += getattr(dish, k, 0.0) * f
            dc += (dish.portion_cost or 0) * it.portion_g / max(dish.portion_g, 1)
        daily_n.append({k: round(v, 1) for k, v in dn.items()})
        daily_c.append(round(dc, 2))
    tr = elder_targets(elder)
    targets = tr.as_dict()["targets"]
    dev = {}
    for k in ("energy_kcal", "protein_g", "sodium_mg", "potassium_mg",
              "phosphorus_mg", "dietary_fiber_g"):
        lo, hi = targets[k]
        vals = [dn[k] for dn in daily_n]
        avg = sum(vals) / len(vals)
        dev[k] = {"avg": round(avg, 1), "target": [lo, hi],
                  "in_range": lo <= avg <= hi}
    return {
        "daily_nutrients": daily_n, "daily_costs": daily_c,
        "total_cost": round(sum(daily_c), 2),
        "manual": True,
        "nutrient_check": dev,
    }
