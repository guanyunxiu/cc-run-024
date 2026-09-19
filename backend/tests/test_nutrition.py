"""营养目标计算与配方换算测试（含 Hypothesis 属性测试）。"""
from datetime import date

from hypothesis import given, strategies as st

from app.core.nutrition import compute_targets, recipe_to_finished, age


def test_basic_energy_within_bmr_band():
    t = compute_targets(
        birth_date=date(1955, 1, 1), gender="male", height_cm=170, weight_kg=70,
        activity_level="light", chronic_diseases=[], nutrition_goal="maintain")
    lo, hi = t.targets["energy_kcal"]
    # 70 岁男性轻活动，能量应在 1500~2600 合理区间
    assert 1500 < lo < hi < 2600
    assert t.targets["protein_g"][0] >= 60


def test_hypertension_tightens_sodium():
    base = compute_targets(
        birth_date=date(1955, 1, 1), gender="male", height_cm=170, weight_kg=70,
        activity_level="light", chronic_diseases=[], nutrition_goal="maintain")
    htn = compute_targets(
        birth_date=date(1955, 1, 1), gender="male", height_cm=170, weight_kg=70,
        activity_level="light", chronic_diseases=["hypertension"],
        nutrition_goal="maintain")
    assert htn.targets["sodium_mg"][1] < base.targets["sodium_mg"][1]
    assert htn.targets["sodium_mg"][1] == 1500


def test_ckd_sarcopenia_conflict_is_compromise_and_explained():
    t = compute_targets(
        birth_date=date(1940, 1, 1), gender="female", height_cm=155, weight_kg=45,
        activity_level="sedentary",
        chronic_diseases=["ckd", "sarcopenia"], nutrition_goal="malnutrition")
    lo, hi = t.targets["protein_g"]
    # 折中：介于 CKD 0.6~0.8 与肌少症 1.2~1.5 之间 → 0.8~1.0
    assert 0.8 * 45 <= lo
    assert hi <= 1.05 * 45
    assert t.conflict_notes  # 冲突必须被解释
    assert t.targets["potassium_mg"][1] <= 2000
    assert t.targets["phosphorus_mg"][1] == 800


def test_manual_override_wins():
    t = compute_targets(
        birth_date=date(1955, 1, 1), gender="male", height_cm=170, weight_kg=70,
        activity_level="light", chronic_diseases=["hypertension"],
        nutrition_goal="maintain",
        target_overrides={"energy_kcal": 2000.0})
    lo, hi = t.targets["energy_kcal"]
    assert abs(lo - 1800) < 1 and abs(hi - 2200) < 1


def test_recipe_aggregation_cost_and_nutrients():
    class Ing:
        def __init__(self, energy, protein, sodium, cost, edible=1.0):
            self.energy_kcal = energy
            self.protein_g = protein
            self.fat_g = self.carbs_g = self.dietary_fiber_g = 0
            self.sodium_mg = sodium
            self.potassium_mg = self.phosphorus_mg = self.calcium_mg = 0
            self.cholesterol_mg = self.sugar_g = self.purine_mg = 0
            self.unit_cost = cost
            self.edible_rate = edible
            self.gi = None
    rice = Ing(350, 7, 2, 0.7)
    rows = [{"ing": rice, "gross_weight_g": 100, "cooking_loss_rate": 0.0}]
    out = recipe_to_finished(250, rows)
    assert abs(out["energy_kcal"] - 350) < 1e-6
    assert abs(out["cost_per_portion"] - 0.7) < 1e-6
    # 烹饪吸水（粥）：成品每100g营养被稀释
    rows2 = [{"ing": rice, "gross_weight_g": 50, "cooking_loss_rate": -1.0}]
    out2 = recipe_to_finished(300, rows2)  # 50g 米吸水到 100g
    assert abs(out2["energy_kcal"] - 350 * 0.5) < 1e-6


@given(weight=st.floats(min_value=35, max_value=120, allow_nan=False,
                        allow_infinity=False))
def test_protein_targets_positive_and_ordered(weight):
    t = compute_targets(
        birth_date=date(1950, 6, 1), gender="female", height_cm=160,
        weight_kg=weight, activity_level="sedentary",
        chronic_diseases=[], nutrition_goal="maintain")
    lo, hi = t.targets["protein_g"]
    assert 0 < lo <= hi
    e_lo, e_hi = t.targets["energy_kcal"]
    assert 0 < e_lo <= e_hi


def test_age_calc():
    assert age(date(1940, 12, 31), date(2026, 9, 19)) == 85
    assert age(date(1940, 9, 20), date(2026, 9, 19)) == 85  # 生日未到
    assert age(date(1940, 9, 19), date(2026, 9, 19)) == 86
