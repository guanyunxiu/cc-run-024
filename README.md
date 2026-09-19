# 老年营养与慢病配餐优化管理系统

根据老人 **慢病、过敏、吞咽等级（IDDSI）、营养目标、成本约束**，用 **Google OR-Tools CP-SAT** 自动生成每日/每周配餐方案，满足硬约束并对营养偏差、成本、浪费、满意度、多样性等多目标进行优化。

## 一、核心能力

| 模块 | 说明 |
| --- | --- |
| 老人档案与营养目标 | 基本信息/慢病/过敏/吞咽/忌口/宗教/活动量/体重/目标；按多病共存计算能量、蛋白、钠、钾、磷、纤维等个体化目标，**记录冲突与折衷依据** |
| 菜品营养库 | 食材（可食部、每100g营养、单价、标签、过敏原）→ 菜品配方（投料毛重、烹饪损失）→ **自动换算成品营养与成本** |
| 禁忌规则 | 过敏原 / 慢病 / 药物-食物交互 / IDDSI / 宗教；**JSON 规则表 + Python 校验函数**；带版本、优先级、硬/软级别、临床依据解释 |
| 配餐求解 | OR-Tools CP-SAT；硬约束=合规、餐次槽位、锁定、日成本、重复频率（候选池自适应）；软目标=营养偏差、软规则、忌口、满意度、浪费、成本、多样性；不可行时自动松弛并告警 |
| 排餐日历与版本 | 日/周排餐、草稿/发布/归档、版本快照、版本对比、一键回滚；数据库版本号**乐观锁**防并发覆盖 |
| 手动调整 | dnd-kit 拖拽换菜、锁定菜品、实时硬/软冲突高亮（红/黄）、锁定项参与下一次**局部重求解** |
| 报告与审计 | 营养雷达、每日趋势、方案对比、软约束解释；**后端生成 PDF（WeasyPrint）与 Excel（OpenPyXL）**；采购需求汇总（只汇总需求，不做库存）；完整操作日志、规则版本、求解器参数记录 |

## 二、技术栈

- **后端**：Python · FastAPI · Pydantic · SQLModel · SQLite（单文件）· Google OR-Tools CP-SAT · WeasyPrint · OpenPyXL · FastAPI BackgroundTasks · JWT · pytest + Hypothesis
- **前端**：React 18 + TypeScript + Vite · Ant Design 5 · ECharts · FullCalendar · dnd-kit · TanStack Query · Zustand · React Hook Form + Zod

## 三、登录账号（开箱即用）

| 角色 | 用户名 | 密码 | 权限 |
| --- | --- | --- | --- |
| 系统管理员 | `admin` | `Admin@2026` | 全部，含删除/停用 |
| 营养师 | `dietitian` | `Nutri@2026` | 档案/菜品/规则/排餐的增改与发布 |
| 只读查看员 | `viewer` | `View@2026` | 仅查看与导出 |

> 首次启动自动初始化 SQLite 并写入种子数据：3 个用户、14 条规则、约 70 种食材、84 道菜品配方、6 位典型多病共存老人。

## 四、快速启动

### 方式 A：一键启动（推荐，后端同时托管前端）

```bash
cd backend
pip install -r requirements.txt          # 首次
bash run.sh                              # 初始化种子库 + 启动，监听 http://localhost:8000
```

浏览器打开 **http://localhost:8000** ，用上方账号登录即可。

### 方式 B：前后端分离开发（热更新）

```bash
# 终端 1 - 后端（:8000）
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 终端 2 - 前端（:5173，已配置 /api 代理到 8000）
cd frontend && npm install && npm run dev
```

访问 http://localhost:5173 。

### 重新生成数据库

删除 `backend/app/mealplan.db` 后重启即可重新播种。

## 五、测试

```bash
cd backend
python -m pytest tests/ -q
# 覆盖：营养目标（含 Hypothesis 属性测试）、规则引擎、配方换算、
#       求解器硬约束可行性/锁定/局部重算/预算、API 全链路、PDF/Excel 导出
```

## 六、使用流程

1. **老人档案**：维护慢病/过敏/IDDSI/宗教/用药 → 系统实时计算营养目标并解释多病共存冲突。
2. **菜品/食材库**：维护配方，营养与成本自动换算；可选择老人预览每道菜的合规性。
3. **禁忌规则**：查看/维护规则版本与优先级（无复杂规则引擎，JSON + Python 分派）。
4. **排餐方案**：新建日/周方案 → 后台 CP-SAT 求解并轮询进度 → 拖拽换菜/锁定 → 实时冲突高亮 → 局部重算 → 发布。
5. **版本**：多次发布形成快照，可逐槽位对比并回滚。
6. **报告**：查看雷达/趋势 → 导出 PDF / Excel → 查看采购需求汇总。
7. **操作日志**：所有写操作与导出均有审计记录。

## 七、目录结构

```
backend/
  app/
    main.py            # FastAPI 入口（含 SPA 托管）
    config.py          # 全局配置（活动系数、IDDSI、餐次）
    models.py          # SQLModel 表结构（含乐观锁 version、JSON 字段）
    schemas.py         # Pydantic 请求模型
    nutrition.py       # 个体化营养目标 + 多病共存冲突
    rules.py           # 规则引擎（JSON 规则表 + Python 校验）
    recipe.py          # 食材→成品营养/成本换算
    solver.py          # OR-Tools CP-SAT 求解器
    plan_service.py    # 方案/锁定/发布/回滚/快照
    tasks.py           # 后台求解任务
    reports.py         # PDF / Excel / 采购汇总
    seed.py            # 种子数据
    routers/           # API 路由
  assets/fonts/        # PDF 中文字体
  tests/               # pytest + Hypothesis
frontend/src/
  pages/ components/ api/ store/ lib/
```

## 八、求解器建模摘要

- 决策变量：`x[day, slot, line, dish] ∈ {0,1}`，每个餐次槽位 ExactlyOne。
- 候选生成阶段用规则引擎剔除所有硬违规菜品（过敏/慢病/IDDSI/宗教/药物硬规则）。
- 硬约束：日成本上限、周内重复频率（按类别 + 候选池自适应）、锁定菜品固定。
- 软目标（加权最大化）：营养上下限松弛惩罚（量纲归一化）、软规则违规、忌口、浪费率、成本、喜好度奖励、多样性奖励、重复惩罚。
- 两阶段：严格模型不可行 → 自动放宽成本（+25%/+50%）与重复上限再求解，并在界面/报告中给出告警。
