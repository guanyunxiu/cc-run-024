"""规则引擎测试：过敏/IDDSI/宗教/慢病/药物交互、优先级。"""
from types import SimpleNamespace

from app.models import Resident
from app.rules import DEFAULT_RULES, evaluate, evaluate_dish
from app.seed import INGREDIENTS  # noqa: F401  (保证 app.seed 可导入)


def mk_rule(code, rtype, severity="hard", priority=10, **params):
    return SimpleNamespace(
        id=1, code=code, name=code, rule_type=rtype, severity=severity,
        priority=priority, version="1.0.0", active=True, params=params,
        rationale="测试规则")


def mk_dish(**kw):
    base = dict(id=1, name="菜", tags=[], allergens=[], iddsi_level=7,
                sodium_mg=100, potassium_mg=100, phosphorus_mg=50,
                vitamin_k_ug=0)
    base.update(kw)
    return SimpleNamespace(**base)


def mk_res(**kw):
    base = dict(allergies=[], swallowing_level=7, religion="none",
                medications=[], chronic_conditions=[])
    base.update(kw)
    return SimpleNamespace(**base)


def test_allergen_blocks_dish():
    rule = mk_rule("A1", "allergen")
    r = mk_res(allergies=["egg"])
    v = evaluate(rule, mk_dish(allergens=["egg", "milk"]), r)
    assert v is not None and "鸡蛋" in v.message


def test_iddsi_level():
    rule = mk_rule("I1", "iddsi")
    r = mk_res(swallowing_level=5)
    assert evaluate(rule, mk_dish(iddsi_level=7), r) is not None
    assert evaluate(rule, mk_dish(iddsi_level=5), r) is None
    assert evaluate(rule, mk_dish(iddsi_level=4), r) is None


def test_religion_islam_pork():
    rule = mk_rule("R1", "religion")
    r = mk_res(religion="islam")
    v = evaluate(rule, mk_dish(tags=["pork"]), r)
    assert v is not None and "清真" in v.message
    assert evaluate(rule, mk_dish(tags=["vegetable"]), r) is None


def test_chronic_tag_and_nutrient():
    rule = mk_rule("H1", "chronic",
                   condition="hypertension",
                   nutrient_max={"sodium_mg": 500})
    r = mk_res(chronic_conditions=["hypertension"])
    assert evaluate(rule, mk_dish(sodium_mg=600), r) is not None
    assert evaluate(rule, mk_dish(sodium_mg=400), r) is None
    r2 = mk_res(chronic_conditions=[])
    assert evaluate(rule, mk_dish(sodium_mg=900), r2) is None  # 规则不生效


def test_medication_warfarin_soft():
    rule = mk_rule("M1", "medication", severity="soft",
                   medication="warfarin",
                   match={"tags_any": ["high_vitamin_k"]},
                   nutrient_max={"vitamin_k_ug": 400})
    r = mk_res(medications=["warfarin"])
    v = evaluate(rule, mk_dish(tags=["high_vitamin_k"], vitamin_k_ug=500), r)
    assert v is not None and v.severity == "soft"
    r2 = mk_res(medications=[])
    assert evaluate(rule, mk_dish(tags=["high_vitamin_k"], vitamin_k_ug=999), r2) is None


def test_seed_default_rules_all_parse(tmp_path=None):
    # 默认规则表字段完整性
    for r in DEFAULT_RULES:
        assert r["code"] and r["rule_type"] in {
            "allergen", "iddsi", "religion", "chronic", "medication"}
        assert r["severity"] in {"hard", "soft"}
        assert isinstance(r["priority"], int)


def test_evaluate_dish_hard_soft_split():
    rules = [
        mk_rule("H", "allergen", severity="hard", priority=1),
        mk_rule("S", "medication", severity="soft", priority=9,
                medication="warfarin",
                match={"tags_any": ["high_vitamin_k"]}),
    ]
    res = mk_res(allergies=["egg"], medications=["warfarin"])
    dish = mk_dish(allergens=["egg"], tags=["high_vitamin_k"])
    ev = evaluate_dish(dish, res, rules)
    assert ev["eligible"] is False
    assert len(ev["hard"]) == 1 and len(ev["soft"]) == 1
