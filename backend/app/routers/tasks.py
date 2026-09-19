"""求解任务轮询路由。"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..deps import get_current_user
from ..models import SolveTask, User

router = APIRouter(prefix="/api/tasks", tags=["求解任务"])


@router.get("")
def list_tasks(plan_id: int | None = None, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    stmt = select(SolveTask)
    if plan_id:
        stmt = stmt.where(SolveTask.plan_id == plan_id)
    rows = session.exec(stmt.order_by(SolveTask.id.desc()).limit(50)).all()
    return rows


@router.get("/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    t = session.get(SolveTask, task_id)
    if not t:
        from fastapi import HTTPException
        raise HTTPException(404, "任务不存在")
    return t
