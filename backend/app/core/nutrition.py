"""营养计算核心：个体化目标计算（多病共存冲突调解）+ 配方营养换算。

设计原则
--------
1. 目标计算透明可解释：每一步都追加 explanation 文本，前端可展示"为什么是这个值"。
2. 多病共存不是取严格交集，而是按临床优先级"分层修正"：
   CKD（中晚期）> 糖尿病 > 痛风急性期 > 高血压/血脂 > 基础能量蛋白。
   冲突（如 CKD 限蛋白 vs 肌少症/营养不良高蛋白）采用"适度上调 + 提示监测"策略。
3. 所有目标以 (min, max) 区间表达，求解器按区间设硬/软约束。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

NUTRIENTS = [
    "energy_kcal", "protein_g", "fat_g", "carbs_g", "dietary_fiber_g",
    "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg",
    "cholesterol_mg", "sugar_g", "purine_mg",
]

# 每 100g 成品营养字段
DISH_NUTRIENT_FIELDS = NUTRIENTS

# 年龄
def age(birth: date, today: date | None = None) -> int:
    today = today or date.today()
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


@dataclass
class TargetResult:
    targets: dict[str, tuple[float, float]] = field(default_factory=dict)
    explanation: list[str] = field(default_factory=list)
    conflict_notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "targets": {k: [round(v[0], 1), round(v[1], 1)] for k, v in self.targets.items()},
            "explanation": self.explanation,
            "conflict_notes": self.conflict_notes,
        }


def _set(t: TargetResult, key: str, lo: float, hi: float, why: str) -> None:
    lo, hi = min(lo, hi), max(lo, hi)
    if key in t.targets:
        old_lo, old_hi = t.targets[key]
        # 规则默认不覆盖，调用方显式 narrow/override
        t.targets[key] = (min(old_lo, lo), max(old_hi, hi))
    else:
        t.targets[key] = (lo, hi)
    t.explanation.append(f"{key}: {lo:.0f}~{hi:.0f}（{why}）")


def _narrow(t: TargetResult, key: str, lo: float, hi: float, why: str) -> None:
    """收紧已有区间（取交集）。"""
    lo, hi = min(lo, hi), max(lo, hi)
    if key in t.targets:
        olo, ohi = t.targets[key]
        nlo, nhi = max(olo, lo), min(ohi, hi)
        if nlo > nhi:
            # 冲突：保留慢病约束并记录
            t.conflict_notes.append(
                f"{key} 目标冲突：基础 {olo:.0f}~{ohi:.0f} 与 {why} {lo:.0f}~{hi:.0f} 无交集，"
                f"按慢病优先取 {lo:.0f}~{hi:.0f}，建议临床复查")
            t.targets[key] = (lo, hi)
        else:
            t.targets[key] = (nlo, nhi)
    else:
        t.targets[key] = (lo, hi)
    t.explanation.append(f"{key}: 收紧至 {t.targets[key][0]:.0f}~{t.targets[key][1]:.0f}（{why}）")


def _override(t: TargetResult, key: str, lo: float, hi: float, why: str) -> None:
    lo, hi = min(lo, hi), max(lo, hi)
    t.targets[key] = (lo, hi)
    t.explanation.append(f"{key}: 覆盖为 {lo:.0f}~{hi:.0f}（{why}）")


# ───────────────────────── 个体化营养目标 ─────────────────────────

def compute_targets(
    *,
    birth_date: date,
    gender: str,
    height_cm: float,
    weight_kg: float,
    activity_level: str,
    chronic_diseases: list[str],
    nutrition_goal: str,
    target_overrides: dict | None = None,
) -> TargetResult:
    """根据档案计算每日营养目标区间。返回 TargetResult（含解释链与冲突说明）。"""
    from ..models.elder import ACTIVITY_FACTORS

    t = TargetResult()
    years = age(birth_date)
    diseases = set(chronic_diseases)

    # ---- 1) 基础能量：老年人 Mifflin-St Jeor + 活体系数，老年瘦体重下降再 ×0.9 ----
    if gender == "male":
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * years + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * years - 161
    af = ACTIVITY_FACTORS.get(activity_level, 1.2)
    tee = bmr * af
    if years >= 65:
        tee *= 0.95
        t.explanation.append(f"年龄 {years} 岁（≥65），基础能量按老年瘦体重下调 5%")

    # 目标修正
    goal_delta = 0.0
    if nutrition_goal == "lose":
        goal_delta = -300.0
    elif nutrition_goal == "gain":
        goal_delta = 300.0
    elif nutrition_goal == "malnutrition":
        goal_delta = 350.0
    if goal_delta:
        t.explanation.append(
            f"营养目标「{nutrition_goal}」能量调整 {goal_delta:+.0f} kcal")
    energy = max(1200.0, tee + goal_delta)

    # 卧床最低保底 1500（防误配过低）
    energy = max(energy, 1500.0 if activity_level != "bedridden" else 1300.0)
    _set(t, "energy_kcal", energy * 0.92, energy * 1.08,
         f"Mifflin BMR {bmr:.0f} × 活体系数 {af}")

    # ---- 2) 蛋白质：健康老人 1.0~1.2 g/kg；肌少症/营养不良 1.2~1.5 ----
    protein_per_kg = (1.0, 1.2)
    why_protein = "健康老年人推荐 1.0~1.2 g/kg"
    if {"sarcopenia", "malnutrition"} & diseases or nutrition_goal in ("gain", "malnutrition"):
        protein_per_kg = (1.2, 1.5)
        why_protein = "肌少症/营养不良/增重目标 1.2~1.5 g/kg"
    p_lo, p_hi = weight_kg * protein_per_kg[0], weight_kg * protein_per_kg[1]
    _set(t, "protein_g", p_lo, p_hi, why_protein)

    # ---- 3) 脂肪 / 碳水 / 糖 / 纤维 / 胆固醇 ----
    _set(t, "fat_g", energy * 0.20 / 9, energy * 0.30 / 9, "脂肪占总能量 20%~30%")
    _set(t, "carbs_g", energy * 0.45 / 4, energy * 0.60 / 4, "碳水占总能量 45%~60%")
    _set(t, "sugar_g", 0, 25, "WHO 游离糖建议 <25g/d")
    _set(t, "dietary_fiber_g", 20, 30, "老年人膳食纤维 20~30g/d")
    _set(t, "cholesterol_mg", 0, 300, "膳食胆固醇一般建议 <300mg/d")

    # ---- 4) 电解质与微量元素（通用老年建议）----
    _set(t, "sodium_mg", 0, 2000, "老年人限钠 <2000mg/d（食盐约5g）")
    _set(t, "potassium_mg", 2000, 3600, "钾摄入 2000~3600mg/d")
    _set(t, "phosphorus_mg", 0, 1500, "一般成人磷 <1500mg/d")
    _set(t, "calcium_mg", 1000, 1200, "老年人钙推荐 1000~1200mg/d")
    _set(t, "purine_mg", 0, 600, "一般嘌呤 <600mg/d")

    # ---- 5) 慢病分层修正（按优先级）----
    # 5.1 高血压
    if "hypertension" in diseases:
        _narrow(t, "sodium_mg", 0, 1500, "高血压 DASH 限钠 <1500mg/d")
        _narrow(t, "potassium_mg", 3000, 3600, "高血压建议高钾 3000~3600mg/d")
        t.explanation.append("高血压：采用 DASH 模式，富钾蔬果、限腌制/加工肉")

    # 5.2 糖尿病
    if "diabetes2" in diseases:
        _narrow(t, "carbs_g", energy * 0.45 / 4, energy * 0.55 / 4,
                "2型糖尿病碳水占比 45%~55%")
        _narrow(t, "sugar_g", 0, 20, "糖尿病游离糖 <20g/d")
        _narrow(t, "dietary_fiber_g", 25, 35, "糖尿病纤维 25~35g/d 稳血糖")
        t.explanation.append("2型糖尿病：低 GI、控制精制碳水，分餐均匀")

    # 5.3 血脂异常
    if "dyslipidemia" in diseases:
        _narrow(t, "fat_g", energy * 0.20 / 9, energy * 0.25 / 9,
                "血脂异常脂肪 20%~25%")
        _narrow(t, "cholesterol_mg", 0, 200, "血脂异常胆固醇 <200mg/d")
        t.explanation.append("血脂异常：限饱和脂肪/动物内脏，增加深海鱼与全谷")

    # 5.4 痛风
    if "gout" in diseases:
        _narrow(t, "purine_mg", 0, 150, "痛风急性期严格限嘌呤 <150mg/d")
        t.explanation.append("痛风：避免海鲜、动物内脏、浓肉汤，保证饮水")

    # 5.5 骨质疏松（提高钙与蛋白下限，不与 CKD 同发时生效；同发时让位 CKD）
    if "osteoporosis" in diseases and "ckd" not in diseases:
        _narrow(t, "calcium_mg", 1200, 1500, "骨质疏松钙 1200~1500mg/d")
        t.explanation.append("骨质疏松：提高钙与优质蛋白，配合维D日照")

    # 5.6 CKD（最高优先级，限蛋白/钾/磷/钠，与肌少症高蛋白冲突时折中）
    if "ckd" in diseases:
        ck_lo, ck_hi = weight_kg * 0.6, weight_kg * 0.8
        if {"sarcopenia", "malnutrition"} & diseases or nutrition_goal in (
                "gain", "malnutrition"):
            # 冲突调解：透析前不宜高蛋白，但避免肌少症恶化 → 0.8~1.0 折中并提示
            ck_lo, ck_hi = weight_kg * 0.8, weight_kg * 1.0
            t.conflict_notes.append(
                "CKD 限蛋白（0.6~0.8g/kg）与肌少症/营养不良高蛋白（1.2~1.5g/kg）冲突："
                "采用折中 0.8~1.0g/kg 优质蛋白，需医生/营养师按透析情况与白蛋白复查")
        _override(t, "protein_g", ck_lo, ck_hi, "CKD 非透析优质低蛋白 0.6~0.8g/kg")
        _narrow(t, "potassium_mg", 0, 2000, "CKD 限钾 <2000mg/d")
        _narrow(t, "phosphorus_mg", 0, 800, "CKD 限磷 <800mg/d")
        _narrow(t, "sodium_mg", 0, 1500, "CKD 限钠 <1500mg/d")
        _narrow(t, "calcium_mg", 800, 1000, "CKD 钙 800~1000mg/d 防血管钙化")
        t.explanation.append("CKD：限豆制品浓汤之外的高磷、高钾食物（香蕉/橙汁/土豆）")

    # ---- 6) COPD（高蛋白高脂低碳水，降低呼吸商）----
    if "copd" in diseases:
        _narrow(t, "fat_g", energy * 0.30 / 9, energy * 0.35 / 9,
                "COPD 提高脂肪供能 30%~35%")
        _narrow(t, "carbs_g", energy * 0.40 / 4, energy * 0.50 / 4,
                "COPD 碳水 40%~50% 降低 CO2 产生")
        t.explanation.append("COPD：高脂低碳、足量蛋白，减少产气食物")

    # ---- 7) 手工覆盖（营养师权威，置顶优先级）----
    if target_overrides:
        for k, v in target_overrides.items():
            if k not in t.targets:
                continue
            if isinstance(v, (int, float)):
                lo, hi = v * 0.9, v * 1.1
            else:
                lo, hi = float(v[0]), float(v[1])
            _override(t, k, lo, hi, "营养师手工覆盖")

    # 四舍五入整理
    t.targets = {k: (round(lo, 1), round(hi, 1)) for k, (lo, hi) in t.targets.items()}
    return t


# ───────────────────────── 配方营养换算 ─────────────────────────

def recipe_to_finished(dish_weight_g: float, rows: list[dict]) -> dict[str, float]:
    """根据配方行计算成品每100g营养与每份成本。

    rows: [{"ing": Ingredient, "gross_weight_g": float, "cooking_loss_rate": float}]
    可食部：可食重量 = 市品重量 × edible_rate
    熟后重量 = 可食重量 × (1 - 烹饪损失率)   （负值=吸水，如米粥重量增加）
    营养保留 = 可食重量 × min(1, 1-损失率) × (食材每100g营养 / 100)
              吸水只增加重量不增加营养；失水按比例浓缩（维生素流失另行修正系数）
    成品每100g营养 = 总营养保留 / 熟后总重 × 100
    """
    totals = {n: 0.0 for n in NUTRIENTS}
    total_cost = 0.0
    cooked_weight = 0.0
    for r in rows:
        ing = r["ing"]
        gross = float(r["gross_weight_g"])
        loss = float(r.get("cooking_loss_rate", 0.0))
        edible = gross * ing.edible_rate
        retained_weight = edible * (1.0 - loss)          # 熟后重量（吸水>生食重）
        retained_nutrient = edible * min(1.0, 1.0 - loss)  # 吸水不创造营养
        cooked_weight += retained_weight
        for n in NUTRIENTS:
            totals[n] += retained_nutrient * getattr(ing, n, 0.0) / 100.0
        total_cost += gross * ing.unit_cost / 100.0

    out = {}
    denom = cooked_weight if cooked_weight > 0 else dish_weight_g
    for n in NUTRIENTS:
        out[n] = totals[n] / denom * 100.0 if denom else 0.0
    out["cost_per_portion"] = total_cost  # 一份成品总成本（元）
    out["cooked_weight_g"] = cooked_weight
    return out
