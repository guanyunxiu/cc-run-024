"""老人档案与营养目标路由。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user, require_roles
from ..models import Resident, User
from ..nutrition import targets_snapshot
from ..rules import explain_rules
from ..models import Rule
from ..schemas import ResidentIn, ResidentUpdate

router = APIRouter(prefix="/api/residents", tags=["老人档案"])

CHRONIC_OPTIONS = [
    ("hypertension", "高血压"), ("diabetes", "糖尿病"), ("ckd", "慢性肾病"),
    ("hyperlipidemia", "高脂血症"), ("gout", "痛风"),
]
ALLERGEN_OPTIONS = [
    ("egg", "鸡蛋"), ("milk", "牛奶"), ("fish", "鱼类"), ("shrimp", "虾蟹"),
    ("peanut", "花生"), ("soy", "大豆"), ("gluten", "麸质"),
    ("sesame", "芝麻"), ("tree_nut", "坚果"),
]
ACTIVITY_OPTIONS = [
    ("bedridden", "卧床"), ("sedentary", "久坐"), ("light", "轻度活动"),
    ("moderate", "中度活动"), ("active", "较活跃"),
]
RELIGION_OPTIONS = [
    ("none", "无"), ("islam", "清真/伊斯兰"), ("buddhist", "佛教素食"),
    ("vegetarian", "素食主义"),
]
MEDICATION_OPTIONS = [("warfarin", "华法林")]


@router.get("/options")
def options(user: User = Depends(get_current_user)):
    return {"chronic": CHRONIC_OPTIONS, "allergens": ALLERGEN_OPTIONS,
            "activity": ACTIVITY_OPTIONS, "religion": RELIGION_OPTIONS,
            "medications": MEDICATION_OPTIONS, "iddsi": list(range(8))}


@router.get("/targets/preview")
def preview_targets(body: ResidentIn, user: User = Depends(get_current_user),
                    session: Session = Depends(get_session)):
    """表单填写时实时预览营养目标。"""
    r = Resident.model_validate(body.model_dump())
    return targets_snapshot(r)


@router.get("")
def list_residents(kw: str = "", session: Session = Depends(get_session),
                   user: User = Depends(get_current_user)):
    stmt = select(Resident).where(Resident.is_active == True)  # noqa: E712
    if kw:
        stmt = stmt.where(Resident.name.contains(kw))
    rows = session.exec(stmt.order_by(Resident.id)).all()
    return [{
        "id": r.id, "name": r.name, "gender": r.gender, "age": r.age,
        "swallowing_level": r.swallowing_level,
        "chronic_conditions": r.chronic_conditions,
        "allergies": r.allergies, "religion": r.religion,
        "activity_level": r.activity_level, "weight_kg": r.weight_kg,
        "bmi": (r.targets or {}).get("bmi"),
        "tdee": (r.targets or {}).get("tdee"),
        "version": r.version,
    } for r in rows]


@router.get("/{resident_id}")
def get_resident(resident_id: int, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    r = session.get(Resident, resident_id)
    if not r:
        raise HTTPException(404, "老人不存在")
    rules = session.exec(select(Rule)).all()
    data = r.model_dump()
    data["applicable_rules"] = explain_rules(rules, r)
    return data


@router.post("", status_code=201)
def create_resident(body: ResidentIn, session: Session = Depends(get_session),
                    user: User = Depends(require_roles("admin", "nutritionist"))):
    r = Resident.model_validate(body.model_dump())
    session.add(r)
    session.flush()
    r.targets = targets_snapshot(r)
    session.add(r)
    audit(session, user, "create", "resident", r.id, {"name": r.name})
    session.commit()
    session.refresh(r)
    return {"id": r.id}


@router.put("/{resident_id}")
def update_resident(resident_id: int, body: ResidentUpdate,
                    session: Session = Depends(get_session),
                    user: User = Depends(require_roles("admin", "nutritionist"))):
    r = session.get(Resident, resident_id)
    if not r:
        raise HTTPException(404, "老人不存在")
    if body.version != r.version:
        raise HTTPException(409, "档案已被他人修改，请刷新后重试（乐观锁冲突）")
    for k, v in body.model_dump(exclude={"version"}).items():
        setattr(r, k, v)
    r.targets = targets_snapshot(r)
    r.version += 1
    r.updated_at = datetime.utcnow()
    session.add(r)
    audit(session, user, "update", "resident", r.id,
          {"conditions": r.chronic_conditions})
    session.commit()
    return {"id": r.id, "version": r.version, "targets": r.targets}


@router.delete("/{resident_id}")
def deactivate_resident(resident_id: int, session: Session = Depends(get_session),
                        user: User = Depends(require_roles("admin"))):
    r = session.get(Resident, resident_id)
    if not r:
        raise HTTPException(404, "老人不存在")
    r.is_active = False
    session.add(r)
    audit(session, user, "delete", "resident", r.id)
    session.commit()
    return {"ok": True}
