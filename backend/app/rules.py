"""禁忌规则引擎：JSON 规则表 + Python 校验函数。

不引入第三方规则引擎。每条规则是一行 JSON 参数（Rule.params），
由 rule_type 分派到对应的 Python 校验函数。规则带版本、优先级、
严重级别（hard 排除 / soft 扣分）与解释（rationale）。
"""
from dataclasses import dataclass

# ---------------- 规则校验函数 ----------------

RELIGION_FORBIDDEN_TAGS = {
    "islam": ["pork", "alcohol", "lard"],
    "buddhist": ["meat", "poultry", "fish", "seafood", "egg", "alcohol"],
    "vegetarian": ["meat", "poultry", "fish", "seafood", "alcohol"],
}

ALLERGEN_LABELS = {
    "egg": "鸡蛋", "milk": "牛奶/乳制品", "fish": "鱼类", "shrimp": "虾蟹",
    "crab": "蟹", "peanut": "花生", "soy": "大豆", "gluten": "麸质",
    "sesame": "芝麻", "tree_nut": "坚果",
}
RELIGION_LABELS = {
    "islam": "清真(伊斯兰)", "buddhist": "佛教", "vegetarian": "素食主义",
}
TAG_LABELS = {
    "pork": "猪肉", "alcohol": "酒精", "lard": "猪油", "meat": "畜肉",
    "poultry": "禽肉", "fish": "鱼", "seafood": "海鲜", "egg": "蛋",
    "pickle": "腌制品", "fried": "油炸", "high_sugar": "高糖",
    "high_sodium": "高钠", "high_potassium": "高钾", "high_phosphorus": "高磷",
    "high_purine": "高嘌呤", "organ_meat": "动物内脏", "fatty_meat": "肥肉",
    "high_vitamin_k": "高维生素K", "strong_broth": "浓肉汤",
}


@dataclass
class Violation:
    rule_code: str
    rule_name: str
    severity: str
    priority: int
    message: str
    rationale: str

    def as_dict(self) -> dict:
        return {
            "rule_code": self.rule_code, "rule_name": self.rule_name,
            "severity": self.severity, "priority": self.priority,
            "message": self.message, "rationale": self.rationale,
        }


def _match_sets(rule_match: dict, dish) -> list[str]:
    """返回命中的标签/过敏原描述。"""
    hit = []
    tags = set(getattr(dish, "tags", []) or [])
    allergens = set(getattr(dish, "allergens", []) or [])
    for a in rule_match.get("allergens_any", []):
        if a in allergens:
            hit.append(f"含过敏原「{ALLERGEN_LABELS.get(a, a)}」")
    for t in rule_match.get("tags_any", []):
        if t in tags:
            hit.append(f"含「{TAG_LABELS.get(t, t)}」")
    for t in rule_match.get("tags_all", []):
        if t not in tags:
            return []
    if rule_match.get("tags_all"):
        hit.append("同时具备禁忌标签: " + ",".join(rule_match["tags_all"]))
    return hit


def _nutrient_over(rule: dict, dish) -> list[str]:
    over = []
    for key, limit in (rule.get("nutrient_max") or {}).items():
        val = getattr(dish, key, 0.0) or 0.0
        if val > limit:
            over.append(f"{key}={val:g} 超过单份上限 {limit:g}")
    return over


def evaluate(rule, dish, resident) -> Violation | None:
    """通用分派；返回 Violation 或 None。"""
    p = rule.params or {}
    rt = rule.rule_type

    if rt == "allergen":
        hits = [a for a in (dish.allergens or []) if a in set(resident.allergies or [])]
        if hits:
            labels = "、".join(ALLERGEN_LABELS.get(a, a) for a in hits)
            return Violation(rule.code, rule.name, rule.severity, rule.priority,
                             f"含老人过敏成分：{labels}", rule.rationale)
        return None

    if rt == "iddsi":
        if (dish.iddsi_level or 7) > resident.swallowing_level:
            return Violation(rule.code, rule.name, rule.severity, rule.priority,
                             f"菜品 IDDSI {dish.iddsi_level} 高于老人可接受等级 "
                             f"{resident.swallowing_level}（呛咳/误吸风险）", rule.rationale)
        return None

    if rt == "religion":
        forbidden = RELIGION_FORBIDDEN_TAGS.get(resident.religion, [])
        hits = [TAG_LABELS.get(t, t) for t in (dish.tags or []) if t in forbidden]
        if hits:
            return Violation(rule.code, rule.name, rule.severity, rule.priority,
                             f"违反{RELIGION_LABELS.get(resident.religion, resident.religion)}"
                             f"饮食禁忌：{'、'.join(hits)}",
                             rule.rationale)
        return None

    if rt == "medication":
        med = (p.get("medication") or "").lower()
        if med not in [m.lower() for m in (resident.medications or [])]:
            return None
        hits = _match_sets(p.get("match") or {}, dish)
        over = _nutrient_over(p, dish)
        all_hits = hits + over
        if all_hits:
            return Violation(rule.code, rule.name, rule.severity, rule.priority,
                             f"服用 {med} 期间：{'；'.join(all_hits)}", rule.rationale)
        return None

    if rt == "chronic":
        cond = p.get("condition")
        if cond and cond not in set(resident.chronic_conditions or []):
            return None
        hits = _match_sets(p.get("match") or {}, dish)
        over = _nutrient_over(p, dish)
        all_hits = hits + over
        if all_hits:
            return Violation(rule.code, rule.name, rule.severity, rule.priority,
                             f"{rule.name}：{'；'.join(all_hits)}", rule.rationale)
        return None

    return None


def applicable_rules(rules: list, resident) -> list:
    """规则对该老人生效的条件初筛（allergen/iddsi/religion 恒生效）。"""
    out = []
    for r in rules:
        if not r.active:
            continue
        rt = r.rule_type
        if rt in ("allergen", "iddsi"):
            out.append(r)
        elif rt == "religion":
            if resident.religion and resident.religion != "none":
                out.append(r)
        elif rt == "medication":
            out.append(r)  # evaluate 内部按服药清单判断
        elif rt == "chronic":
            cond = (r.params or {}).get("condition")
            if not cond or cond in set(resident.chronic_conditions or []):
                out.append(r)
    return sorted(out, key=lambda x: (x.priority, x.id or 0))


def evaluate_dish(dish, resident, rules: list) -> dict:
    """对一道菜跑全部适用规则，按优先级返回 hard/soft 违规。"""
    hard, soft = [], []
    for rule in applicable_rules(rules, resident):
        v = evaluate(rule, dish, resident)
        if v:
            (hard if v.severity == "hard" else soft).append(v.as_dict())
    return {"hard": hard, "soft": soft, "eligible": len(hard) == 0}


def explain_rules(rules: list, resident) -> list[dict]:
    """给前端展示：当前老人适用的规则清单。"""
    rows = []
    for r in applicable_rules(rules, resident):
        rows.append({
            "code": r.code, "name": r.name, "type": r.rule_type,
            "severity": r.severity, "priority": r.priority,
            "version": r.version, "rationale": r.rationale,
            "params": r.params,
        })
    return rows


# ---------------- 默认规则表（种子数据） ----------------

DEFAULT_RULES: list[dict] = [
    # ---- 过敏原 / 吞咽 / 宗教（通用硬约束） ----
    dict(code="ALLERGEN-001", name="过敏原禁忌", rule_type="allergen", severity="hard",
         priority=1, rationale="档案登记过敏原必须 100% 排除，防止过敏性休克。"),
    dict(code="IDDSI-001", name="吞咽等级适配", rule_type="iddsi", severity="hard",
         priority=2, rationale="菜品质地等级不得高于老人 IDDSI 等级，防误吸。"),
    dict(code="RELIGION-001", name="宗教饮食禁忌", rule_type="religion", severity="hard",
         priority=3, rationale="尊重宗教信仰，排除其禁忌食材（如清真忌猪肉/酒精）。"),

    # ---- 慢病：标签型 ----
    dict(code="HTN-001", name="高血压-忌腌制高钠", rule_type="chronic", severity="hard",
         priority=10, version="1.1.0", condition_label="高血压",
         params={"condition": "hypertension",
                 "match": {"tags_any": ["pickle"]}},
         rationale="腌制食品钠含量极高，显著升高血压与卒中风险。"),
    dict(code="HTN-002", name="高血压-单菜限钠", rule_type="chronic", severity="hard",
         priority=11, version="1.1.0",
         params={"condition": "hypertension", "nutrient_max": {"sodium_mg": 900}},
         rationale="单菜品钠控制在 900mg 内，保证全日不超标。"),

    dict(code="DM-001", name="糖尿病-忌高糖", rule_type="chronic", severity="hard",
         priority=20,
         params={"condition": "diabetes", "match": {"tags_any": ["high_sugar"]}},
         rationale="含糖甜品导致血糖快速升高，需排除。"),
    dict(code="DM-002", name="糖尿病-限制油炸", rule_type="chronic", severity="soft",
         priority=21,
         params={"condition": "diabetes", "match": {"tags_any": ["fried"]}},
         rationale="油炸食品高热量，不利血糖与体重控制（软约束，尽量减少）。"),

    dict(code="CKD-001", name="肾病-限高钾", rule_type="chronic", severity="hard",
         priority=30,
         params={"condition": "ckd", "match": {"tags_any": ["high_potassium"]}},
         rationale="肾功能减退排钾障碍，高钾可诱发心律失常；蔬菜可焯水去钾。"),
    dict(code="CKD-002", name="肾病-限高磷/内脏", rule_type="chronic", severity="hard",
         priority=31,
         params={"condition": "ckd",
                 "match": {"tags_any": ["high_phosphorus", "organ_meat"]}},
         rationale="高磷血症加速肾病进展与血管钙化。"),
    dict(code="CKD-003", name="肾病-单菜限钾磷", rule_type="chronic", severity="soft",
         priority=32,
         params={"condition": "ckd",
                 "nutrient_max": {"potassium_mg": 600, "phosphorus_mg": 220}},
         rationale="单菜钾/磷软上限，帮助全日总量达标。"),

    dict(code="GOUT-001", name="痛风-限高嘌呤", rule_type="chronic", severity="hard",
         priority=40,
         params={"condition": "gout",
                 "match": {"tags_any": ["high_purine", "organ_meat", "strong_broth"]}},
         rationale="高嘌呤食物升高尿酸，诱发痛风急性发作。"),
    dict(code="GOUT-002", name="痛风-限海鲜", rule_type="chronic", severity="soft",
         priority=41,
         params={"condition": "gout", "match": {"tags_any": ["seafood"]}},
         rationale="部分海鲜嘌呤较高，急性期避免（软约束）。"),

    dict(code="HLP-001", name="高脂血症-限油炸肥肉", rule_type="chronic", severity="soft",
         priority=50,
         params={"condition": "hyperlipidemia",
                 "match": {"tags_any": ["fried", "fatty_meat"]}},
         rationale="饱和脂肪与反式脂肪升高 LDL（软约束）。"),

    # ---- 药物-食物交互 ----
    dict(code="MED-WARFARIN", name="华法林-维生素K稳定", rule_type="medication",
         severity="soft", priority=60,
         params={"medication": "warfarin",
                 "match": {"tags_any": ["high_vitamin_k"]},
                 "nutrient_max": {"vitamin_k_ug": 400}},
         rationale="维生素K 波动影响华法林抗凝效果，并非禁食而是保持每日摄入量稳定。"),
]
