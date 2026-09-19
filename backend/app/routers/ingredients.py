"""食材库路由。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user, require_roles
from ..models import Ingredient, User
from ..schemas import IngredientIn

router = APIRouter(prefix="/api/ingredients", tags=["食材库"])


@router.get("")
def list_ingredients(kw: str = "", category: str = "",
                     session: Session = Depends(get_session),
                     user: User = Depends(get_current_user)):
    stmt = select(Ingredient)
    if kw:
        stmt = stmt.where(Ingredient.name.contains(kw))
    if category:
        stmt = stmt.where(Ingredient.category == category)
    return session.exec(stmt.order_by(Ingredient.category, Ingredient.id)).all()


@router.post("", status_code=201)
def create_ingredient(body: IngredientIn, session: Session = Depends(get_session),
                      user: User = Depends(require_roles("admin", "nutritionist"))):
    obj = Ingredient.model_validate(body.model_dump())
    session.add(obj)
    audit(session, user, "create", "ingredient", 0, {"name": obj.name})
    session.commit()
    session.refresh(obj)
    return {"id": obj.id}


@router.put("/{ing_id}")
def update_ingredient(ing_id: int, body: IngredientIn,
                      session: Session = Depends(get_session),
                      user: User = Depends(require_roles("admin", "nutritionist"))):
    obj = session.get(Ingredient, ing_id)
    if not obj:
        raise HTTPException(404, "食材不存在")
    for k, v in body.model_dump().items():
        setattr(obj, k, v)
    session.add(obj)
    audit(session, user, "update", "ingredient", ing_id)
    session.commit()
    return {"ok": True}


@router.delete("/{ing_id}")
def delete_ingredient(ing_id: int, session: Session = Depends(get_session),
                      user: User = Depends(require_roles("admin"))):
    obj = session.get(Ingredient, ing_id)
    if not obj:
        raise HTTPException(404, "食材不存在")
    session.delete(obj)
    audit(session, user, "delete", "ingredient", ing_id)
    session.commit()
    return {"ok": True}
