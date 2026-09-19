"""营养目标计算测试（含多病共存冲突、Hypothesis 属性测试）。"""
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.models import Resident
from app.nutrition import compute_targets

CONDS = ["hypertension", "diabetes", "ckd", "hyperlipidemia", "gout"]


def make_resident(**kw):
    base = dict(name="测试", gender="female", age=82, height_cm=156,
                weight_kg=52, activity_level="light", swallowing_level=7)
    base.update(kw)
    return Resident(**base)


def test_basic_energy_range():
    r = make_resident()
    res = compute_targets(r)
    assert 1200 <= res.tdee <= 3000
    e = res.targets["energy_kcal"]
    assert e["min"] <= res.tdee <= e["max"]


def test_ckd_protein_compromise_conflict():
    r = make_resident(age=85, chronic_conditions=["ckd", "diabetes"])
    res = compute_targets(r)
    # 85 岁高龄 + 糖尿病原本高蛋白，合并 CKD 必须产生冲突记录并折衷
    assert any(c["nutrient"] == "protein_g" for c in res.conflicts)
    t = res.targets["protein_g"]["target"]
    # 折衷 0.9 g/kg
    assert abs(t - 0.9 * 52) < 1.1


def test_ckd_sodium_potassium_restricted():
    r = make_resident(chronic_conditions=["hypertension", "ckd"])
    res = compute_targets(r)
    assert res.targets["sodium_mg"]["max"] <= 1500
    assert res.targets["potassium_mg"]["max"] <= 2000
    assert res.targets["phosphorus_mg"]["max"] <= 800


def test_manual_override():
    r = make_resident(custom_targets={"protein_g": 100})
    res = compute_targets(r)
    assert res.targets["protein_g"]["target"] == 100
    assert any("手工覆盖" in a for a in res.assumptions)


def test_swallowing_fiber_conflict():
    r = make_resident(chronic_conditions=["diabetes"], swallowing_level=4)
    res = compute_targets(r)
    assert any(c["nutrient"] == "fiber_g" for c in res.conflicts)
    assert res.targets["fiber_g"]["min"] <= 30


@given(
    age=st.integers(min_value=60, max_value=100),
    weight=st.floats(min_value=35, max_value=90, allow_nan=False,
                     allow_infinity=False),
    height=st.floats(min_value=140, max_value=180, allow_nan=False,
                     allow_infinity=False),
    gender=st.sampled_from(["male", "female"]),
)
@settings(max_examples=40)
def test_targets_always_well_formed(age, weight, height, gender):
    r = make_resident(age=age, weight_kg=weight, height_cm=height,
                      gender=gender,
                      chronic_conditions=["hypertension", "diabetes"])
    res = compute_targets(r)
    t = res.targets
    # 所有指标上下界有序、目标非负
    for nut, spec in t.items():
        if spec.get("min") is not None and spec.get("max") is not None:
            assert spec["min"] <= spec["max"]
        assert (spec.get("target") or 0) >= 0
    # 钠始终受控
    assert t["sodium_mg"]["max"] <= 2000
