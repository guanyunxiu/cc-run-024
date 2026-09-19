"""审计日志。"""
import json
from sqlmodel import Session

from ..models import AuditLog


def log(session: Session, username: str, action: str,
        entity_type: str = "", entity_id: str | int = "",
        detail: dict | None = None, rule_version: str = "") -> AuditLog:
    row = AuditLog(
        username=username, action=action, entity_type=entity_type,
        entity_id=str(entity_id), detail_json=json.dumps(detail or {}, ensure_ascii=False),
        rule_version=rule_version,
    )
    session.add(row)
    session.commit()
    return row
