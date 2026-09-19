"""菜品库服务：配方营养/成本聚合、标签继承。"""
import json
from sqlmodel import Session, select

from ..models import Dish, Ingredient, RecipeItem
from ..core.nutrition import recipe_to_finished, NUTRIENTS

# 沿配方传播的"身份/文化/交互"标签（猪肉、酒精、过敏原交互等与含量无关）
IDENTITY_TAGS = {
    "pork", "beef", "lamb", "poultry", "fish", "seafood", "egg", "soy", "milk",
    "alcohol", "animal_blood", "organ_meat", "processed_meat", "preserved",
    "tyramine", "vitamin_k_rich", "high_protein_timing", "potassium_supplement",
    "peanut", "sesame", "nuts",
}
# 质地标签同样传播
TEXTURE_TAGS = {"soft", "liquid"}
# 营养等级标签不传播：按成品每100g营养阈值重新判定（盐、少量油不会把整菜变"高钠食品"）
NUTRIENT_TAG_THRESHOLDS = {
    # tag: (字段, 下限)；>= 下限即打标
    "high_sodium": ("sodium_mg", 600.0),
    "high_fat": ("fat_g", 15.0),
    "high_sugar": ("sugar_g", 12.0),
    "high_purine": ("purine_mg", 150.0),
    "high_cholesterol": ("cholesterol_mg", 150.0),
    "high_potassium": ("potassium_mg", 250.0),
    "low_potassium": ("potassium_mg", 60.0),
    "low_sodium": ("sodium_mg", 80.0),
}


def derive_nutrient_tags(values: dict[str, float], gi: float | None) -> set[str]:
    """按成品每100g营养成分判定营养等级标签。"""
    out = set()
    for tag, (field, threshold) in NUTRIENT_TAG_THRESHOLDS.items():
        if tag.startswith("low_"):
            continue  # 低值标签单独处理，避免与高值互斥冲突
        if values.get(field, 0.0) >= threshold:
            out.add(tag)
    if values.get("sodium_mg", 0.0) <= NUTRIENT_TAG_THRESHOLDS["low_sodium"][1]:
        out.add("low_sodium")
    if values.get("potassium_mg", 0.0) <= NUTRIENT_TAG_THRESHOLDS["low_potassium"][1]:
        out.add("low_potassium")
    if gi is not None and gi >= 70:
        out.add("high_gi")
    return out


def refresh_dish_nutrition(session: Session, dish: Dish,
                           recipe: list[dict] | None = None) -> Dish:
    """根据配方重算成品每100g营养、成本，并聚合过敏原/标签。

    标签策略：
      - 过敏原标签：沿食材传播（任一成分含即标记，最保守）
      - 身份/质地标签：沿食材传播（如 pork、soft）
      - 营养等级标签（高钠/高脂/高嘌呤/高钾…）：按成品营养阈值重新判定，
        避免"加了盐的菜都算高钠食品"这类误伤
    """
    if recipe is None:
        rows_sql = session.exec(
            select(RecipeItem).where(RecipeItem.dish_id == dish.id)
        ).all()
        recipe = [{"ingredient_id": r.ingredient_id,
                   "gross_weight_g": r.gross_weight_g,
                   "cooking_loss_rate": r.cooking_loss_rate} for r in rows_sql]

    rows = []
    allergens, identity_tags = set(), set()
    ing_names = []
    for r in recipe:
        ing = session.get(Ingredient, r["ingredient_id"])
        if not ing:
            continue
        rows.append({"ing": ing, "gross_weight_g": r["gross_weight_g"],
                     "cooking_loss_rate": r.get("cooking_loss_rate", 0.0)})
        if ing.allergen_tags:
            allergens |= {t.strip() for t in ing.allergen_tags.split(",") if t.strip()}
        if ing.tags:
            for t in (x.strip() for x in ing.tags.split(",") if x.strip()):
                if t in IDENTITY_TAGS or t in TEXTURE_TAGS:
                    identity_tags.add(t)
        ing_names.append(ing.name)

    result = recipe_to_finished(dish.portion_g, rows)
    nutrient_values = {n: result[n] for n in NUTRIENTS}
    for n in NUTRIENTS:
        setattr(dish, n, round(result[n], 2))
    # GI 按重量加权
    gi_value = None
    if rows:
        gi_vals = [(r["ing"].gi, r["gross_weight_g"]) for r in rows
                   if r["ing"].gi is not None]
        if gi_vals:
            w = sum(x[1] for x in gi_vals)
            gi_value = round(sum(g * ww for g, ww in gi_vals) / w, 1)
            dish.gi = gi_value
    if dish.portion_cost <= 0:
        dish.portion_cost = round(result["cost_per_portion"], 2)

    derived = derive_nutrient_tags(nutrient_values, gi_value)
    # 保留人工补充标签（从菜品现有标签里提取非自动派生的部分）
    auto_tags = set(NUTRIENT_TAG_THRESHOLDS) | {"high_gi"}
    manual_allergens = {t.strip() for t in (dish.allergen_tags or "").split(",") if t.strip()}
    manual_tags = {t.strip() for t in (dish.tags or "").split(",") if t.strip()}
    manual_tags = {t for t in manual_tags
                   if t not in auto_tags and t not in IDENTITY_TAGS
                   and t not in TEXTURE_TAGS}
    dish.allergen_tags = ",".join(sorted(allergens | manual_allergens))
    dish.tags = ",".join(sorted(identity_tags | derived | manual_tags))
    session.add(dish)
    return dish


def replace_recipe(session: Session, dish_id: int, recipe: list[dict]) -> None:
    old = session.exec(select(RecipeItem).where(RecipeItem.dish_id == dish_id)).all()
    for r in old:
        session.delete(r)
    for r in recipe:
        session.add(RecipeItem(
            dish_id=dish_id, ingredient_id=r["ingredient_id"],
            gross_weight_g=r["gross_weight_g"],
            cooking_loss_rate=r.get("cooking_loss_rate", 0.0)))
    session.commit()


def dish_recipe_detail(session: Session, dish_id: int) -> list[dict]:
    rows = session.exec(select(RecipeItem).where(RecipeItem.dish_id == dish_id)).all()
    out = []
    for r in rows:
        ing = session.get(Ingredient, r.ingredient_id)
        out.append({
            "id": r.id, "ingredient_id": r.ingredient_id,
            "ingredient_name": ing.name if ing else f"#{r.ingredient_id}",
            "gross_weight_g": r.gross_weight_g,
            "cooking_loss_rate": r.cooking_loss_rate,
            "edible_rate": ing.edible_rate if ing else 1.0,
            "unit_cost": ing.unit_cost if ing else 0.0,
        })
    return out


def ingredient_names_for_dishes(session: Session) -> dict[int, list[str]]:
    """一次性加载 菜品→食材名 映射，供规则引擎使用。"""
    mapping: dict[int, list[str]] = {}
    rows = session.exec(select(RecipeItem)).all()
    ids = {r.ingredient_id for r in rows}
    ings = {i.id: i.name for i in session.exec(select(Ingredient)).all() if i.id in ids}
    for r in rows:
        mapping.setdefault(r.dish_id, []).append(ings.get(r.ingredient_id, ""))
    return mapping
