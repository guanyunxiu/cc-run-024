"""配餐方案业务逻辑：求解、手动调整、冲突检查、发布/回滚、乐观锁。"""
import json
from datetime import datetime

from sqlmodel import Session, select

from .models import (Dish, MenuItem, MenuPlan, PlanVersion, Resident, Rule)
from .nutrition import targets_snapshot
from .rules import evaluate_dish
from .solver import SLOT_LINES, solve_menu

SLOT_ORDER = {s: i for i, s in enumerate(SLOT_LINES)}
LINE_ORDER = {"staple": 0, "protein": 1, "entree": 1, "vegetable": 2,
              "soup": 3, "snack": 0}


class ConflictError(Exception):
    pass


def load_context(session: Session, resident_id: int):
    resident = session.get(Resident, resident_id)
    if not resident:
        raise ConflictError("老人不存在")
    dishes = session.exec(select(Dish).where(Dish.active == True)).all()  # noqa: E712
    rules = session.exec(select(Rule)).all()
    return resident, dishes, rules


def items_as_locks(items: list[MenuItem]) -> dict:
    return {(it.day_index, it.slot, it.line): it.dish_id
            for it in items if it.locked}


def locks_from_result(result_items: list[dict]) -> dict:
    return {(it["day_index"], it["slot"], it["line"]): it["dish_id"]
            for it in result_items if it.get("locked")}


def replace_items(session: Session, plan: MenuPlan, result_items: list[dict],
                  keep_locks: bool = True) -> list[MenuItem]:
    """用求解结果重建 MenuItem，保留 locked 标记。"""
    old = session.exec(select(MenuItem).where(MenuItem.plan_id == plan.id)).all()
    locked_map = {(o.day_index, o.slot, o.line): (o.locked, o.locked_by)
                  for o in old}
    for o in old:
        session.delete(o)
    session.flush()
    new_items = []
    for it in result_items:
        key = (it["day_index"], it["slot"], it["line"])
        locked, by = locked_map.get(key, (False, ""))
        mi = MenuItem(plan_id=plan.id, day_index=it["day_index"], slot=it["slot"],
                      line=it["line"], dish_id=it["dish_id"],
                      locked=locked if keep_locks else False,
                      locked_by=by if keep_locks else "")
        session.add(mi)
        new_items.append(mi)
    session.flush()
    return new_items


def _json_default(o):
    if isinstance(o, (datetime, )):
        return o.isoformat()
    import datetime as _dt
    if isinstance(o, _dt.date):
        return o.isoformat()
    return str(o)


def run_solve(session: Session, plan: MenuPlan, resident: Resident, dishes, rules,
              time_limit_sec: int = 20, allowed_days: set | None = None,
              existing_items: list[MenuItem] | None = None,
              weights: dict | None = None) -> dict:
    snap = resident.targets or targets_snapshot(resident)
    targets = snap["targets"]
    locks = items_as_locks(existing_items) if existing_items else {}
    # 局部重算：不在求解范围内的天，其全部既有菜品视为固定锁传入
    if allowed_days is not None and existing_items:
        for it in existing_items:
            if it.day_index not in allowed_days:
                locks[(it.day_index, it.slot, it.line)] = it.dish_id
    result = solve_menu(
        resident, dishes, rules, targets, days=plan.days,
        budget_per_day=plan.budget_per_day, locks=locks,
        weights=weights, time_limit_sec=time_limit_sec,
        allowed_days=allowed_days)
    if result["status"] != "success":
        return result
    # 局部重算：把未参与求解天的既有菜品合并进结果
    replace_items(session, plan, result["items"])
    plan.targets_snapshot = snap
    plan.rule_version = ", ".join(sorted({r.version for r in rules if r.active}))
    plan.solver_params = {
        "time_limit_sec": time_limit_sec,
        "allowed_days": sorted(allowed_days) if allowed_days is not None else "all",
        "weights": weights or {},
    }
    plan.score = result["score"]
    plan.totals = {"totals": result["totals"], "day_totals": result["day_totals"],
                   "soft_violations": result["soft_violations"],
                   "warnings": result["warnings"]}
    plan.version += 1
    plan.updated_at = datetime.utcnow()
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return result


def check_plan_conflicts(session: Session, resident: Resident,
                         item_dish_pairs: list[tuple]) -> dict:
    """item_dish_pairs: [(day_index, slot, line, dish_id)] 实时规则校验。"""
    rules = session.exec(select(Rule)).all()
    dish_map = {d.id: d for d in session.exec(select(Dish)).all()}
    hard, soft = [], []
    for day, slot, line, did in item_dish_pairs:
        dish = dish_map.get(did)
        if not dish:
            hard.append({"day_index": day, "slot": slot, "line": line,
                         "dish_id": did, "message": "菜品不存在或已停用"})
            continue
        ev = evaluate_dish(dish, resident, rules)
        for v in ev["hard"]:
            hard.append({"day_index": day, "slot": slot, "line": line,
                         "dish_name": dish.name, **v})
        for v in ev["soft"]:
            soft.append({"day_index": day, "slot": slot, "line": line,
                         "dish_name": dish.name, **v})
    return {"hard": hard, "soft": soft, "feasible": len(hard) == 0}


def plan_detail(session: Session, plan: MenuPlan) -> dict:
    items = session.exec(
        select(MenuItem).where(MenuItem.plan_id == plan.id)
    ).all()
    dish_map = {d.id: d for d in session.exec(select(Dish)).all()}
    item_rows = []
    for it in sorted(items, key=lambda x: (x.day_index, SLOT_ORDER.get(x.slot, 9),
                                           LINE_ORDER.get(x.line, 9))):
        d = dish_map.get(it.dish_id)
        item_rows.append({
            "id": it.id, "day_index": it.day_index, "slot": it.slot,
            "line": it.line, "dish_id": it.dish_id,
            "dish_name": d.name if d else f"#{it.dish_id}",
            "category": d.category if d else "",
            "iddsi_level": d.iddsi_level if d else None,
            "cost": d.cost if d else 0,
            "locked": it.locked, "locked_by": it.locked_by,
        })
    return {
        "id": plan.id, "name": plan.name, "resident_id": plan.resident_id,
        "start_date": plan.start_date, "days": plan.days, "status": plan.status,
        "budget_per_day": plan.budget_per_day, "version": plan.version,
        "targets_snapshot": plan.targets_snapshot,
        "rule_version": plan.rule_version, "solver_params": plan.solver_params,
        "score": plan.score, "totals": plan.totals,
        "created_by": plan.created_by, "created_at": plan.created_at,
        "published_at": plan.published_at, "updated_at": plan.updated_at,
        "items": item_rows,
    }


def publish_plan(session: Session, plan: MenuPlan, username: str, note: str) -> PlanVersion:
    items = session.exec(select(MenuItem).where(MenuItem.plan_id == plan.id)).all()
    last = session.exec(
        select(PlanVersion).where(PlanVersion.plan_id == plan.id)
        .order_by(PlanVersion.version_no.desc())
    ).first()
    vno = (last.version_no + 1) if last else 1
    detail = plan_detail(session, plan)
    # 深拷贝并把 date/datetime 转成字符串，保证 SQLite JSON 可序列化
    snap = json.loads(json.dumps({
        "plan": {k: v for k, v in detail.items() if k != "items"},
        "items": detail["items"],
    }, default=_json_default))
    pv = PlanVersion(plan_id=plan.id, version_no=vno, snapshot=snap,
                     score=plan.score or {}, created_by=username, note=note)
    session.add(pv)
    plan.status = "published"
    plan.published_at = datetime.utcnow()
    plan.version += 1
    session.add(plan)
    session.commit()
    session.refresh(pv)
    return pv


def rollback_plan(session: Session, plan: MenuPlan, version_no: int, username: str) -> dict:
    pv = session.exec(
        select(PlanVersion).where(PlanVersion.plan_id == plan.id,
                                  PlanVersion.version_no == version_no)
    ).first()
    if not pv:
        raise ConflictError("目标版本不存在")
    old = session.exec(select(MenuItem).where(MenuItem.plan_id == plan.id)).all()
    for o in old:
        session.delete(o)
    session.flush()
    for it in pv.snapshot["items"]:
        session.add(MenuItem(
            plan_id=plan.id, day_index=it["day_index"], slot=it["slot"],
            line=it["line"], dish_id=it["dish_id"],
            locked=it.get("locked", False), locked_by=it.get("locked_by", "")))
    p = pv.snapshot["plan"]
    plan.score = p.get("score") or {}
    plan.totals = p.get("totals") or {}
    plan.status = "published"
    plan.published_at = datetime.utcnow()
    plan.version += 1
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan_detail(session, plan)
