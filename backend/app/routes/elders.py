"""老人档案路由：含营养目标试算/重算。"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, Elder
from ..schemas import ElderIn, ElderOut
from ..core.nutrition import compute_targets
from ..services import audit
from .deps import get_current_user

router = APIRouter(prefix="/api/elders", tags=["老人档案"])


def _explain(elder: Elder) -> dict:
    try:
        return json.loads(elder.target_explanation or "{}")
    except json.JSONDecodeError:
        return {}


def recalc(session: Session, e: Elder, overrides: dict | None = None) -> None:
    diseases = [x.strip() for x in e.chronic_diseases.split(",") if x.strip()]
    ov = overrides if overrides is not None else json.loads(e.target_overrides or "{}")
    tr = compute_targets(
        birth_date=e.birth_date, gender=e.gender, height_cm=e.height_cm,
        weight_kg=e.weight_kg, activity_level=e.activity_level,
        chronic_diseases=diseases, nutrition_goal=e.nutrition_goal,
        target_overrides=ov)
    e.target_overrides = json.dumps(ov, ensure_ascii=False)
    e.target_explanation = json.dumps(tr.as_dict(), ensure_ascii=False)


@router.get("", response_model=list[ElderOut])
def list_elders(session: Session = Depends(get_session),
                _: User = Depends(get_current_user)):
    return session.exec(select(Elder).order_by(Elder.id)).all()


@router.get("/{elder_id}")
def get_elder(elder_id: int, session: Session = Depends(get_session),
              _: User = Depends(get_current_user)):
    e = session.get(Elder, elder_id)
    if not e:
        raise HTTPException(404, "老人不存在")
    out = e.model_dump()
    out["target"] = _explain(e)
    return out


@router.post("", response_model=ElderOut)
def create_elder(body: ElderIn, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    payload = body.model_dump()
    overrides = payload.pop("target_overrides")
    e = Elder(**payload)
    recalc(session, e, overrides)
    session.add(e)
    session.commit()
    session.refresh(e)
    audit.log(session, user.username, "elder.create", "elder", e.id, {"name": e.name})
    return e


@router.put("/{elder_id}", response_model=ElderOut)
def update_elder(elder_id: int, body: ElderIn,
                 session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    e = session.get(Elder, elder_id)
    if not e:
        raise HTTPException(404, "老人不存在")
    payload = body.model_dump()
    overrides = payload.pop("target_overrides")
    for k, v in payload.items():
        setattr(e, k, v)
    from datetime import datetime
    e.updated_at = datetime.now()
    recalc(session, e, overrides)
    session.add(e)
    session.commit()
    session.refresh(e)
    audit.log(session, user.username, "elder.update", "elder", e.id, {"name": e.name})
    return e


@router.post("/preview-targets")
def preview_targets(body: ElderIn, _: User = Depends(get_current_user)):
    """表单填写过程中实时试算目标，不落库。"""
    diseases = [x.strip() for x in body.chronic_diseases.split(",") if x.strip()]
    tr = compute_targets(
        birth_date=body.birth_date, gender=body.gender,
        height_cm=body.height_cm, weight_kg=body.weight_kg,
        activity_level=body.activity_level, chronic_diseases=diseases,
        nutrition_goal=body.nutrition_goal,
        target_overrides=body.target_overrides or None)
    return tr.as_dict()
