"""CP-SAT 配餐求解器。

硬约束：菜品合规（过敏/慢病/吞咽/宗教/药物硬规则在候选生成时过滤）、
        每槽位恰好一道菜、锁定菜品、每日成本上限、重复频率。
软目标：营养偏差、软规则违规、忌口、满意度、浪费、成本、多样性。
两阶段：严格模型不可行时自动松弛（成本上浮、重复上限放宽）并给出告警。
"""
import math
import time
from collections import defaultdict

from ortools.sat.python import cp_model

from .rules import evaluate_dish

NUTRIENTS = [
    "energy_kcal", "protein_g", "fat_g", "carb_g", "sodium_mg",
    "potassium_mg", "phosphorus_mg", "fiber_g", "calcium_mg",
]
NUT_LABELS = {
    "energy_kcal": "能量(kcal)", "protein_g": "蛋白质(g)", "fat_g": "脂肪(g)",
    "carb_g": "碳水(g)", "sodium_mg": "钠(mg)", "potassium_mg": "钾(mg)",
    "phosphorus_mg": "磷(mg)", "fiber_g": "纤维(g)", "calcium_mg": "钙(mg)",
}
# 营养量纲归一化尺度（用于不同量纲目标加权）
NUT_SCALE = {
    "energy_kcal": 200, "protein_g": 12, "fat_g": 15, "carb_g": 30,
    "sodium_mg": 500, "potassium_mg": 500, "phosphorus_mg": 150,
    "fiber_g": 5, "calcium_mg": 250,
}

# 餐次槽位 → [(line, 允许菜品类别)]
SLOT_LINES = {
    "breakfast": [
        ("staple", {"staple"}),
        ("protein", {"egg", "soy", "dairy", "entree"}),
        ("vegetable", {"vegetable"}),
    ],
    "morning_snack": [("snack", {"snack", "fruit", "dairy"})],
    "lunch": [
        ("staple", {"staple"}),
        ("entree", {"entree", "egg", "soy"}),
        ("vegetable", {"vegetable"}),
        ("soup", {"soup"}),
    ],
    "afternoon_snack": [("snack", {"snack", "fruit", "dairy", "soy"})],
    "dinner": [
        ("staple", {"staple"}),
        ("entree", {"entree", "egg", "soy"}),
        ("vegetable", {"vegetable"}),
        ("soup", {"soup"}),
    ],
}

# 7 天内同一菜品最大出现次数（按类别）
WEEKLY_CAP = {
    "staple": 9, "entree": 3, "vegetable": 5, "soup": 4,
    "egg": 4, "soy": 4, "snack": 3, "fruit": 5, "dairy": 5,
}

OBJ_SCALE = 1_000_000  # 目标函数整数放大倍数（CP-SAT 仅接受整数系数）

DEFAULT_WEIGHTS = {
    "nutrient": 100,     # 每归一化偏差单位
    "soft_rule": 300,    # 每次软规则违规
    "dislike": 120,
    "satisfaction": 25,
    "waste": 100,
    "cost": 2,           # 每元
    "diversity": 15,     # 每道不同菜品
    "repeat": 8,         # 第 2 次起每次重复
}


def _scale_cap(cat: str, days: int) -> int:
    return max(1, math.ceil(WEEKLY_CAP.get(cat, 3) * days / 7))


def build_candidates(dishes: list, resident, rules: list) -> dict:
    """返回 {dish_id: {eligible, soft: [...]}}，只保留 active 菜品。"""
    result = {}
    for d in dishes:
        if not getattr(d, "active", True):
            continue
        ev = evaluate_dish(d, resident, rules)
        if ev["eligible"]:
            result[d.id] = {"dish": d, "soft": ev["soft"]}
    return result


def solve_menu(resident, dishes, rules, targets: dict, days: int,
               budget_per_day: float, locks: dict | None = None,
               weights: dict | None = None, time_limit_sec: int = 20,
               allowed_days: set | None = None) -> dict:
    """求解。

    locks: {(day_index, slot, line): dish_id}  锁定的槽位
    allowed_days: 只求解这些天（局部重算）；None 表示全部。其余天沿用 locks。
    """
    t0 = time.time()
    locks = locks or {}
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    candidates = build_candidates(dishes, resident, rules)
    dislike_tags = set(resident.dislikes or [])

    warnings_list: list[str] = []
    relax_round = 0

    def run_model(relax: int):
        model = cp_model.CpModel()
        x = {}   # (day, slot, line, dish_id) -> BoolVar
        cells = []
        empty_cells = []

        for day in range(days):
            if allowed_days is not None and day not in allowed_days:
                continue
            for slot, lines in SLOT_LINES.items():
                for line, cats in lines:
                    locked_dish = locks.get((day, slot, line))
                    pool = []
                    if locked_dish is not None and locked_dish in candidates and \
                            candidates[locked_dish]["dish"].category in cats:
                        pool = [locked_dish]
                    elif locked_dish is not None:
                        # 锁定菜已不合规（如档案变更），告警并忽略
                        warnings_list.append(
                            f"第{day+1}天{slot}/{line} 锁定菜品(id={locked_dish})"
                            f"已不符合当前规则，重新选择")
                        pool = [did for did, c in candidates.items()
                                if c["dish"].category in cats]
                    else:
                        pool = [did for did, c in candidates.items()
                                if c["dish"].category in cats]
                    if not pool:
                        empty_cells.append((day, slot, line))
                        continue
                    vars_ = []
                    for did in pool:
                        b = model.NewBoolVar(f"x_{day}_{slot}_{line}_{did}")
                        x[(day, slot, line, did)] = b
                        vars_.append(b)
                    model.AddExactlyOne(vars_)
                    if locked_dish in pool:
                        model.Add(x[(day, slot, line, locked_dish)] == 1)
                    cells.append((day, slot, line, pool))

        if empty_cells:
            return None, None, x, empty_cells

        # ---- 每日成本上限（硬约束，松弛时上浮） ----
        bud = budget_per_day * (1 + 0.25 * relax)
        for day in range(days):
            if allowed_days is not None and day not in allowed_days:
                continue
            cost_terms = []
            for (d_, slot, line, did), b in x.items():
                if d_ == day:
                    cost_terms.append(b * int(round(candidates[did]["dish"].cost * 100)))
            if cost_terms:
                model.Add(sum(cost_terms) <= int(round(bud * 100)))

        # ---- 重复频率（候选池自适应；松弛轮放宽） ----
        n_days_scope = len(allowed_days) if allowed_days else days
        # 每个 line 的槽位需求与候选池大小
        demand_by_line: dict[str, int] = defaultdict(int)
        pool_by_line: dict[str, set] = defaultdict(set)
        for day, slot, line, pool in cells:
            demand_by_line[line] += 1
            pool_by_line[line].update(pool)
        by_dish = defaultdict(list)
        for (day, slot, line, did), b in x.items():
            by_dish[did].append(b)
        for did, bs in by_dish.items():
            cat = candidates[did]["dish"].category
            base_cap = _scale_cap(cat, n_days_scope)
            # 自适应：各 line 均衡分配时，该菜至多承担 Σceil(需求/候选数)，
            # 保证吞咽受限等小候选池场景仍可行
            forced = 0
            for line, pool in pool_by_line.items():
                if did in pool:
                    forced += math.ceil(demand_by_line[line] / max(len(pool), 1))
            cap = max(base_cap, forced) + 2 * relax
            model.Add(sum(bs) <= cap)

        # ---- 营养偏差软约束（按天） ----
        # CP-SAT 只接受整数线性表达式：用统一放大倍数得到归一化整数系数
        M = OBJ_SCALE
        obj_terms = []
        day_nut_expr = {}
        for day in range(days):
            if allowed_days is not None and day not in allowed_days:
                continue
            for nut in NUTRIENTS:
                terms = []
                for (d_, slot, line, did), b in x.items():
                    if d_ != day:
                        continue
                    val = int(round(getattr(candidates[did]["dish"], nut) * 100))
                    if val:
                        terms.append(b * val)
                expr = sum(terms) if terms else 0
                day_nut_expr[(day, nut)] = expr
                spec = (targets or {}).get(nut) or {}
                lo = spec.get("min")
                hi = spec.get("max")
                coef = w["nutrient"] * M // (NUT_SCALE[nut] * 100)
                if lo is not None:
                    s = model.NewIntVar(0, 10**9, f"sl_{day}_{nut}_lo")
                    model.Add(expr + s >= int(round(lo * 100)))
                    obj_terms.append(-coef * s)
                if hi is not None:
                    s = model.NewIntVar(0, 10**9, f"sl_{day}_{nut}_hi")
                    model.Add(expr - s <= int(round(hi * 100)))
                    obj_terms.append(-coef * s)

        # ---- 菜品级软目标 ----
        for (day, slot, line, did), b in x.items():
            dish = candidates[did]["dish"]
            pen = 0
            pen += w["soft_rule"] * M * len(candidates[did]["soft"])
            pen += w["dislike"] * M * len(set(dish.tags or []) & dislike_tags)
            pen += int(w["waste"] * M * float(dish.waste_index or 0))
            pen += (w["cost"] * M // 100) * int(round(dish.cost * 100))
            bonus = w["satisfaction"] * M * int(round(float(dish.satisfaction or 3) - 3))
            if pen:
                obj_terms.append(-pen * b)
            if bonus:
                obj_terms.append(bonus * b)

        # ---- 多样性：出现即奖励；第 2 次起计重复惩罚 ----
        for did, bs in by_dish.items():
            y = model.NewBoolVar(f"used_{did}")
            model.AddMaxEquality(y, bs)
            obj_terms.append(w["diversity"] * M * y)
            if len(bs) > 1:
                obj_terms.append(-w["repeat"] * M * (sum(bs) - 1))

        model.Maximize(sum(obj_terms))
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit_sec)
        solver.parameters.num_search_workers = 4
        status = solver.Solve(model)
        return solver, status, x, []

    solver = status = x = None
    for relax in range(3):
        relax_round = relax
        solver, status, x, empty = run_model(relax)
        if empty:
            return {
                "status": "failed",
                "error": "以下餐次无合规菜品可选：" +
                         "；".join(f"第{d+1}天 {s}/{l}" for d, s, l in empty[:8]) +
                         "。请扩充菜品库或调整老人吞咽/禁忌等级。",
            }
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            if relax == 1:
                warnings_list.append("严格成本约束不可行，已按预算上浮 25% 求解，请复核成本。")
            elif relax == 2:
                warnings_list.append("已同时放宽成本（+50%）与重复频率后求得可行方案，请人工复核。")
            break
        if relax == 0:
            warnings_list.append("严格模型不可行，尝试松弛成本与重复约束……")
    else:
        return {"status": "failed", "error": "求解器未能找到可行方案，请检查菜品库覆盖度或放宽约束。"}

    # ---- 解析结果 ----
    chosen = []   # (day, slot, line, dish_id)
    for (day, slot, line, did), b in x.items():
        if solver.Value(b) == 1:
            chosen.append((day, slot, line, did))

    # 合并锁定但不在本轮变量中的槽位（局部重算时其他天）
    for (day, slot, line), did in locks.items():
        if not any(c[:3] == (day, slot, line) for c in chosen):
            chosen.append((day, slot, line, did))

    dish_by_id = {d.id: d for d in dishes}
    return _assemble_result(chosen, dish_by_id, candidates, targets, days,
                            budget_per_day, solver, status, warnings_list,
                            time.time() - t0, locks, OBJ_SCALE)


def _assemble_result(chosen, dish_by_id, candidates, targets, days,
                     budget_per_day, solver, status, warnings_list,
                     elapsed, locks, m_scale: int = 1) -> dict:
    items = []
    day_totals = {d: defaultdict(float) for d in range(days)}
    overall = defaultdict(float)
    soft_violations = []
    sat_sum, sat_n, waste_sum = 0.0, 0, 0.0

    chosen.sort(key=lambda c: (c[0], list(SLOT_LINES).index(c[1]), c[2]))
    for day, slot, line, did in chosen:
        dish = dish_by_id.get(did)
        if dish is None:
            continue
        items.append({
            "day_index": day, "slot": slot, "line": line,
            "dish_id": did, "dish_name": dish.name,
            "category": dish.category,
            "locked": (day, slot, line) in locks,
        })
        for nut in NUTRIENTS:
            v = getattr(dish, nut, 0.0) or 0.0
            day_totals[day][nut] += v
            overall[nut] += v
        day_totals[day]["cost"] += dish.cost
        overall["cost"] += dish.cost
        sat_sum += float(dish.satisfaction or 3)
        waste_sum += float(dish.waste_index or 0) * dish.cost
        sat_n += 1
        for sv in candidates.get(did, {}).get("soft", []):
            soft_violations.append({"day_index": day, "slot": slot,
                                    "dish_name": dish.name, **sv})

    # ---- 营养达标率 ----
    attainment = {}
    avg_day = {nut: overall[nut] / days for nut in NUTRIENTS}
    for nut, spec in (targets or {}).items():
        if not spec:
            continue
        val = avg_day.get(nut, 0.0)
        lo, hi, tgt = spec.get("min"), spec.get("max"), spec.get("target")
        if lo is not None and hi is not None:
            ratio = 1.0 if lo <= val <= hi else min(val, hi) / max(lo, 1e-6)
        elif hi is not None:
            ratio = 1.0 if val <= hi else max(0.0, hi / max(val, 1e-6))
        elif lo is not None:
            ratio = min(1.0, val / max(lo, 1e-6))
        else:
            ratio = 1.0
        attainment[nut] = round(max(0.0, min(1.0, ratio)) * 100, 1)

    distinct = len({i["dish_id"] for i in items})
    score = {
        "objective": round(solver.ObjectiveValue() / max(m_scale, 1), 1) if solver else None,
        "avg_attainment_pct": round(sum(attainment.values()) /
                                    max(len(attainment), 1), 1),
        "attainment": attainment,
        "avg_satisfaction": round(sat_sum / max(sat_n, 1), 2),
        "estimated_waste_cost": round(waste_sum, 2),
        "total_cost": round(overall["cost"], 2),
        "avg_cost_per_day": round(overall["cost"] / days, 2),
        "distinct_dishes": distinct,
        "soft_violation_count": len(soft_violations),
        "status": "optimal" if status is not None and
                  solver and solver.StatusName(status) == "OPTIMAL" else "feasible",
        "solve_time_sec": round(elapsed, 2),
    }

    return {
        "status": "success",
        "items": items,
        "day_totals": {str(d): {k: round(v, 2) for k, v in t.items()}
                       for d, t in day_totals.items()},
        "totals": {k: round(v, 2) for k, v in overall.items()},
        "score": score,
        "attainment": attainment,
        "soft_violations": soft_violations,
        "warnings": warnings_list,
        "nut_labels": NUT_LABELS,
    }
