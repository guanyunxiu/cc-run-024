"""后台求解任务：独立数据库会话执行，前端轮询状态。"""
from datetime import datetime

from sqlmodel import Session, select

from .database import engine
from .models import MenuItem, MenuPlan, SolveTask
from .plan_service import load_context, run_solve


def _update(task_id: int, **kw):
    with Session(engine) as s:
        t = s.get(SolveTask, task_id)
        for k, v in kw.items():
            setattr(t, k, v)
        s.add(t)
        s.commit()


def run_solve_task(task_id: int) -> None:
    with Session(engine) as s:
        t = s.get(SolveTask, task_id)
        if not t:
            return
        t.status = "running"
        t.started_at = datetime.utcnow()
        t.progress = 10
        s.add(t)
        s.commit()
        plan = s.get(MenuPlan, t.plan_id) if t.plan_id else None
        params = t.params or {}

    try:
        with Session(engine) as s:
            resident, dishes, rules = load_context(s, t.resident_id)
            plan = s.get(MenuPlan, t.plan_id)
            if not plan:
                raise RuntimeError("方案不存在")
            existing = s.exec(
                select(MenuItem).where(MenuItem.plan_id == plan.id)
            ).all()
            allowed = None
            if t.task_type == "resolve" and params.get("day_index") is not None:
                allowed = {int(params["day_index"])}
            _update(task_id, progress=40, message="CP-SAT 求解中……")
            result = run_solve(
                s, plan, resident, dishes, rules,
                time_limit_sec=int(params.get("time_limit_sec", 20)),
                allowed_days=allowed, existing_items=existing,
                weights=params.get("weights"))
            if result["status"] != "success":
                _update(task_id, status="failed", progress=100,
                        finished_at=datetime.utcnow(), error=result["error"],
                        message="求解失败")
                return
            payload = {"plan_id": plan.id, "plan_version": plan.version,
                       "item_count": len(result["items"]),
                       "score": result["score"], "warnings": result["warnings"]}
        _update(task_id, status="success", progress=100,
                finished_at=datetime.utcnow(), result=payload,
                message="求解完成")
    except Exception as e:  # noqa: BLE001
        _update(task_id, status="failed", progress=100,
                finished_at=datetime.utcnow(), error=str(e), message="求解异常")
