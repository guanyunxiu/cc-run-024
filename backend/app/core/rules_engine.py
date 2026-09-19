"""禁忌规则引擎：JSON 规则表 + Python 校验函数。

不引入外部规则引擎。规则从 DB（由 seed_rules.json 灌入）加载，
本模块负责：
  1. 把老人档案 + 菜品/食材事实编译为一次"校验上下文"
  2. 对候选菜品执行全部适用规则，产出 violations（forbid 硬约束 / warn 软警告）
  3. 冲突解释：violation 携带规则 code、名称、优先级、命中字段、建议

Python 校验函数处理 JSON 表达不了的语义（IDDSI 质地比较、药食交互的分级提示等）。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

# 已知过敏原（与食材 allergen_tags 对齐）
KNOWN_ALLERGENS = [
    ("peanut", "花生"), ("seafood", "甲壳类海鲜"), ("fish", "鱼类"),
    ("egg", "蛋类"), ("milk", "乳制品"), ("nuts", "树坚果"),
    ("soy", "大豆"), ("wheat", "小麦/麸质"), ("sesame", "芝麻"),
]
ALLERGEN_LABEL = dict(KNOWN_ALLERGENS)

# 宗教 → 禁止标签
RELIGION_FORBIDDEN = {
    "islam": (["pork", "alcohol", "animal_blood"], "伊斯兰禁忌：猪肉、血液制品、酒精"),
    "vegetarian": (["pork", "beef", "lamb", "poultry", "fish", "seafood", "animal_blood"],
                   "素食：禁忌一切动物性食材（蛋奶素可放宽奶蛋）"),
    "buddhist": (["pork", "beef", "lamb", "poultry", "fish", "seafood", "alcohol", "animal_blood"],
                 "佛教素食：忌荤腥与酒"),
}

# 药食交互（Python 校验，分级）
DRUG_FOOD = {
    "warfarin": {
        "forbid_tags": [],
        "warn_tags": ["vitamin_k_rich"],   # 菠菜、西兰花等 → 稳定摄入而非禁食
        "message": "华法林：维生素K食物需每日稳定，避免骤增骤减",
    },
    "mao_i": {
        "forbid_tags": ["tyramine"],       # 发酵、腌腊、奶酪
        "warn_tags": [],
        "message": "单胺氧化酶抑制剂：禁食高酪胺食物（腌腊、发酵、陈年奶酪）",
    },
    "levodopa": {
        "forbid_tags": [],
        "warn_tags": ["high_protein_timing"],
        "message": "左旋多巴：高蛋白饮食宜与服药时间错开，避免蛋白影响吸收",
    },
    "acei": {
        "forbid_tags": ["potassium_supplement"],
        "warn_tags": ["high_potassium"],
        "message": "ACEI/保钾利尿剂：避免高钾补充剂，高钾食物适量",
    },
}


@dataclass
class Violation:
    level: str                 # forbid / warn
    rule_code: str
    rule_name: str
    rule_type: str
    priority: int
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class DishContext:
    """候选菜品事实（编译后）。"""
    dish_id: int
    name: str
    allergens: set[str] = field(default_factory=set)
    tags: set[str] = field(default_factory=set)
    iddsi_level: int = 7
    ingredient_names: list[str] = field(default_factory=list)
    dish_type: str = ""


@dataclass
class PersonContext:
    elder_id: int
    name: str
    allergies: set[str]
    iddsi_level: int
    religion: str
    diseases: set[str]
    medications: set[str]
    dislike_keywords: list[str]


class RuleEngine:
    def __init__(self, rules: list[dict] | None = None):
        # rules: DB Rule 行转 dict（含 condition）
        self.rules: list[dict] = rules or []

    # ---------- 主入口 ----------
    def evaluate_dish(self, person: PersonContext, dish: DishContext
                      ) -> list[Violation]:
        viol: list[Violation] = []
        viol += self._check_allergens(person, dish)
        viol += self._check_religion(person, dish)
        viol += self._check_iddsi(person, dish)
        viol += self._check_drug_food(person, dish)
        viol += self._check_dislikes(person, dish)
        viol += self._check_json_rules(person, dish)
        # 去重（同 code 同菜只留最高优先级），并按优先级排序
        best: dict[str, Violation] = {}
        for v in viol:
            k = v.rule_code
            if k not in best or v.priority > best[k].priority:
                best[k] = v
        ordered = sorted(best.values(), key=lambda v: -v.priority)
        return ordered

    @staticmethod
    def has_forbid(violations: list[Violation]) -> bool:
        return any(v.level == "forbid" for v in violations)

    # ---------- Python 原生校验 ----------
    def _check_allergens(self, p: PersonContext, d: DishContext) -> list[Violation]:
        out = []
        hit = p.allergies & d.allergens
        for a in hit:
            label = ALLERGEN_LABEL.get(a, a)
            out.append(Violation(
                level="forbid", rule_code=f"PY-ALLERGEN-{a}",
                rule_name=f"过敏原：{label}", rule_type="allergen", priority=1000,
                message=f"{p.name} 对「{label}」过敏，菜品「{d.name}」含该成分",
                suggestion=f"移除含{label}的菜品，替换为同质地同营养菜品"))
        return out

    def _check_religion(self, p: PersonContext, d: DishContext) -> list[Violation]:
        out = []
        if p.religion in RELIGION_FORBIDDEN:
            tags, reason = RELIGION_FORBIDDEN[p.religion]
            hit = set(tags) & d.tags
            for tag in hit:
                out.append(Violation(
                    level="forbid", rule_code=f"PY-RELIGION-{p.religion}-{tag}",
                    rule_name=reason.split("：")[0], rule_type="religion", priority=950,
                    message=f"{reason}；菜品「{d.name}」命中 {tag}",
                    suggestion="替换为清真/素食同营养菜品"))
        return out

    def _check_iddsi(self, p: PersonContext, d: DishContext) -> list[Violation]:
        # 菜品质地等级 > 老人可接受等级 → 老人吃不动（如 7普通食 对 5碎软食）
        if d.iddsi_level > p.iddsi_level:
            gap = d.iddsi_level - p.iddsi_level
            return [Violation(
                level="forbid", rule_code=f"PY-IDDSI-{d.iddsi_level}-{p.iddsi_level}",
                rule_name="吞咽 IDDSI 质地不符", rule_type="iddsi", priority=980,
                message=(f"{p.name} 的吞咽等级为 {p.iddsi_level} 级，"
                         f"菜品「{d.name}」为 {d.iddsi_level} 级，质地偏硬/偏粗（差 {gap} 级），"
                         f"存在误吸风险"),
                suggestion=f"替换为 ≤{p.iddsi_level} 级菜品，或后厨做切碎/制泥等质地改造")]
        # 低一档软提示（过度流质化影响食欲/营养密度）
        if p.iddsi_level - d.iddsi_level >= 3 and p.iddsi_level >= 5:
            return [Violation(
                level="warn", rule_code="PY-IDDSI-OVER",
                rule_name="质地过度改造", rule_type="iddsi", priority=100,
                message=f"菜品「{d.name}」质地远低于老人能力，可能影响饱腹感与进食满意度",
                suggestion="可选择更接近老人吞咽等级的菜品")]
        return []

    def _check_drug_food(self, p: PersonContext, d: DishContext) -> list[Violation]:
        out = []
        for drug in p.medications:
            cfg = DRUG_FOOD.get(drug)
            if not cfg:
                continue
            for tag in set(cfg["forbid_tags"]) & d.tags:
                out.append(Violation(
                    level="forbid", rule_code=f"PY-DRUG-{drug}-{tag}",
                    rule_name=f"药食交互：{drug}", rule_type="drug_food",
                    priority=900, message=cfg["message"] + f"；命中「{d.name}」",
                    suggestion="更换菜品或遵医嘱调整服药安排"))
            for tag in set(cfg["warn_tags"]) & d.tags:
                out.append(Violation(
                    level="warn", rule_code=f"PY-DRUG-{drug}-{tag}",
                    rule_name=f"药食交互（注意）：{drug}", rule_type="drug_food",
                    priority=200, message=cfg["message"] + f"；命中「{d.name}」",
                    suggestion="保持每日摄入量稳定并记录"))
        return out

    def _check_dislikes(self, p: PersonContext, d: DishContext) -> list[Violation]:
        out = []
        haystack = d.name + " " + " ".join(d.ingredient_names)
        for kw in p.dislike_keywords:
            if kw and kw in haystack:
                out.append(Violation(
                    level="warn", rule_code=f"PY-DISLIKE-{kw}",
                    rule_name=f"个人忌口：{kw}", rule_type="dislike", priority=150,
                    message=f"{p.name} 忌口「{kw}」，菜品「{d.name}」可能含此食材",
                    suggestion="优先替换；长期忌口需评估营养替代"))
        return out

    # ---------- JSON 规则表校验（慢病禁忌等）----------
    def _check_json_rules(self, p: PersonContext, d: DishContext) -> list[Violation]:
        out = []
        for r in self.rules:
            if not r.get("is_active", True):
                continue
            cond = r.get("condition", {})
            rtype = r["rule_type"]
            applies = False
            if rtype == "chronic":
                applies = cond.get("disease") in p.diseases
            elif rtype == "allergen":
                applies = cond.get("allergen") in p.allergies
            elif rtype == "religion":
                applies = cond.get("religion") == p.religion
            elif rtype == "drug_food":
                applies = cond.get("drug") in p.medications
            elif rtype == "iddsi":
                applies = True
            if not applies:
                continue
            # 命中判定
            tags_any = set(cond.get("tags_any", []))
            tags_all = cond.get("tags_all", [])
            field_name = cond.get("field")          # 如 sodium_mg
            op = cond.get("op")                      # gt / lt
            value = cond.get("value")
            hit = bool(tags_any & d.tags) if tags_any else True
            if tags_all and not set(tags_all).issubset(d.tags):
                hit = False
            # 数值型规则需要菜品营养快照（放在 tags 标记更简单，这里支持 field）
            if hit and field_name:
                dish_value = getattr(d, "_nutrients", {}) or {}
                dv = dish_value.get(field_name)
                if dv is None:
                    hit = False
                elif op == "gt" and not dv > value:
                    hit = False
                elif op == "lt" and not dv < value:
                    hit = False
            if not hit:
                continue
            out.append(Violation(
                level=r["action"], rule_code=r["code"],
                rule_name=r["name"], rule_type=rtype,
                priority=r["priority"],
                message=f"{r['name']}：{r.get('message', '')}；命中菜品「{d.name}」",
                suggestion=cond.get("suggestion", "")))
        return out


def compile_person(elder, dislike_keywords: list[str] | None = None) -> PersonContext:
    def split(s: str) -> set[str]:
        return {x.strip() for x in (s or "").split(",") if x.strip()}
    return PersonContext(
        elder_id=elder.id, name=elder.name,
        allergies=split(elder.allergies),
        iddsi_level=elder.iddsi_level,
        religion=elder.religion,
        diseases=split(elder.chronic_diseases),
        medications=split(elder.medications),
        dislike_keywords=dislike_keywords or
        [x.strip() for x in (elder.dislikes or "").replace("，", ";").split(";") if x.strip()],
    )


def compile_dish(dish, ingredient_names: list[str] | None = None,
                 nutrients: dict | None = None) -> DishContext:
    def split(s: str) -> set[str]:
        return {x.strip() for x in (s or "").split(",") if x.strip()}
    dc = DishContext(
        dish_id=dish.id, name=dish.name,
        allergens=split(dish.allergen_tags),
        tags=split(dish.tags),
        iddsi_level=dish.iddsi_level,
        ingredient_names=ingredient_names or [],
        dish_type=getattr(dish, "dish_type", ""),
    )
    if nutrients is not None:
        setattr(dc, "_nutrients", nutrients)
    return dc
