"""菜品库路由：维护配方并自动从食材换算营养与成本。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..deps import audit, get_current_user, require_roles
from ..models import Dish, DishIngredient, Resident, Rule, User
from ..recipe import compute_from_recipe
from ..rules import evaluate_dish
from ..schemas import DishIn
from ..solver import NUT_LABELS

router = APIRouter(prefix="/api/dishes", tags=["菜品库"])

CATEGORY_LABELS = {
    "staple": "主食", "entree": "荤菜/主菜", "vegetable": "蔬菜",
    "soup": "汤羹", "egg": "蛋类", "soy": "豆制品", "snack": "加餐",
    "fruit": "水果", "dairy": "奶制品", "pickle": "腌制菜",
}


def _save_recipe(session: Session, dish_id: int, recipe: list[dict]):
    old = session.exec(select(DishIngredient).where(
        DishIngredient.dish_id == dish_id)).all()
    for o in old:
        session.delete(o)
    session.flush()
    for item in recipe:
        session.add(DishIngredient(
            dish_id=dish_id, ingredient_id=item["ingredient_id"],
            gross_g=item.get("gross_g", 0),
            cooking_loss_pct=item.get("cooking_loss_pct", 0),
            note=item.get("note", "")))
    session.flush()


@router.get("/options")
def dish_options(user: User = Depends(get_current_user)):
    return {"categories": list(CATEGORY_LABELS.items()),
            "nut_labels": NUT_LABELS, "iddsi": list(range(8))}


@router.get("")
def list_dishes(kw: str = "", category: str = "", resident_id: int | None = None,
                session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    """resident_id 非空时附带每道菜对该老人的规则校验结果（菜品库页冲突提示）。"""
    stmt = select(Dish)
    if kw:
        stmt = stmt.where(Dish.name.contains(kw))
    if category:
        stmt = stmt.where(Dish.category == category)
    dishes = session.exec(stmt.order_by(Dish.category, Dish.id)).all()
    resident = session.get(Resident, resident_id) if resident_id else None
    rules = session.exec(select(Rule)).all()
    out = []
    for d in dishes:
        row = d.model_dump()
        if resident:
            row["check"] = evaluate_dish(d, resident, rules)
        out.append(row)
    return out


@router.get("/{dish_id}")
def get_dish(dish_id: int, session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    recipe = session.exec(select(DishIngredient).where(
        DishIngredient.dish_id == dish_id)).all()
    data = d.model_dump()
    data["recipe"] = [r.model_dump() for r in recipe]
    return data


@router.post("/recipe-preview")
def recipe_preview(payload: dict, session: Session = Depends(get_session),
                   user: User = Depends(get_current_user)):
    """配方编辑时实时换算营养/成本。"""
    return compute_from_recipe(session, payload.get("recipe", []))


@router.post("", status_code=201)
def create_dish(body: DishIn, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin", "nutritionist"))):
    d = Dish(name=body.name, category=body.category,
             iddsi_level=body.iddsi_level, serving_desc=body.serving_desc,
             satisfaction=body.satisfaction, waste_index=body.waste_index,
             active=body.active, note=body.note, tags=body.tags,
             allergens=body.allergens)
    session.add(d)
    session.flush()
    _save_recipe(session, d.id, [r.model_dump() for r in body.recipe])
    if body.recipe:
        from ..recipe import recompute_dish
        recompute_dish(session, d)
    session.add(d)
    audit(session, user, "create", "dish", d.id, {"name": d.name})
    session.commit()
    session.refresh(d)
    return {"id": d.id}


@router.put("/{dish_id}")
def update_dish(dish_id: int, body: DishIn,
                session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin", "nutritionist"))):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    d.name = body.name
    d.category = body.category
    d.iddsi_level = body.iddsi_level
    d.serving_desc = body.serving_desc
    d.satisfaction = body.satisfaction
    d.waste_index = body.waste_index
    d.active = body.active
    d.note = body.note
    # 手工标签 + 标签以编辑值为准；配方传播标签会在重算时并集
    d.tags = body.tags
    d.allergens = body.allergens
    _save_recipe(session, dish_id, [r.model_dump() for r in body.recipe])
    if body.recipe:
        from ..recipe import recompute_dish
        recompute_dish(session, d)
    session.add(d)
    audit(session, user, "update", "dish", dish_id, {"name": d.name})
    session.commit()
    return {"ok": True}


@router.delete("/{dish_id}")
def delete_dish(dish_id: int, session: Session = Depends(get_session),
                user: User = Depends(require_roles("admin"))):
    d = session.get(Dish, dish_id)
    if not d:
        raise HTTPException(404, "菜品不存在")
    d.active = False
    session.add(d)
    audit(session, user, "delete", "dish", dish_id)
    session.commit()
    return {"ok": True}
