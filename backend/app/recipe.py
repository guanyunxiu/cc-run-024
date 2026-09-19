"""食材 → 成品菜品的营养与成本换算。

每份菜品营养 = Σ 食材投料毛重 × 可食部% × 每100g可食部营养 ÷ 100。
烹饪损失只影响成品重量（出成率），不计入营养/成本（米吸水等）。
成本 = Σ 毛重(kg) × 单价(元/kg)。标签/过敏原由配方自动并集。
"""
from sqlmodel import Session, select

from .models import Dish, DishIngredient, Ingredient

NUTRIENT_COLS = [
    "energy_kcal", "protein_g", "fat_g", "carb_g", "sodium_mg",
    "potassium_mg", "phosphorus_mg", "fiber_g", "calcium_mg", "vitamin_k_ug",
]

# 允许从食材自动传播到菜品的标签（宗教/慢病的食材属性）。
# 刻意排除 fried/high_sodium/high_sugar —— 这些取决于用量与烹饪方式，
# 应由菜品显式标注（否则任何菜只要用油/盐都会被误判）。
PROPAGATE_TAGS = {
    "pork", "alcohol", "lard", "meat", "poultry", "fish", "seafood",
    "egg", "milk", "organ_meat", "fatty_meat",
    "high_potassium", "high_phosphorus", "high_vitamin_k",
}


def compute_from_recipe(session: Session, recipe: list[dict]) -> dict:
    out = {k: 0.0 for k in NUTRIENT_COLS}
    out["cost"] = 0.0
    out["cooked_weight_g"] = 0.0
    tags, allergens = set(), set()

    for item in recipe:
        ing = session.get(Ingredient, item["ingredient_id"])
        if not ing:
            continue
        gross = float(item.get("gross_g", 0))
        edible = gross * ing.edible_pct / 100.0
        loss = float(item.get("cooking_loss_pct", 0))
        out["cooked_weight_g"] += edible * (1 - loss / 100.0)
        for k in NUTRIENT_COLS:
            out[k] += getattr(ing, k, 0.0) * edible / 100.0
        out["cost"] += gross / 1000.0 * ing.unit_cost
        tags.update(ing.tags or [])
        allergens.update(ing.allergens or [])

    return {
        "nutrition": {k: round(out[k], 2) for k in NUTRIENT_COLS},
        "cost": round(out["cost"], 2),
        "cooked_weight_g": round(out["cooked_weight_g"], 1),
        "tags": sorted(tags),
        "allergens": sorted(allergens),
    }


def recompute_dish(session: Session, dish: Dish, recipe_items: list[DishIngredient] | None = None) -> dict:
    """用配方重算菜品营养/成本并回写。返回换算明细。"""
    if recipe_items is None:
        recipe_items = session.exec(
            select(DishIngredient).where(DishIngredient.dish_id == dish.id)
        ).all()
    payload = [
        {"ingredient_id": ri.ingredient_id, "gross_g": ri.gross_g,
         "cooking_loss_pct": ri.cooking_loss_pct}
        for ri in recipe_items
    ]
    if not payload:
        return {}
    res = compute_from_recipe(session, payload)
    for k, v in res["nutrition"].items():
        setattr(dish, k, v)
    dish.cost = res["cost"]
    # 只传播白名单标签（食材属性），其余标签以菜品显式标注为准
    prop_tags = {t for t in res["tags"] if t in PROPAGATE_TAGS}
    dish.tags = sorted(set(dish.tags or []) | prop_tags)
    dish.allergens = sorted(set(dish.allergens or []) | set(res["allergens"]))
    return res
