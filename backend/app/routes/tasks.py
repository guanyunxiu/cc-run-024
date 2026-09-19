"""任务状态轮询 + 操作日志查询。"""
import json
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, Task, AuditLog
from .deps import get_current_user

router = APIRouter(prefix="/api", tags=["任务与日志"])


@router.get("/tasks/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session),
             _: User = Depends(get_current_user)):
    t = session.get(Task, task_id)
    d = t.model_dump() if t else None
    if d:
        d["result"] = json.loads(t.result_json or "{}")
        d["params"] = json.loads(t.params_json or "{}")
    return d


@router.get("/tasks")
def list_tasks(limit: int = 30, session: Session = Depends(get_session),
               _: User = Depends(get_current_user)):
    rows = session.exec(select(Task).order_by(Task.id.desc()).limit(limit)).all()
    out = []
    for t in rows:
        d = t.model_dump()
        d["result"] = json.loads(t.result_json or "{}")
        out.append(d)
    return out


@router.get("/audit-logs")
def list_audit_logs(limit: int = 100, action: str = "",
                    session: Session = Depends(get_session),
                    _: User = Depends(get_current_user)):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = select(AuditLog).where(AuditLog.action.contains(action)).order_by(
            AuditLog.id.desc()).limit(limit)
    rows = session.exec(stmt).all()
    out = []
    for r in rows:
        d = r.model_dump()
        d["detail"] = json.loads(r.detail_json or "{}")
        out.append(d)
    return out
