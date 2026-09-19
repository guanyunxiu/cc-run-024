"""CP-SAT 配餐求解器（OR-Tools）。

决策变量
--------
对每个 (day, slot, 候选菜)：
  x 布尔（是否选用）；u 整数 0..MAX_UNIT（份数单元，每单元 = UNIT_G 克），
  x=1 ⇔ u≥1（channeling）。

硬约束
------
  过敏/宗教/IDDSI/慢病禁忌/药食交互（forbid 级，预过滤候选）
  餐次结构（主食必选，午晚荤素搭配，每槽位菜品数上下限）
  日成本上限；同菜周重复 ≤3；相邻日同餐次不重复；锁定菜固定
软约束（加权最小化）
  营养偏差（能量/蛋白/钠/钾/磷/纤维，区间外线性罚分）
  成本、浪费率、低满意度、重复、多样性、慢病风险标签

三阶段求解（多营养区间同时硬卡数学上常不可行，且大系数营养目标会拖慢 CP-SAT）：
  phase0 无营养目标求纯可行（秒级），phase1 温和营养引导选菜，
  phase2 固定结构只优化份量精调营养偏差。
若严格硬约束不可行，自动分级松弛（成本 +25% → 结构放宽 → 重复频率放宽）并记录轨迹。
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from .rules_engine import RuleEngine, Violation

UNIT_G = 30              # 每份量单元（克）
MAX_UNIT = 10            # 单菜最大 300g
SCALE = 100              # 营养数值放大系数（转整数）

# 软约束默认权重（求解器参数可覆盖）
DEFAULT_WEIGHTS = {
    "nutrition": 1000,   # 营养偏差
    "cost": 25,          # 成本（元 ×权重）
    "waste": 60,         # 浪费
    "satisfaction": 40,  # 满意度不足
    "repeat": 90,        # 重复出现
    "risk_tag": 150,     # 慢病软风险标签（warn 级）
}

# 进入目标函数的营养素（归一化方式：除以目标区间中值）
OBJECTIVE_NUTRIENTS = [
    "energy_kcal", "protein_g", "sodium_mg",
    "potassium_mg", "phosphorus_mg", "dietary_fiber_g",
]


@dataclass
class CandidateDish:
    dish_id: int
    name: str
    dish_type: str
    slots: list[str]
    # 每 UNIT_G 克的营养与成本
    per_unit: dict[str, float]
    cost_per_unit: float
    preference_score: float
    waste_rate: float
    iddsi_level: int
    risk_tags: set[str] = field(default_factory=set)
    violations: list[Violation] = field(default_factory=list)


@dataclass
class SolveResult:
    status: str                    # optimal / feasible / infeasible / error
    objective: float
    items: list[dict]              # day/slot/dish/portion
    daily_nutrients: list[dict]
    daily_costs: list[float]
    total_cost: float
    score_breakdown: dict
    relaxations: list[str]
    solve_seconds: float
    candidate_count: int
    warnings: list[str]


def _per_unit(dish, unit_g: int) -> dict[str, float]:
    f = unit_g / 100.0
    keys = ["energy_kcal", "protein_g", "fat_g", "carbs_g", "dietary_fiber_g",
            "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg",
            "cholesterol_mg", "sugar_g", "purine_mg"]
    return {k: getattr(dish, k, 0.0) * f for k in keys}


def build_candidates(dishes, person_ctx, engine: RuleEngine,
                     ingredient_map: dict | None = None) -> tuple[list[CandidateDish], dict[int, list]]:
    """预过滤：返回候选列表与被淘汰菜及原因（供前端解释）。"""
    ingredient_map = ingredient_map or {}
    candidates, rejected = [], {}
    for d in dishes:
        if not d.is_active:
            continue
        dctx = ingredient_map.get("__dish_ctx__", {}).get(d.id)
        if dctx is None:
            from .rules_engine import compile_dish
            dctx = compile_dish(d)
        viol = engine.evaluate_dish(person_ctx, dctx)
        if RuleEngine.has_forbid(viol):
            rejected[d.id] = [v.to_dict() for v in viol if v.level == "forbid"]
            continue
        per = _per_unit(d, UNIT_G)
        cost_per_portion = d.portion_cost or 0.0
        candidates.append(CandidateDish(
            dish_id=d.id, name=d.name, dish_type=d.dish_type,
            slots=[s.strip() for s in d.meal_slots.split(",") if s.strip()],
            per_unit=per,
            cost_per_unit=cost_per_portion * UNIT_G / max(d.portion_g, 1.0),
            preference_score=d.preference_score,
            waste_rate=d.waste_rate,
            iddsi_level=d.iddsi_level,
            risk_tags={v.rule_code for v in viol if v.level == "warn"},
            violations=viol,
        ))
    return candidates, rejected


def _type_groups(candidates: list[CandidateDish]) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = {}
    for i, c in enumerate(candidates):
        groups.setdefault(c.dish_type or "other", []).append(i)
    return groups


# ───────────── 贪心初始可行解（作为 CP-SAT hint，快速锁定可行域）─────────────

SLOT_TYPES = {
    "breakfast": [("staple", "liquid_staple"), ("egg", "milk", "soy", "meat")],
    "lunch": [("staple", "liquid_staple"), ("meat", "egg", "soy"), ("vegetable",)],
    "dinner": [("staple", "liquid_staple"), ("egg", "soy", "meat"), ("vegetable",)],
}



def solve(
    *,
    days: int,
    dates: list[str],
    slots: list[str],
    dishes,                          # Dish ORM 列表
    person_ctx,
    engine: RuleEngine,
    targets: dict[str, tuple[float, float]],
    cost_limit_day: float,
    weights: dict | None = None,
    time_limit_seconds: float = 20.0,
    random_seed: int = 42,
    locked_items: list[dict] | None = None,   # [{day_index,slot,dish_id,portion_g}]
    max_repeat_week: int = 3,
    ingredient_map: dict | None = None,
) -> SolveResult:
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    locked_items = locked_items or []
    t0 = time.time()
    relaxations: list[str] = []
    warnings: list[str] = []

    candidates, rejected = build_candidates(dishes, person_ctx, engine, ingredient_map)
    if not candidates:
        return SolveResult("infeasible", 0, [], [], [], 0, {}, [], 0.0, 0,
                           ["无任何通过禁忌校验的候选菜品，请先扩充菜品库或放宽档案限制"])

    # 锁定菜若在禁选名单则直接冲突报错
    locked_by_key = {(li["day_index"], li["slot"], li["dish_id"]): li for li in locked_items}
    for li in locked_items:
        if li["dish_id"] in rejected:
            v = rejected[li["dish_id"]][0]
            warnings.append(f"锁定菜 #{li['dish_id']} 在 {li['slot']} 违反硬约束：{v['message']}")

    groups = _type_groups(candidates)
    cid_index = {c.dish_id: i for i, c in enumerate(candidates)}

    def build_model(cost_factor: float, strict_structure: bool, repeat_limit: int,
                    nut_scale: float = 1.0):
        m = cp_model.CpModel()
        x, u = {}, {}
        for d in range(days):
            for s_idx, slot in enumerate(slots):
                for i, c in enumerate(candidates):
                    if slot not in c.slots:
                        continue
                    x[d, s_idx, i] = m.NewBoolVar(f"x_{d}_{s_idx}_{i}")
                    u[d, s_idx, i] = m.NewIntVar(0, MAX_UNIT, f"u_{d}_{s_idx}_{i}")
                    # channeling: x=1 ⇔ u≥1
                    m.Add(u[d, s_idx, i] >= 1).OnlyEnforceIf(x[d, s_idx, i])
                    m.Add(u[d, s_idx, i] == 0).OnlyEnforceIf(x[d, s_idx, i].Not())

        # ---- 餐次结构 ----
        min_dishes = {"breakfast": 2, "lunch": 3, "dinner": 2 if strict_structure else 1}
        max_dishes = {"breakfast": 3, "lunch": 4, "dinner": 3}
        for d in range(days):
            for s_idx, slot in enumerate(slots):
                present = [x[d, s_idx, i] for i in range(len(candidates))
                           if (d, s_idx, i) in x]
                m.Add(sum(present) >= min_dishes[slot])
                m.Add(sum(present) <= max_dishes[slot])
                def gsum(types):
                    return [x[d, s_idx, i] for t in types for i in groups.get(t, [])
                            if (d, s_idx, i) in x]
                staple = gsum(["staple", "liquid_staple"])
                if staple:
                    m.Add(sum(staple) >= 1)  # 每餐至少一种主食
                if slot == "lunch":
                    meat = gsum(["meat", "egg", "soy"])
                    if meat and strict_structure:
                        m.Add(sum(meat) >= 1)
                    veg = gsum(["vegetable"])
                    if veg and strict_structure:
                        m.Add(sum(veg) >= 1)
                if slot == "dinner":
                    veg = gsum(["vegetable"])
                    if veg and strict_structure:
                        m.Add(sum(veg) >= 1)
                if slot == "breakfast":
                    protein = gsum(["meat", "egg", "soy", "milk"])
                    if protein and strict_structure:
                        m.Add(sum(protein) >= 1)

        # ---- 成本上限（硬） ----
        for d in range(days):
            day_cost = []
            for s_idx in range(len(slots)):
                for i, c in enumerate(candidates):
                    if (d, s_idx, i) in x:
                        day_cost.append(int(round(c.cost_per_unit * SCALE)) * u[d, s_idx, i])
            m.Add(sum(day_cost) <= int(cost_limit_day * cost_factor * SCALE))

        # ---- 重复频率 ----
        for i, c in enumerate(candidates):
            all_presence = [x[d, s_idx, i] for d in range(days)
                            for s_idx in range(len(slots)) if (d, s_idx, i) in x]
            if all_presence:
                m.Add(sum(all_presence) <= repeat_limit)
        adj_enabled = repeat_limit < 99
        if adj_enabled:
            for d in range(days - 1):
                for s_idx in range(len(slots)):
                    for i in range(len(candidates)):
                        if (d, s_idx, i) in x and (d + 1, s_idx, i) in x:
                            m.Add(x[d, s_idx, i] + x[d + 1, s_idx, i] <= 1)

        # ---- 锁定菜 ----
        for (d, slot, dish_id), li in locked_by_key.items():
            if dish_id not in cid_index:
                continue  # 被禁菜：无法锁定，已在 warnings 记录
            s_idx = slots.index(slot)
            i = cid_index[dish_id]
            if (d, s_idx, i) not in x:
                warnings.append(f"锁定菜「{li.get('dish_name', dish_id)}」不适用于该餐次，已忽略")
                continue
            m.Add(x[d, s_idx, i] == 1)
            units = max(1, min(MAX_UNIT, int(round(li["portion_g"] / UNIT_G))))
            m.Add(u[d, s_idx, i] == units)

        # ---- 软约束目标 ----
        obj_terms: list = []
        breakdown = {k: 0 for k in
                     ["nutrition", "cost", "waste", "satisfaction", "repeat", "risk_tag"]}

        # 日营养偏差（区间外距离 / 目标中值 ×SCALE 加权）
        nutrient_keys = ["energy_kcal", "protein_g", "fat_g", "carbs_g", "dietary_fiber_g",
                         "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg",
                         "cholesterol_mg", "sugar_g", "purine_mg"]
        day_nut_var = {}
        for d in range(days):
            for k in nutrient_keys:
                expr = 0
                for s_idx in range(len(slots)):
                    for i, c in enumerate(candidates):
                        if (d, s_idx, i) in x:
                            coef = int(round(c.per_unit[k] * SCALE / UNIT_G * UNIT_G))
                            expr += coef * u[d, s_idx, i]
                day_nut_var[d, k] = expr

        # 营养偏差：纯线性归一化（避免除法约束拖慢 CP-SAT 搜索）
        # 罚分 ≈ w_nut × 100 × 偏离百分点，其中 w_nut = 10000 / 中值（取整，系数保持温和）
        # nut_scale: phase1 选菜用 0.25（温和引导选高营养菜），phase2 用 1.0（精调份量）
        # nut_scale > 0 时启用营养目标（phase1 温和 / phase2 完整）
        if nut_scale > 0:
            nut_w = int(weights["nutrition"] * nut_scale)
            for k in OBJECTIVE_NUTRIENTS:
                if k not in targets:
                    continue
                lo, hi = targets[k]
                mid = max((lo + hi) / 2, 1e-6)
                lin_weight = max(1, int(10000.0 / mid))   # 每 SCALE 单位偏差的罚系数
                for d in range(days):
                    val = day_nut_var[d, k]
                    lo_v = int(lo * SCALE)
                    hi_v = int(hi * SCALE)
                    cap = int(mid * SCALE * 5)             # 偏差封顶 500% 中值
                    below = m.NewIntVar(0, cap, f"below_{k}_{d}")
                    above = m.NewIntVar(0, cap, f"above_{k}_{d}")
                    m.AddMaxEquality(below, [lo_v - val, 0])
                    m.AddMaxEquality(above, [val - hi_v, 0])
                    obj_terms.append(nut_w * lin_weight * below)
                    obj_terms.append(nut_w * lin_weight * above)

        # 成本/浪费/满意度（系数折叠为整数，避免线性表达式除法）
        for d in range(days):
            for s_idx in range(len(slots)):
                for i, c in enumerate(candidates):
                    if (d, s_idx, i) not in x:
                        continue
                    coef_cost = int(round(weights["cost"] * c.cost_per_unit))
                    if coef_cost:
                        obj_terms.append(coef_cost * u[d, s_idx, i])
                    coef_waste = int(round(weights["waste"] * c.waste_rate * 10))
                    if coef_waste:
                        obj_terms.append(coef_waste * u[d, s_idx, i])
                    sat_pen = int(round(weights["satisfaction"] * (5.0 - c.preference_score)))
                    if sat_pen:
                        obj_terms.append(sat_pen * x[d, s_idx, i])
                    # 慢病软风险
                    if c.risk_tags:
                        obj_terms.append(weights["risk_tag"] * x[d, s_idx, i])

        # 重复/多样性：同菜第 2 次出现起递增罚分
        for i, c in enumerate(candidates):
            all_presence = [x[d, s_idx, i] for d in range(days)
                            for s_idx in range(len(slots)) if (d, s_idx, i) in x]
            if len(all_presence) >= 2:
                obj_terms.append(weights["repeat"] * (sum(all_presence) - 1))

        m.Minimize(sum(obj_terms))
        return m, x, u, day_nut_var

    # ── 容量预检（按餐次槽位给出可解释的供给不足提示）──
    slot_min = {"breakfast": 2, "lunch": 3, "dinner": 2}
    precheck_msgs = []
    for slot in slots:
        capable = [c for c in candidates if slot in c.slots]
        needed = days * slot_min[slot]
        # 严格模式理论容量：每菜 max_repeat_week 次
        capacity = len(capable) * max_repeat_week
        if capacity < needed:
            precheck_msgs.append(
                f"{slot} 可用候选仅 {len(capable)} 道，按每菜周限 {max_repeat_week} 次"
                f"可供给 {capacity} 份 < 最低需求 {needed} 份；将自动放宽重复限制")

    # ── 分级配置（成本松弛 → 结构松弛 → 重复约束松弛）──
    attempts = [
        (1.00, True, max_repeat_week, ""),
        (1.25, True, max_repeat_week, "严格成本上限不可行：日成本上限松弛 +25%"),
        (1.50, False, max_repeat_week, "结构强约束不可行：放宽荤素结构下限，成本上限 +50%"),
        (1.50, False, 99, "候选菜品不足：进一步放宽周重复频率限制（多样性由目标函数尽量保持）"),
    ]

    def run_sat(mod, tlimit):
        sv = cp_model.CpSolver()
        sv.parameters.max_time_in_seconds = max(2.0, tlimit)
        sv.parameters.num_search_workers = 8
        sv.parameters.random_seed = random_seed
        return sv, sv.Solve(mod)

    model = x = u = day_nut_var = None
    solver = None
    chosen_keys: set = set()
    t_budget = time_limit_seconds
    for cost_factor, strict, repeat_limit, note in attempts:
        # 阶段 1a：纯可行（无营养目标），快速判断该松弛级别是否可行并取得可行结构
        mf, xf, uf, _ = build_model(cost_factor, strict, repeat_limit, nut_scale=0.0)
        mf.Minimize(0)
        svf, stf = run_sat(mf, t_budget * 0.12)
        if stf not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            continue  # 该松弛级别结构都不可行 → 进入下一级别

        # 阶段 1b：优化结构（满意度/成本/浪费/多样性/温和营养引导）
        m1, x1, u1, _ = build_model(cost_factor, strict, repeat_limit, nut_scale=0.3)
        # 用 phase0 的可行结构作为 hint，避免带营养目标时重新冷启动
        for k in x1:
            if k in xf:
                m1.AddHint(x1[k], svf.Value(xf[k]))
                m1.AddHint(u1[k], svf.Value(uf[k]))
        sv1, st1 = run_sat(m1, t_budget * 0.33)
        if st1 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            # 优化超时但 1a 已证明可行 → 直接用 1a 的可行结构
            sv1, st1, m1, x1, u1 = svf, stf, mf, xf, uf
        chosen = {k for k in x1 if sv1.Value(x1[k]) == 1}

        # 阶段 2：固定结构，只优化份量与营养偏差（x 全固定后规模骤减）
        m2, x2, u2, dnv2 = build_model(cost_factor, strict, repeat_limit, nut_scale=1.0)
        for k in x2:
            m2.Add(x2[k] == 1 if k in chosen else x2[k] == 0)
        sv2, st2 = run_sat(m2, t_budget * 0.55)
        if st2 in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            model, x, u, day_nut_var = m2, x2, u2, dnv2
            solver, chosen_keys = sv2, chosen
            if note:
                relaxations.append(note)
            break
        # 阶段2失败则退回阶段1结构（默认份量），保证有可用方案
        model, x, u, day_nut_var = m1, x1, u1, {}
        solver, chosen_keys = sv1, chosen
        if note:
            relaxations.append(note)
        break
    else:
        return SolveResult("infeasible", 0, [], [], [], 0, {},
                           [a[3] for a in attempts if a[3]],
                           time.time() - t0, len(candidates),
                           precheck_msgs + warnings +
                           ["候选菜品不足以构成可行餐次，请扩充菜品库或放宽档案限制"])

    # ── 提取结果 ──
    nutrient_keys = ["energy_kcal", "protein_g", "fat_g", "carbs_g", "dietary_fiber_g",
                     "sodium_mg", "potassium_mg", "phosphorus_mg", "calcium_mg",
                     "cholesterol_mg", "sugar_g", "purine_mg"]
    items, daily_nutrients, daily_costs = [], [], []
    dish_count: dict[int, int] = {}
    for d in range(days):
        dn = {k: 0.0 for k in nutrient_keys}
        day_cost = 0.0
        for s_idx, slot in enumerate(slots):
            for i, c in enumerate(candidates):
                if (d, s_idx, i) not in x:
                    continue
                if solver.Value(x[d, s_idx, i]) == 1:
                    units = solver.Value(u[d, s_idx, i])
                    portion = units * UNIT_G
                    items.append({
                        "day_index": d, "meal_date": dates[d] if d < len(dates) else "",
                        "slot": slot, "dish_id": c.dish_id, "dish_name": c.name,
                        "portion_g": portion,
                        "cost": round(c.cost_per_unit * units, 2),
                        "dish_type": c.dish_type,
                        "locked": (d, slot, c.dish_id) in locked_by_key,
                    })
                    for k in nutrient_keys:
                        dn[k] += c.per_unit[k] * units
                    day_cost += c.cost_per_unit * units
                    dish_count[c.dish_id] = dish_count.get(c.dish_id, 0) + 1
        daily_nutrients.append({k: round(v, 1) for k, v in dn.items()})
        daily_costs.append(round(day_cost, 2))

    # 得分拆解（用真实值重算，保证报告指标一致）
    bd = _score_breakdown(daily_nutrients, daily_costs, items, targets,
                          weights, candidates, dish_count, days)
    if relaxations:
        warnings = precheck_msgs + warnings
    status_name = "optimal" if day_nut_var else "feasible"
    return SolveResult(
        status=status_name, objective=round(solver.ObjectiveValue(), 2),
        items=items, daily_nutrients=daily_nutrients,
        daily_costs=daily_costs, total_cost=round(sum(daily_costs), 2),
        score_breakdown=bd, relaxations=relaxations,
        solve_seconds=round(time.time() - t0, 2),
        candidate_count=len(candidates), warnings=warnings,
    )


def _score_breakdown(daily_nutrients, daily_costs, items, targets,
                     weights, candidates, dish_count, days) -> dict:
    cand_by_id = {c.dish_id: c for c in candidates}
    nut_dev = 0.0
    nut_detail = {}
    for k in OBJECTIVE_NUTRIENTS:
        if k not in targets:
            continue
        lo, hi = targets[k]
        mid = max((lo + hi) / 2, 1e-6)
        dev_pct_days = []
        for dn in daily_nutrients:
            v = dn[k]
            dmg = max(0.0, lo - v, v - hi)
            dev_pct_days.append(dmg / mid * 100.0)
        avg_dev = sum(dev_pct_days) / len(dev_pct_days)
        nut_detail[k] = round(avg_dev, 1)
        nut_dev += avg_dev
    waste = sum(cand_by_id[i["dish_id"]].waste_rate * i["portion_g"]
                for i in items if i["dish_id"] in cand_by_id)
    sat = sum(cand_by_id[i["dish_id"]].preference_score for i in items) / max(len(items), 1)
    repeats = sum(n - 1 for n in dish_count.values() if n > 1)
    risk_hits = sum(1 for i in items if cand_by_id.get(i["dish_id"]) and
                    cand_by_id[i["dish_id"]].risk_tags)
    return {
        "avg_nutrient_deviation_pct": round(nut_dev / max(len(OBJECTIVE_NUTRIENTS), 1), 1),
        "nutrient_deviation_by_key_pct": nut_detail,
        "total_cost": round(sum(daily_costs), 2),
        "avg_day_cost": round(sum(daily_costs) / max(days, 1), 2),
        "waste_g_est": round(waste, 0),
        "avg_satisfaction": round(sat, 2),
        "repeat_extra_count": repeats,
        "risk_tag_hits": risk_hits,
        "distinct_dishes": len(dish_count),
        "total_items": len(items),
    }
