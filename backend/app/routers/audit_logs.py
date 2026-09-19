"""操作审计日志路由。"""
from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..deps import get_current_user, require_roles
from ..models import AuditLog, User

router = APIRouter(prefix="/api/audit-logs", tags=["审计日志"])

ACTION_LABELS = {
    "create": "新建", "update": "修改", "delete": "删除", "solve": "求解",
    "resolve": "局部重算", "publish": "发布", "rollback": "回滚",
    "archive": "归档", "export": "导出", "login": "登录",
}
ENTITY_LABELS = {
    "resident": "老人档案", "dish": "菜品", "ingredient": "食材",
    "rule": "禁忌规则", "plan": "配餐方案", "plan_item": "排餐调整",
    "plan_pdf": "PDF报告", "plan_excel": "Excel报告", "user": "用户",
}


@router.get("")
def list_logs(action: str = "", entity: str = "", page: int = 1, size: int = 30,
              session: Session = Depends(get_session),
              user: User = Depends(get_current_user)):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if entity:
        stmt = stmt.where(AuditLog.entity == entity)
    all_rows = session.exec(stmt.order_by(AuditLog.id.desc())).all()
    total = len(all_rows)
    rows = all_rows[(page - 1) * size: page * size]
    return {"total": total, "page": page, "size": size,
            "action_labels": ACTION_LABELS, "entity_labels": ENTITY_LABELS,
            "items": [r.model_dump() for r in rows]}


@router.get("/labels")
def labels(user: User = Depends(get_current_user)):
    return {"actions": ACTION_LABELS, "entities": ENTITY_LABELS}
