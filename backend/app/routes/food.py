"""食材与菜品库路由。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..database import get_session
from ..models import User, Ingredient, Dish
from ..schemas import IngredientIn, IngredientOut, DishIn, DishOut
from ..services.foodlib import refresh_dish_nutrition, replace_recipe, dish_recipe_detail
from ..services import audit
from .deps import get_current_user

router = APIRouter(prefix="/api/food", tags=["菜品营养库"])


# ── 食材 ──
@router.get("/ingredients", response_model=list[IngredientOut])
def list_ingredients(q: str = "", category: str = "",
                     session: Session = Depends(get_session),
                     _: User = Depends(get_current_user)):
    stmt = select(Ingredient).where(Ingredient.is_active == True)  # noqa: E712
    if q:
        stmt = stmt.where(Ingredient.name.contains(q) | Ingredient.code.contains(q))
    if category:
        stmt = stmt.where(Ingredient.category == category)
    return session.exec(stmt.order_by(Ingredient.category, Ingredient.id)).all()


@router.post("/ingredients", response_model=IngredientOut)
def create_ingredient(body: IngredientIn, session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    if session.exec(select(Ingredient).where(Ingredient.code == body.code)).first():
        raise HTTPException(400, f"食材编码 {body.code} 已存在")
    ing = Ingredient(**body.model_dump())
    session.add(ing)
    session.commit()
    session.refresh(ing)
    audit.log(session, user.username, "ingredient.create", "ingredient", ing.id,
              {"name": ing.name})
    return ing


@router.put("/ingredients/{ing_id}", response_model=IngredientOut)
def update_ingredient(ing_id: int, body: IngredientIn,
                      session: Session = Depends(get_session),
                      user: User = Depends(get_current_user)):
    ing = session.get(Ingredient, ing_id)
    if not ing:
        raise HTTPException(404, "食材不存在")
    for k, v in body.model_dump().items():
        setattr(ing, k, v)
    session.add(ing)
    session.commit()
    session.refresh(ing)
    audit.log(session, user.username, "ingredient.update", "ingredient", ing_id)
    return ing


# ── 菜品 ──
def _dish_out(session: Session, d: Dish) -> DishOut:
    data = {c: getattr(d, c) for c in DishOut.model_fields if c != "recipe"}
    data["recipe"] = dish_recipe_detail(session, d.id)
    return DishOut(**data)


@router.get("/dishes", response_model=list[DishOut])
def list_dishes(q: str = "", dish_type: str = "", iddsi_max: int | None = None,
                session: Session = Depends(get_session),
                _: User = Depends(get_current_user)):
    stmt = select(Dish).where(Dish.is_active == True)  # noqa: E712
    if q:
        stmt = stmt.where(Dish.name.contains(q) | Dish.code.contains(q))
    if dish_type:
        stmt = stmt.where(Dish.dish_type == dish_type)
    if iddsi_max is not None:
        stmt = stmt.where(Dish.iddsi_level <= iddsi_max)
    dishes = session.exec(stmt.order_by(Dish.dish_type, Dish.id)).all()
    return [_dish_out(session, d) for d in dishes]


@router.get("/dishes/{dish_id}", response_model=DishOut)
def get_dish(dish_id: int, session: Session = Depends(get_session),
             _: User = Depends(get_current_user)):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    return _dish_out(session, d)


@router.post("/dishes", response_model=DishOut)
def create_dish(body: DishIn, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    if session.exec(select(Dish).where(Dish.code == body.code)).first():
        raise HTTPException(400, f"菜品编码 {body.code} 已存在")
    payload = body.model_dump(exclude={"recipe"})
    d = Dish(**payload)
    session.add(d)
    session.commit()
    session.refresh(d)
    replace_recipe(session, d.id,
                   [r.model_dump() for r in body.recipe])
    refresh_dish_nutrition(session, d)
    session.commit()
    audit.log(session, user.username, "dish.create", "dish", d.id, {"name": d.name})
    return _dish_out(session, d)


@router.put("/dishes/{dish_id}", response_model=DishOut)
def update_dish(dish_id: int, body: DishIn,
                session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    payload = body.model_dump(exclude={"recipe"})
    for k, v in payload.items():
        setattr(d, k, v)
    session.add(d)
    replace_recipe(session, d.id, [r.model_dump() for r in body.recipe])
    refresh_dish_nutrition(session, d)
    session.commit()
    audit.log(session, user.username, "dish.update", "dish", dish_id, {"name": d.name})
    return _dish_out(session, d)


@router.post("/dishes/{dish_id}/recompute", response_model=DishOut)
def recompute_dish(dish_id: int, session: Session = Depends(get_session),
                   user: User = Depends(get_current_user)):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    refresh_dish_nutrition(session, d)
    session.commit()
    return _dish_out(session, d)
