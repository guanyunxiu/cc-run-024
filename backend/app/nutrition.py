"""个体化营养目标计算。

依据 Mifflin-St Jeor 公式估算基础代谢，结合活动量、营养目标与慢病，
输出每日能量、蛋白质、钠、钾、磷、膳食纤维等目标。
多病共存时记录冲突与折衷依据，供前端解释展示。
"""
from dataclasses import dataclass, field

from .config import ACTIVITY_FACTOR
from .models import Resident

NUTRIENT_FIELDS = [
    "energy_kcal", "protein_g", "fat_g", "carb_g", "sodium_mg",
    "potassium_mg", "phosphorus_mg", "fiber_g", "calcium_mg",
]


@dataclass
class TargetResult:
    targets: dict = field(default_factory=dict)
    conflicts: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    bmr: float = 0.0
    tdee: float = 0.0
    bmi: float = 0.0


def _rng(low: float | None, high: float | None, target: float | None = None) -> dict:
    d = {}
    if low is not None:
        d["min"] = round(low, 1)
    if high is not None:
        d["max"] = round(high, 1)
    if target is not None:
        d["target"] = round(target, 1)
    return d


def compute_targets(r: Resident) -> TargetResult:
    res = TargetResult()
    w, h, age = r.weight_kg, r.height_cm, r.age
    bmi = w / ((h / 100) ** 2)
    res.bmi = round(bmi, 1)

    # 1) BMR（Mifflin-St Jeor）
    bmr = 10 * w + 6.25 * h - 5 * age + (5 if r.gender == "male" else -161)
    res.bmr = round(bmr)
    pal = ACTIVITY_FACTOR.get(r.activity_level, 1.3)
    tdee = bmr * pal

    conds = set(r.chronic_conditions)
    # 2) 能量按目标微调
    if r.nutrition_goal_type == "lose":
        tdee -= 300
        res.assumptions.append("减重目标：在总消耗基础上减少约 300 kcal/日")
    elif r.nutrition_goal_type == "gain":
        tdee += 300
        res.assumptions.append("增重目标：在总消耗基础上增加约 300 kcal/日")
    # 高龄安全下限，避免极低能量
    floor = 1500 if r.gender == "male" else 1200
    if tdee < floor:
        res.assumptions.append(f"能量低于高龄安全下限，按 {floor} kcal 兜底")
        tdee = float(floor)
    res.tdee = round(tdee)

    energy_t = round(tdee / 10) * 10

    # 3) 蛋白质 g/kg —— 多病共存冲突核心
    pro_per_kg = 1.0
    reasons = []
    elderly = age >= 75
    if elderly:
        pro_per_kg = max(pro_per_kg, 1.1)
        reasons.append("高龄老人预防肌少症：蛋白质 ≥1.1 g/kg")
    if "diabetes" in conds:
        pro_per_kg = max(pro_per_kg, 1.1)
        reasons.append("糖尿病：建议蛋白质 1.0–1.2 g/kg 以稳定血糖")
    if "ckd" in conds:
        ckd_need = 0.7
        if pro_per_kg > ckd_need:
            # 冲突：限蛋白 vs 防肌少症/糖尿病 —— 折衷 0.9 g/kg
            res.conflicts.append({
                "nutrient": "protein_g",
                "topic": "慢性肾病限蛋白 vs 高龄/糖尿病需充足蛋白",
                "resolution": "折衷采用 0.9 g/kg，并选用高生物价蛋白（蛋、鱼、大豆），由营养师按 eGFR 复核",
            })
            pro_per_kg = 0.9
        else:
            pro_per_kg = ckd_need
            reasons.append("慢性肾病非透析：蛋白质 0.6–0.8 g/kg")
    if "gout" in conds:
        reasons.append("痛风：蛋白质不过量，优先蛋奶豆，限高嘌呤食材")
    protein_t = round(pro_per_kg * w)
    res.assumptions.extend(reasons)

    # 4) 钠
    sodium_max = 2300.0
    if "hypertension" in conds:
        sodium_max = 2000.0
    if ("hypertension" in conds and ("diabetes" in conds or "ckd" in conds)) or "ckd" in conds:
        sodium_max = 1500.0
        res.assumptions.append("高血压合并糖尿病/肾病：钠严格限至 1500 mg")

    # 5) 钾
    if "ckd" in conds:
        k_low, k_high = None, 2000.0
        res.assumptions.append("慢性肾病：限钾 ≤2000 mg/日，蔬菜焯水去钾")
    else:
        k_low, k_high = 2000.0, 4000.0

    # 6) 磷
    p_max = 800.0 if "ckd" in conds else 1500.0

    # 7) 膳食纤维
    fiber_min = 25.0
    if "diabetes" in conds:
        fiber_min = 30.0
        res.assumptions.append("糖尿病：膳食纤维 ≥30 g/日，优先全谷物")
    if r.swallowing_level <= 5:
        before = fiber_min
        fiber_min = max(20.0, fiber_min - 5)
        res.conflicts.append({
            "nutrient": "fiber_g",
            "topic": f"糖尿病建议高纤维({before:.0f}g) 与 IDDSI {r.swallowing_level} 吞咽受限",
            "resolution": f"采用细腻全谷糊、瓜果泥等可溶性纤维，目标下调至 {fiber_min:.0f} g",
        })

    # 8) 脂肪 / 碳水 供能比
    fat_pct = 0.25 if "hyperlipidemia" in conds else 0.30
    fat_max = round(energy_t * fat_pct / 9)
    if "diabetes" in conds:
        carb_low = round(energy_t * 0.45 / 4)
        carb_high = round(energy_t * 0.55 / 4)
        res.assumptions.append("糖尿病：碳水供能 45%–55%，低 GI、分餐")
    else:
        carb_low, carb_high = round(energy_t * 0.45 / 4), round(energy_t * 0.60 / 4)

    if "hyperlipidemia" in conds:
        res.assumptions.append("高脂血症：脂肪供能 ≤25%，避免油炸与肥肉")
    if "gout" in conds:
        res.assumptions.append("痛风：限酒、动物内脏、浓肉汤等高嘌呤食物，多饮水")

    # 9) 钙（高龄通用）
    calcium_min = 1000.0

    t = {
        "energy_kcal": _rng(energy_t - 200, energy_t + 200, energy_t),
        "protein_g": _rng(round(protein_t * 0.9), round(protein_t * 1.3), protein_t),
        "fat_g": _rng(None, fat_max),
        "carb_g": _rng(carb_low, carb_high),
        "sodium_mg": _rng(None, sodium_max, sodium_max * 0.9),
        "potassium_mg": _rng(k_low, k_high),
        "phosphorus_mg": _rng(None, p_max),
        "fiber_g": _rng(fiber_min, 35.0, fiber_min + 3),
        "calcium_mg": _rng(calcium_min, 2500.0),
    }
    # 手工覆盖（营养师权威）
    for k, v in (r.custom_targets or {}).items():
        if k in t and isinstance(v, (int, float)):
            t[k] = {"target": float(v), "min": float(v) * 0.9, "max": float(v) * 1.1}
            res.assumptions.append(f"营养师手工覆盖 {k} = {v}")
    res.targets = t
    return res


def targets_snapshot(r: Resident) -> dict:
    res = compute_targets(r)
    return {
        "targets": res.targets,
        "conflicts": res.conflicts,
        "assumptions": res.assumptions,
        "bmr": res.bmr,
        "tdee": res.tdee,
        "bmi": res.bmi,
    }
