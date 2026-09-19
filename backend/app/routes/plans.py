"""配餐方案路由：发起求解、查询、手动调整、发布/归档/回滚、版本对比。"""
import json
from datetime import datetime, date
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session, new_session
from ..models import User, MealPlan, MealItem, PlanVersionArchive, Task, Dish, Elder
from ..schemas import SolveRequest, PlanUpdateIn
from ..services.planner import (run_solve_task, apply_manual_update, ConflictError,
                                archive_version)
from ..services import audit
from .deps import get_current_user

router = APIRouter(prefix="/api/plans", tags=["配餐方案"])


def _detail(session: Session, plan: MealPlan) -> dict:
    items = session.exec(
        select(MealItem).where(MealItem.plan_id == plan.id)
        .order_by(MealItem.day_index, MealItem.slot, MealItem.id)
    ).all()
    out = plan.model_dump()
    out["items"] = []
    for it in items:
        d = it.model_dump()
        try:
            d["detail"] = json.loads(it.detail_json or "{}")
        except json.JSONDecodeError:
            d["detail"] = {}
        out["items"].append(d)
    try:
        out["metrics"] = json.loads(plan.metrics_json or "{}")
    except json.JSONDecodeError:
        out["metrics"] = {}
    try:
        out["solver_params"] = json.loads(plan.solver_params or "{}")
    except json.JSONDecodeError:
        out["solver_params"] = {}
    return out


@router.get("")
def list_plans(elder_id: int | None = None,
               status_filter: str | None = None,
               session: Session = Depends(get_session),
               _: User = Depends(get_current_user)):
    stmt = select(MealPlan).order_by(MealPlan.id.desc())
    if elder_id:
        stmt = stmt.where(MealPlan.elder_id == elder_id)
    if status_filter:
        stmt = stmt.where(MealPlan.status == status_filter)
    plans = session.exec(stmt).all()
    out = []
    for p in plans:
        d = p.model_dump()
        try:
            d["metrics"] = json.loads(p.metrics_json or "{}")
        except json.JSONDecodeError:
            d["metrics"] = {}
        elder = session.get(Elder, p.elder_id)
        d["elder_name"] = elder.name if elder else f"#{p.elder_id}"
        out.append(d)
    return out


@router.get("/{plan_id}")
def get_plan(plan_id: int, session: Session = Depends(get_session),
             _: User = Depends(get_current_user)):
    p = session.get(MealPlan, plan_id)
    if not p:
        raise HTTPException(404, "方案不存在")
    return _detail(session, p)


@router.post("/solve")
def create_solve_task(body: SolveRequest, bg: BackgroundTasks,
                      session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    elder = session.get(Elder, body.elder_id)
    if not elder:
        raise HTTPException(404, "老人不存在")
    if body.days > 1 and body.period_type != "week":
        raise HTTPException(400, "多天必须为 week 类型")
    task = Task(
        task_type="solve", status="pending",
        params_json=body.model_dump_json(),
        created_by=user.username,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    bg.add_task(run_solve_task, task.id)
    audit.log(session, user.username, "plan.solve_submit", "task", task.id,
              {"elder_id": body.elder_id, "days": body.days,
               "plan_id": body.plan_id})
    return {"task_id": task.id, "status": "pending"}


@router.put("/{plan_id}")
def update_plan_items(plan_id: int, body: PlanUpdateIn,
                      session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    plan = session.get(MealPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    if plan.status == "archived":
        raise HTTPException(400, "已归档方案不可修改")
    items = [i.model_dump() for i in body.items] if body.items is not None else None
    try:
        if items is None:
            if body.title is not None:
                plan.title = body.title
                plan.lock_version += 1
                session.add(plan)
                session.commit()
            return _detail(session, plan)
        result = apply_manual_update(session, plan, items, user.username,
                                     body.lock_version)
    except ConflictError as e:
        raise HTTPException(409, str(e))
    audit.log(session, user.username, "plan.manual_update", "plan", plan_id,
              {"conflict_count": len(result["conflicts"]),
               "lock_version": result["lock_version"]})
    return _detail(session, plan)


@router.post("/{plan_id}/resolve")
def resolve_plan(plan_id: int, bg: BackgroundTasks,
                 session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    """局部重求解：已锁定条目固定，其余重新优化。"""
    plan = session.get(MealPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    locked = session.exec(select(MealItem).where(
        MealItem.plan_id == plan_id, MealItem.locked == True)).all()  # noqa: E712
    if not locked:
        raise HTTPException(400, "没有锁定的菜品；局部重求解需要先锁定至少一道菜")
    days = 7 if plan.period_type == "week" else 1
    payload = SolveRequest(
        elder_id=plan.elder_id, period_type=plan.period_type,
        start_date=date.fromisoformat(plan.start_date), days=days,
        title=plan.title, plan_id=plan.id)
    task = Task(task_type="resolve", status="pending",
                params_json=payload.model_dump_json(), created_by=user.username)
    session.add(task)
    session.commit()
    session.refresh(task)
    bg.add_task(run_solve_task, task.id)
    audit.log(session, user.username, "plan.resolve_submit", "task", task.id,
              {"plan_id": plan_id})
    return {"task_id": task.id, "status": "pending"}


@router.post("/{plan_id}/publish")
def publish_plan(plan_id: int, lock_version: int,
                 session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    plan = session.get(MealPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    if plan.lock_version != lock_version:
        raise HTTPException(409, "版本冲突：方案已被他人修改，请刷新")
    plan.status = "published"
    plan.published_at = datetime.now()
    plan.lock_version += 1
    session.add(plan)
    session.commit()
    archive_version(session, plan, user.username, note_status="published")
    audit.log(session, user.username, "plan.publish", "plan", plan_id,
              {}, rule_version=plan.rule_version)
    return _detail(session, plan)


@router.post("/{plan_id}/archive")
def archive_plan(plan_id: int, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    plan = session.get(MealPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    plan.status = "archived"
    session.add(plan)
    session.commit()
    audit.log(session, user.username, "plan.archive", "plan", plan_id)
    return _detail(session, plan)


@router.get("/{plan_id}/versions")
def plan_versions(plan_id: int, session: Session = Depends(get_session),
                  _: User = Depends(get_current_user)):
    rows = session.exec(
        select(PlanVersionArchive).where(PlanVersionArchive.plan_id == plan_id)
        .order_by(PlanVersionArchive.version_no.desc())
    ).all()
    return [{"id": r.id, "version_no": r.version_no, "status": r.status,
             "created_by": r.created_by, "created_at": r.created_at,
             "metrics": json.loads(r.metrics_json or "{}")} for r in rows]


@router.get("/{plan_id}/versions/{version_no}")
def get_version(plan_id: int, version_no: int,
                session: Session = Depends(get_session),
                _: User = Depends(get_current_user)):
    r = session.exec(select(PlanVersionArchive).where(
        PlanVersionArchive.plan_id == plan_id,
        PlanVersionArchive.version_no == version_no)).first()
    if not r:
        raise HTTPException(404, "版本不存在")
    return json.loads(r.snapshot_json)


@router.post("/{plan_id}/rollback/{version_no}")
def rollback(plan_id: int, version_no: int,
             session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    plan = session.get(MealPlan, plan_id)
    if not plan:
        raise HTTPException(404, "方案不存在")
    r = session.exec(select(PlanVersionArchive).where(
        PlanVersionArchive.plan_id == plan_id,
        PlanVersionArchive.version_no == version_no)).first()
    if not r:
        raise HTTPException(404, "版本不存在")
    snap = json.loads(r.snapshot_json)
    old_items = session.exec(select(MealItem).where(MealItem.plan_id == plan_id)).all()
    for o in old_items:
        session.delete(o)
    for it in snap["items"]:
        it.pop("id", None)
        session.add(MealItem(**it))
    plan.metrics_json = r.metrics_json
    plan.status = "draft"
    plan.lock_version += 1
    plan.updated_at = datetime.now()
    session.add(plan)
    session.commit()
    audit.log(session, user.username, "plan.rollback", "plan", plan_id,
              {"rollback_to_version": version_no})
    return _detail(session, plan)


@router.get("/{plan_id}/diff/{v_a}/{v_b}")
def diff_versions(plan_id: int, v_a: int, v_b: int,
                  session: Session = Depends(get_session),
                  _: User = Depends(get_current_user)):
    def load(vn):
        r = session.exec(select(PlanVersionArchive).where(
            PlanVersionArchive.plan_id == plan_id,
            PlanVersionArchive.version_no == vn)).first()
        return json.loads(r.snapshot_json) if r else None
    sa, sb = load(v_a), load(v_b)
    if not sa or not sb:
        raise HTTPException(404, "版本不存在")
    key = lambda i: f"{i['day_index']}|{i['slot']}|{i['dish_id']}"
    ma = {key(i): i for i in sa["items"]}
    mb = {key(i): i for i in sb["items"]}
    added = [mb[k] for k in mb.keys() - ma.keys()]
    removed = [ma[k] for k in ma.keys() - mb.keys()]
    changed = []
    for k in ma.keys() & mb.keys():
        if ma[k]["portion_g"] != mb[k]["portion_g"] or ma[k]["locked"] != mb[k]["locked"]:
            changed.append({"from": ma[k], "to": mb[k]})
    return {
        "added": added, "removed": removed, "changed": changed,
        "metrics_a": json.loads(sa["plan"].get("metrics_json") or "{}"),
        "metrics_b": json.loads(sb["plan"].get("metrics_json") or "{}"),
    }
