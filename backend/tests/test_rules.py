"""规则引擎测试：过敏/宗教/IDDSI/慢病/药食/优先级。"""
from app.core.rules_engine import (
    RuleEngine, PersonContext, DishContext, Violation)


def person(**kw):
    defaults = dict(elder_id=1, name="老人", allergies=set(), iddsi_level=7,
                    religion="none", diseases=set(), medications=set(),
                    dislike_keywords=[])
    defaults.update(kw)
    return PersonContext(**defaults)


def dish(**kw):
    defaults = dict(dish_id=1, name="测试菜", allergens=set(), tags=set(),
                    iddsi_level=7, ingredient_names=[])
    defaults.update(kw)
    return DishContext(**defaults)


def test_allergen_forbid():
    eng = RuleEngine()
    p = person(allergies={"peanut"})
    v = eng.evaluate_dish(p, dish(allergens={"peanut", "soy"}))
    assert any(x.level == "forbid" and x.rule_type == "allergen" for x in v)


def test_iddsi_hard_vs_soft():
    eng = RuleEngine()
    p = person(iddsi_level=5)
    hard = eng.evaluate_dish(p, dish(iddsi_level=7))
    assert any(x.level == "forbid" and x.rule_type == "iddsi" for x in hard)
    soft = eng.evaluate_dish(p, dish(iddsi_level=4))
    assert not any(x.level == "forbid" for x in soft)


def test_religion_islam_pork_and_alcohol():
    eng = RuleEngine()
    p = person(religion="islam")
    v = eng.evaluate_dish(p, dish(tags={"pork"}))
    assert any(x.level == "forbid" for x in v)
    v2 = eng.evaluate_dish(p, dish(tags={"beef"}))
    assert not any(x.level == "forbid" for x in v2)


def test_drug_warfarin_is_warn_not_forbid():
    eng = RuleEngine()
    p = person(medications={"warfarin"})
    v = eng.evaluate_dish(p, dish(tags={"vitamin_k_rich"}))
    assert v and v[0].level == "warn"


def test_drug_mao_forbid():
    eng = RuleEngine()
    p = person(medications={"mao_i"})
    v = eng.evaluate_dish(p, dish(tags={"tyramine"}))
    assert any(x.level == "forbid" for x in v)


def test_json_chronic_rule():
    rules = [{
        "code": "T1", "name": "高血压限高钠", "rule_type": "chronic",
        "subject": "dish", "action": "forbid", "priority": 800, "is_active": True,
        "condition": {"disease": "hypertension", "tags_any": ["high_sodium"]},
        "message": "限钠",
    }]
    eng = RuleEngine(rules)
    p = person(diseases={"hypertension"})
    v = eng.evaluate_dish(p, dish(tags={"high_sodium"}))
    assert any(x.rule_code == "T1" and x.level == "forbid" for x in v)
    # 无慢病不命中
    v2 = eng.evaluate_dish(person(), dish(tags={"high_sodium"}))
    assert not any(x.rule_code == "T1" for x in v2)


def test_priority_ordering_and_dedup():
    rules = [
        {"code": "A", "name": "低优先", "rule_type": "chronic", "action": "warn",
         "priority": 10, "is_active": True,
         "condition": {"disease": "gout", "tags_any": ["x"]}, "message": ""},
        {"code": "A", "name": "高优先", "rule_type": "chronic", "action": "forbid",
         "priority": 900, "is_active": True,
         "condition": {"disease": "gout", "tags_any": ["x"]}, "message": ""},
    ]
    eng = RuleEngine(rules)
    v = eng.evaluate_dish(person(diseases={"gout"}), dish(tags={"x"}))
    codes = {x.rule_code: x for x in v}
    assert codes["A"].priority == 900
    assert list(v)[0].priority >= list(v)[-1].priority


def test_dislike_is_warn():
    eng = RuleEngine()
    p = person(dislike_keywords=["香菜"])
    v = eng.evaluate_dish(p, dish(name="香菜拌豆腐"))
    assert any(x.rule_type == "dislike" and x.level == "warn" for x in v)
