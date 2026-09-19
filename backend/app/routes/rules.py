"""规则版本与规则管理 + 菜品实时冲突校验。"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, Rule, RuleVersion, Dish, Elder
from ..schemas import RuleIn, RuleOut, RuleVersionOut, CheckIn
from ..core.rules_engine import RuleEngine, compile_person, compile_dish
from ..services.foodlib import ingredient_names_for_dishes
from ..services.planner import active_rules
from ..services import audit
from .deps import get_current_user, require_admin

router = APIRouter(prefix="/api/rules", tags=["禁忌规则"])


def _rule_out(r: Rule) -> RuleOut:
    d = r.model_dump()
    d["condition"] = json.loads(r.condition_json or "{}")
    return RuleOut(**d)


@router.get("/versions", response_model=list[RuleVersionOut])
def versions(session: Session = Depends(get_session),
             _: User = Depends(get_current_user)):
    rvs = session.exec(select(RuleVersion).order_by(RuleVersion.id.desc())).all()
    out = []
    for rv in rvs:
        cnt = len(session.exec(select(Rule).where(Rule.version_id == rv.id)).all())
        d = rv.model_dump()
        d["rule_count"] = cnt
        out.append(RuleVersionOut(**d))
    return out


@router.get("/current")
def current_rules(session: Session = Depends(get_session),
                  _: User = Depends(get_current_user)):
    rules, version = active_rules(session)
    return {"version": version, "rules": rules}


@router.post("/versions", response_model=RuleVersionOut)
def create_version(version: str, note: str = "",
                   session: Session = Depends(get_session),
                   user: User = Depends(require_admin)):
    if session.exec(select(RuleVersion).where(RuleVersion.version == version)).first():
        raise HTTPException(400, "版本号已存在")
    rv = RuleVersion(version=version, note=note, status="draft")
    session.add(rv)
    session.commit()
    session.refresh(rv)
    audit.log(session, user.username, "rule.version_create", "rule_version", rv.id)
    return RuleVersionOut(**rv.model_dump(), rule_count=0)


@router.post("/versions/{version_id}/publish", response_model=RuleVersionOut)
def publish_version(version_id: int, session: Session = Depends(get_session),
                    user: User = Depends(require_admin)):
    rv = session.get(RuleVersion, version_id)
    if not rv:
        raise HTTPException(404, "规则版本不存在")
    # 其余已发布转归档
    for old in session.exec(select(RuleVersion).where(RuleVersion.status == "published")).all():
        old.status = "archived"
        session.add(old)
    rv.status = "published"
    rv.published_at = datetime.now()
    session.add(rv)
    session.commit()
    session.refresh(rv)
    audit.log(session, user.username, "rule.version_publish", "rule_version", rv.id)
    cnt = len(session.exec(select(Rule).where(Rule.version_id == rv.id)).all())
    return RuleVersionOut(**rv.model_dump(), rule_count=cnt)


@router.get("/versions/{version_id}/rules", response_model=list[RuleOut])
def list_rules(version_id: int, session: Session = Depends(get_session),
               _: User = Depends(get_current_user)):
    rows = session.exec(
        select(Rule).where(Rule.version_id == version_id).order_by(Rule.priority.desc())
    ).all()
    return [_rule_out(r) for r in rows]


@router.post("/versions/{version_id}/rules", response_model=RuleOut)
def add_rule(version_id: int, body: RuleIn,
             session: Session = Depends(get_session),
             user: User = Depends(require_admin)):
    rv = session.get(RuleVersion, version_id)
    if not rv:
        raise HTTPException(404, "规则版本不存在")
    if rv.status == "published":
        raise HTTPException(400, "已发布版本不可修改，请新建版本")
    r = Rule(version_id=version_id, code=body.code, name=body.name,
             rule_type=body.rule_type, subject=body.subject, action=body.action,
             priority=body.priority, message=body.message, is_active=body.is_active,
             condition_json=json.dumps(body.condition, ensure_ascii=False))
    session.add(r)
    session.commit()
    session.refresh(r)
    audit.log(session, user.username, "rule.create", "rule", r.id, {"code": r.code})
    return _rule_out(r)


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleIn,
                session: Session = Depends(get_session),
                user: User = Depends(require_admin)):
    r = session.get(Rule, rule_id)
    if not r:
        raise HTTPException(404, "规则不存在")
    rv = session.get(RuleVersion, r.version_id)
    if rv.status == "published":
        raise HTTPException(400, "已发布版本不可修改，请新建版本")
    for k in ("code", "name", "rule_type", "subject", "action", "priority",
              "message", "is_active"):
        setattr(r, k, getattr(body, k))
    r.condition_json = json.dumps(body.condition, ensure_ascii=False)
    session.add(r)
    session.commit()
    session.refresh(r)
    audit.log(session, user.username, "rule.update", "rule", r.id)
    return _rule_out(r)


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: int, session: Session = Depends(get_session),
                user: User = Depends(require_admin)):
    r = session.get(Rule, rule_id)
    if not r:
        raise HTTPException(404, "规则不存在")
    rv = session.get(RuleVersion, r.version_id)
    if rv.status == "published":
        raise HTTPException(400, "已发布版本不可删除规则")
    session.delete(r)
    session.commit()
    audit.log(session, user.username, "rule.delete", "rule", rule_id)
    return {"ok": True}


@router.post("/check-dishes")
def check_dishes(body: CheckIn, session: Session = Depends(get_session),
                 _: User = Depends(get_current_user)):
    """手动换菜时实时冲突高亮：返回每个 dish 的 forbid/warn 明细。"""
    elder = session.get(Elder, body.elder_id)
    if not elder:
        raise HTTPException(404, "老人不存在")
    rules, version = active_rules(session)
    engine = RuleEngine(rules)
    person = compile_person(elder)
    ing_map = ingredient_names_for_dishes(session)
    result = {}
    for did in body.dish_ids:
        d = session.get(Dish, did)
        if not d:
            result[str(did)] = {"found": False, "violations": []}
            continue
        dctx = compile_dish(d, ing_map.get(did, []))
        violations = engine.evaluate_dish(person, dctx)
        result[str(did)] = {
            "found": True, "dish_name": d.name, "iddsi_level": d.iddsi_level,
            "forbid": any(v.level == "forbid" for v in violations),
            "violations": [v.to_dict() for v in violations],
        }
    return {"rule_version": version, "results": result}
