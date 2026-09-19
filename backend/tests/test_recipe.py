"""配方营养换算测试。"""
import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import Dish, Ingredient
from app.recipe import compute_from_recipe, recompute_dish


@pytest.fixture
def session():
    with Session(engine) as s:
        yield s


def test_rice_recipe_energy(session):
    rice = session.exec(select(Ingredient).where(
        Ingredient.name == "粳米(生)")).first()
    # 100g 生米（吸水不出营养损失）→ 约 346 kcal
    res = compute_from_recipe(session, [
        {"ingredient_id": rice.id, "gross_g": 100, "cooking_loss_pct": -130}])
    assert abs(res["nutrition"]["energy_kcal"] - 346) < 1
    # 吸水后成品重量约 230g
    assert 225 < res["cooked_weight_g"] < 235


def test_edible_portion(session):
    fish = session.exec(select(Ingredient).where(
        Ingredient.name == "鲈鱼")).first()
    # 毛重 140g × 可食部 58%
    res = compute_from_recipe(session, [
        {"ingredient_id": fish.id, "gross_g": 140, "cooking_loss_pct": 8}])
    edible = 140 * 0.58
    expected_kcal = 105 * edible / 100
    assert abs(res["nutrition"]["energy_kcal"] - round(expected_kcal, 2)) < 0.5
    assert abs(res["cooked_weight_g"] - edible * 0.92) < 0.5


def test_cost_and_allergen_aggregation(session):
    shrimp = session.exec(select(Ingredient).where(
        Ingredient.name == "虾仁")).first()
    egg = session.exec(select(Ingredient).where(
        Ingredient.name == "鸡蛋")).first()
    res = compute_from_recipe(session, [
        {"ingredient_id": shrimp.id, "gross_g": 70},
        {"ingredient_id": egg.id, "gross_g": 80}])
    assert abs(res["cost"] - (0.07 * 70 + 0.012 * 80)) < 0.01
    assert set(res["allergens"]) == {"shrimp", "egg"}
    # egg 标签从食材传播
    assert "egg" in res["tags"]


def test_seeded_dishes_recomputed(session):
    # 种子菜品全部由配方换算，营养为正
    dishes = session.exec(select(Dish)).all()
    assert len(dishes) >= 50
    for d in dishes[:20]:
        assert d.energy_kcal >= 0
        assert d.cost >= 0


def test_recompute_dish_merges_manual_tags(session):
    from app.models import DishIngredient
    rice = session.exec(select(Ingredient).where(
        Ingredient.name == "粳米(生)")).first()
    d = Dish(name="测试菜", category="staple", iddsi_level=7, tags=["手工标签"])
    session.add(d)
    session.flush()
    session.add(DishIngredient(dish_id=d.id, ingredient_id=rice.id,
                               gross_g=100, cooking_loss_pct=-130))
    session.flush()
    recompute_dish(session, d)
    assert "手工标签" in d.tags
    assert d.energy_kcal > 300
    session.rollback()
