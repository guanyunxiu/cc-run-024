"""禁忌规则路由（JSON 规则表 + Python 校验函数）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user, require_roles
from ..models import Resident, Rule, User
from ..rules import explain_rules
from ..schemas import RuleIn

router = APIRouter(prefix="/api/rules", tags=["禁忌规则"])

TYPE_LABELS = {
    "allergen": "过敏原", "chronic": "慢病禁忌", "medication": "药物交互",
    "iddsi": "吞咽 IDDSI", "religion": "宗教禁忌",
}


@router.get("")
def list_rules(rule_type: str = "", session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    stmt = select(Rule)
    if rule_type:
        stmt = stmt.where(Rule.rule_type == rule_type)
    return session.exec(stmt.order_by(Rule.priority, Rule.id)).all()


@router.get("/types")
def rule_types(user: User = Depends(get_current_user)):
    return {"types": list(TYPE_LABELS.items())}


@router.get("/applicable/{resident_id}")
def applicable(resident_id: int, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    r = session.get(Resident, resident_id)
    if not r:
        raise HTTPException(404, "老人不存在")
    rules = session.exec(select(Rule)).all()
    return explain_rules(rules, r)


@router.post("", status_code=201)
def create_rule(body: RuleIn, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin", "nutritionist"))):
    if session.exec(select(Rule).where(Rule.code == body.code)).first():
        raise HTTPException(400, "规则编码已存在")
    obj = Rule.model_validate(body.model_dump())
    session.add(obj)
    audit(session, user, "create", "rule", 0, {"code": obj.code})
    session.commit()
    session.refresh(obj)
    return {"id": obj.id}


@router.put("/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin", "nutritionist"))):
    obj = session.get(Rule, rule_id)
    if not obj:
        raise HTTPException(404, "规则不存在")
    for k, v in body.model_dump().items():
        setattr(obj, k, v)
    session.add(obj)
    audit(session, user, "update", "rule", rule_id,
          {"code": obj.code, "version": obj.version})
    session.commit()
    return {"ok": True}


@router.delete("/{rule_id}")
def delete_rule(rule_id: int, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin"))):
    obj = session.get(Rule, rule_id)
    if not obj:
        raise HTTPException(404, "规则不存在")
    session.delete(obj)
    audit(session, user, "delete", "rule", rule_id, {"code": obj.code})
    session.commit()
    return {"ok": True}
