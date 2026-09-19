"""数据库种子初始化：账号、食材、菜品（含配方聚合）、规则版本、演示老人。

用法: python -m app.seed            # 仅空库时初始化
      python -m app.seed --reset    # 删除数据库重建
"""
import json
import sys
from datetime import date
from pathlib import Path

from sqlmodel import select

from .database import engine, init_db, new_session
from .models import User, Ingredient, Dish, RecipeItem, Elder, Rule, RuleVersion
from .core.security import hash_password
from .core.nutrition import compute_targets
from .services.foodlib import refresh_dish_nutrition

DATA_DIR = Path(__file__).parent / "data"


def _load(name):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def seed_users(s):
    if s.exec(select(User)).first():
        return
    users = [
        User(username="admin", hashed_password=hash_password("admin123"),
             full_name="系统管理员", role="admin"),
        User(username="nutritionist", hashed_password=hash_password("nutri123"),
             full_name="林营养师", role="nutritionist"),
    ]
    s.add_all(users)
    s.commit()
    print("  账号: admin/admin123, nutritionist/nutri123")


def seed_foods(s):
    if s.exec(select(Ingredient)).first():
        return
    ings = _load("seed_ingredients.json")
    ing_by_code: dict[str, Ingredient] = {}
    for row in ings:
        ing = Ingredient(**row)
        s.add(ing)
        ing_by_code[row["code"]] = ing
    s.commit()
    print(f"  食材: {len(ings)} 种")

    dishes = _load("seed_dishes.json")
    n = 0
    for row in dishes:
        recipe = row.pop("recipe", [])
        tags_extra = row.pop("tags", "")
        d = Dish(**row, tags=tags_extra)
        s.add(d)
        s.commit()
        s.refresh(d)
        for r in recipe:
            ing = ing_by_code.get(r["ing"])
            if not ing or r.get("gross_weight_g", 0) <= 0:
                continue
            s.add(RecipeItem(dish_id=d.id, ingredient_id=ing.id,
                             gross_weight_g=r["gross_weight_g"],
                             cooking_loss_rate=r.get("loss", 0.0)))
        s.commit()
        refresh_dish_nutrition(s, d)
        s.commit()
        n += 1
    print(f"  菜品: {n} 道（营养与成本已按配方聚合）")


def seed_rules(s):
    if s.exec(select(RuleVersion)).first():
        return
    data = _load("seed_rules.json")
    from datetime import datetime
    rv = RuleVersion(version=data["version"], status="published",
                     note=data["note"], published_at=datetime.now())
    s.add(rv)
    s.commit()
    s.refresh(rv)
    for r in data["rules"]:
        cond = r.pop("condition")
        s.add(Rule(version_id=rv.id, condition_json=json.dumps(cond, ensure_ascii=False), **r))
    s.commit()
    print(f"  规则版本 {data['version']}: {len(data['rules'])} 条")


def _make_elder(s, **kw):
    overrides = kw.pop("target_overrides", None)
    e = Elder(**kw)
    diseases = [x.strip() for x in e.chronic_diseases.split(",") if x.strip()]
    tr = compute_targets(
        birth_date=e.birth_date, gender=e.gender, height_cm=e.height_cm,
        weight_kg=e.weight_kg, activity_level=e.activity_level,
        chronic_diseases=diseases, nutrition_goal=e.nutrition_goal,
        target_overrides=overrides or {})
    e.target_overrides = json.dumps(overrides or {}, ensure_ascii=False)
    e.target_explanation = json.dumps(tr.as_dict(), ensure_ascii=False)
    s.add(e)
    s.commit()


def seed_elders(s):
    if s.exec(select(Elder)).first():
        return
    _make_elder(s,
        name="张德福", gender="male", birth_date=date(1942, 3, 15),
        height_cm=168, weight_kg=72, activity_level="light",
        chronic_diseases="hypertension,diabetes2",
        allergies="", iddsi_level=6, dislikes="香菜;动物内脏",
        religion="none", medications="", nutrition_goal="lose",
        cost_limit_day=38.0)
    _make_elder(s,
        name="李秀兰", gender="female", birth_date=date(1939, 7, 22),
        height_cm=155, weight_kg=43, activity_level="sedentary",
        chronic_diseases="ckd,sarcopenia,osteoporosis",
        allergies="egg", iddsi_level=5, dislikes="羊肉",
        religion="none", medications="acei", nutrition_goal="malnutrition",
        cost_limit_day=45.0)
    _make_elder(s,
        name="王桂英", gender="female", birth_date=date(1945, 11, 2),
        height_cm=158, weight_kg=55, activity_level="light",
        chronic_diseases="",
        allergies="peanut", iddsi_level=7, dislikes="",
        religion="buddhist", medications="", nutrition_goal="maintain",
        cost_limit_day=30.0)
    _make_elder(s,
        name="刘建国", gender="male", birth_date=date(1948, 1, 9),
        height_cm=170, weight_kg=78, activity_level="sedentary",
        chronic_diseases="gout,dyslipidemia,hypertension",
        allergies="seafood", iddsi_level=6, dislikes="",
        religion="none", medications="warfarin", nutrition_goal="lose",
        cost_limit_day=42.0)
    print("  演示老人: 张德福、李秀兰、王桂英、刘建国")


def main():
    reset = "--reset" in sys.argv
    db_file = engine.url.database
    if reset:
        if db_file:
            p = Path(db_file)
            if p.exists():
                p.unlink()
        print("已删除旧数据库")
    if db_file:
        Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    init_db()
    with new_session() as s:
        print("开始种子初始化...")
        seed_users(s)
        seed_foods(s)
        seed_rules(s)
        seed_elders(s)
        print("种子数据就绪。")


if __name__ == "__main__":
    main()
