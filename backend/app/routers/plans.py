"""排餐方案路由：求解、手动调整、冲突高亮、发布/归档/版本/回滚。"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user, require_roles
from ..models import (Dish, MenuItem, MenuPlan, PlanVersion, Resident, SolveTask,
                      User)
from ..plan_service import (ConflictError, check_plan_conflicts, load_context,
                            plan_detail, publish_plan, rollback_plan, run_solve)
from ..schemas import (CheckPlanIn, LockItem, PlanCreate, PlanItemPatch,
                       PublishIn, ResolveIn)
from ..tasks import run_solve_task

router = APIRouter(prefix="/api/plans", tags=["排餐方案"])

WRITER = {"admin", "nutritionist"}


def _get_plan(session: Session, plan_id: int) -> MenuPlan:
    p = session.get(MenuPlan, plan_id)
    if not p:
        raise HTTPException(404, "方案不存在")
    return p


def _check_version(plan: MenuPlan, version: int):
    if version != plan.version:
        raise HTTPException(409, f"方案已被他人修改（当前版本 v{plan.version}），"
                                f"请刷新后重试（乐观锁冲突）")


# ---------------- 方案 CRUD ----------------

@router.get("")
def list_plans(resident_id: int | None = None, status_: str | None = None,
               session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    stmt = select(MenuPlan)
    if resident_id:
        stmt = stmt.where(MenuPlan.resident_id == resident_id)
    if status_:
        stmt = stmt.where(MenuPlan.status == status_)
    plans = session.exec(stmt.order_by(MenuPlan.id.desc())).all()
    residents = {r.id: r.name for r in session.exec(select(Resident)).all()}
    return [{
        "id": p.id, "name": p.name, "resident_id": p.resident_id,
        "resident_name": residents.get(p.resident_id, str(p.resident_id)),
        "start_date": p.start_date, "days": p.days, "status": p.status,
        "budget_per_day": p.budget_per_day, "version": p.version,
        "score": p.score, "created_by": p.created_by,
        "created_at": p.created_at,
    } for p in plans]


@router.post("", status_code=201)
def create_plan(body: PlanCreate, bg: BackgroundTasks,
                session: Session = Depends(get_session),
                user: User = Depends(require_roles(*WRITER))):
    if not session.get(Resident, body.resident_id):
        raise HTTPException(404, "老人不存在")
    plan = MenuPlan(name=body.name or f"{body.days}天配餐方案",
                    resident_id=body.resident_id, start_date=body.start_date,
                    days=body.days, budget_per_day=body.budget_per_day,
                    created_by=user.username)
    session.add(plan)
    audit(session, user, "create", "plan", 0, {"resident_id": body.resident_id})
    session.commit()
    session.refresh(plan)
    task = SolveTask(task_type="solve", plan_id=plan.id,
                     resident_id=body.resident_id,
                     params={"time_limit_sec": 20}, created_by=user.username)
    session.add(task)
    session.commit()
    session.refresh(task)
    bg.add_task(run_solve_task, task.id)
    return {"plan_id": plan.id, "task_id": task.id}


@router.get("/{plan_id}")
def get_plan(plan_id: int, session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    return plan_detail(session, _get_plan(session, plan_id))


@router.delete("/{plan_id}")
def delete_plan(plan_id: int, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin"))):
    plan = _get_plan(session, plan_id)
    if plan.status == "published":
        raise HTTPException(400, "已发布方案不可删除，请先归档")
    for it in session.exec(select(MenuItem).where(MenuItem.plan_id == plan_id)).all():
        session.delete(it)
    session.delete(plan)
    audit(session, user, "delete", "plan", plan_id)
    session.commit()
    return {"ok": True}


# ---------------- 手动调整 / 锁定 / 冲突 ----------------

@router.post("/{plan_id}/check")
def check_plan(plan_id: int, body: CheckPlanIn,
               session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    """手动拖拽时实时校验：返回 hard/soft 冲突，不落库。"""
    plan = _get_plan(session, plan_id)
    resident = session.get(Resident, body.resident_id or plan.resident_id)
    pairs = [(it["day_index"], it["slot"], it.get("line", "main"), it["dish_id"])
             for it in body.items]
    res = check_plan_conflicts(session, resident, pairs)
    # 成本校验（按天）
    dishes = {d.id: d for d in session.exec(select(Dish)).all()}
    day_cost: dict[int, float] = {}
    for day, slot, line, did in pairs:
        day_cost[day] = day_cost.get(day, 0) + getattr(dishes.get(did), "cost", 0)
    cost_over = [{"day_index": d, "cost": round(c, 2),
                  "budget": plan.budget_per_day}
                 for d, c in day_cost.items() if c > plan.budget_per_day]
    res["cost_over"] = cost_over
    res["feasible"] = res["feasible"] and not cost_over
    return res


@router.patch("/{plan_id}/items")
def patch_item(plan_id: int, body: PlanItemPatch,
               session: Session = Depends(get_session),
               user: User = Depends(require_roles(*WRITER))):
    """拖拽换菜：替换某槽位并立即返回该方案全部冲突。"""
    plan = _get_plan(session, plan_id)
    _check_version(plan, body.version)
    dish = session.get(Dish, body.dish_id)
    if not dish or not dish.active:
        raise HTTPException(400, "菜品不存在或已停用")
    target = session.exec(select(MenuItem).where(
        MenuItem.plan_id == plan_id, MenuItem.day_index == body.day_index,
        MenuItem.slot == body.slot, MenuItem.line == body.line)).first()
    if not target:
        raise HTTPException(404, "槽位不存在")
    target.dish_id = body.dish_id
    target.locked = body.locked
    target.locked_by = user.username if body.locked else ""
    session.add(target)
    plan.version += 1
    session.add(plan)
    audit(session, user, "update", "plan_item", plan_id,
          {"day": body.day_index, "slot": body.slot, "line": body.line,
           "dish_id": body.dish_id, "locked": body.locked})
    session.commit()
    session.refresh(plan)
    # 返回完整冲突视图供前端高亮
    items = session.exec(select(MenuItem).where(MenuItem.plan_id == plan_id)).all()
    resident = session.get(Resident, plan.resident_id)
    conflicts = check_plan_conflicts(
        session, resident,
        [(i.day_index, i.slot, i.line, i.dish_id) for i in items])
    return {"ok": True, "version": plan.version,
            "item_id": target.id, "conflicts": conflicts}


@router.post("/{plan_id}/lock")
def lock_item(plan_id: int, body: LockItem, session: Session = Depends(get_session),
              user: User = Depends(require_roles(*WRITER))):
    plan = _get_plan(session, plan_id)
    _check_version(plan, body.version)
    item = session.get(MenuItem, body.item_id)
    if not item or item.plan_id != plan_id:
        raise HTTPException(404, "餐次项不存在")
    item.locked = body.locked
    item.locked_by = user.username if body.locked else ""
    session.add(item)
    plan.version += 1
    session.add(plan)
    audit(session, user, "update", "lock_item", body.item_id,
          {"locked": body.locked})
    session.commit()
    return {"ok": True, "version": plan.version}


# ---------------- 局部/全部重求解 ----------------

@router.post("/{plan_id}/resolve", status_code=202)
def resolve(plan_id: int, body: ResolveIn, bg: BackgroundTasks,
            session: Session = Depends(get_session),
            user: User = Depends(require_roles(*WRITER))):
    plan = _get_plan(session, plan_id)
    _check_version(plan, body.version)
    task = SolveTask(task_type="resolve", plan_id=plan_id,
                     resident_id=plan.resident_id,
                     params={"day_index": body.day_index,
                             "time_limit_sec": body.time_limit_sec},
                     created_by=user.username)
    session.add(task)
    audit(session, user, "resolve", "plan", plan_id,
          {"day_index": body.day_index})
    session.commit()
    session.refresh(task)
    bg.add_task(run_solve_task, task.id)
    return {"task_id": task.id}


# ---------------- 发布 / 归档 / 版本 ----------------

@router.post("/{plan_id}/publish")
def publish(plan_id: int, body: PublishIn, session: Session = Depends(get_session),
            user: User = Depends(require_roles(*WRITER))):
    plan = _get_plan(session, plan_id)
    _check_version(plan, body.version)
    items = session.exec(select(MenuItem).where(MenuItem.plan_id == plan_id)).all()
    resident = session.get(Resident, plan.resident_id)
    conflicts = check_plan_conflicts(
        session, resident,
        [(i.day_index, i.slot, i.line, i.dish_id) for i in items])
    if conflicts["hard"]:
        raise HTTPException(400, f"存在 {len(conflicts['hard'])} 项硬约束冲突，"
                                f"无法发布，请先处理")
    pv = publish_plan(session, plan, user.username, body.note)
    audit(session, user, "publish", "plan", plan_id, {"version_no": pv.version_no})
    session.commit()
    return {"ok": True, "version_no": pv.version_no, "plan_version": plan.version}


@router.post("/{plan_id}/archive")
def archive(plan_id: int, session: Session = Depends(get_session),
            user: User = Depends(require_roles("admin", "nutritionist"))):
    plan = _get_plan(session, plan_id)
    plan.status = "archived"
    plan.version += 1
    session.add(plan)
    audit(session, user, "archive", "plan", plan_id)
    session.commit()
    return {"ok": True, "version": plan.version}


@router.get("/{plan_id}/versions")
def versions(plan_id: int, session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    _get_plan(session, plan_id)
    rows = session.exec(select(PlanVersion).where(
        PlanVersion.plan_id == plan_id).order_by(PlanVersion.version_no.desc())).all()
    return [{"id": v.id, "version_no": v.version_no, "note": v.note,
             "created_by": v.created_by, "created_at": v.created_at,
             "score": v.score} for v in rows]


@router.get("/{plan_id}/versions/{version_no}")
def get_version(plan_id: int, version_no: int,
                session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    _get_plan(session, plan_id)
    v = session.exec(select(PlanVersion).where(
        PlanVersion.plan_id == plan_id,
        PlanVersion.version_no == version_no)).first()
    if not v:
        raise HTTPException(404, "版本不存在")
    return v.snapshot


@router.get("/{plan_id}/compare/{v_a}/{v_b}")
def compare(plan_id: int, v_a: int, v_b: int,
            session: Session = Depends(get_session),
            user: User = Depends(get_current_user)):
    """版本对比：营养指标与逐槽位菜品差异。"""
    _get_plan(session, plan_id)
    snaps = {}
    for no in (v_a, v_b):
        v = session.exec(select(PlanVersion).where(
            PlanVersion.plan_id == plan_id, PlanVersion.version_no == no)).first()
        if not v:
            raise HTTPException(404, f"版本 v{no} 不存在")
        snaps[no] = v.snapshot
    a, b = snaps[v_a], snaps[v_b]
    item_diff = []
    key = lambda x: (x["day_index"], x["slot"], x["line"])
    amap = {key(x): x for x in a["items"]}
    bmap = {key(x): x for x in b["items"]}
    for k_ in sorted(set(amap) | set(bmap)):
        an, bn = amap.get(k_, {}).get("dish_name"), bmap.get(k_, {}).get("dish_name")
        if an != bn:
            item_diff.append({"day_index": k_[0], "slot": k_[1], "line": k_[2],
                              f"v{v_a}": an, f"v{v_b}": bn})
    return {
        "v_a": v_a, "v_b": v_b,
        "score_a": a["plan"].get("score"), "score_b": b["plan"].get("score"),
        "totals_a": a["plan"].get("totals"), "totals_b": b["plan"].get("totals"),
        "item_diff": item_diff,
    }


@router.post("/{plan_id}/rollback/{version_no}")
def rollback(plan_id: int, version_no: int, session: Session = Depends(get_session),
             user: User = Depends(require_roles(*WRITER))):
    plan = _get_plan(session, plan_id)
    try:
        detail = rollback_plan(session, plan, version_no, user.username)
    except ConflictError as e:
        raise HTTPException(404, str(e))
    audit(session, user, "rollback", "plan", plan_id, {"to_version": version_no})
    session.commit()
    return {"ok": True, "plan": detail}
