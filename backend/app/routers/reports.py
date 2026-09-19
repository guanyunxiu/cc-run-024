"""报告导出与采购汇总路由。"""
from fastapi import APIRouter, Depends
from fastapi.responses import Response, StreamingResponse
from sqlmodel import Session
import io

from ..database import get_session
from ..deps import audit, get_current_user
from ..models import MenuPlan, User
from ..reports import build_report, export_excel, export_pdf, procurement_list
from ..solver import NUTRIENTS, NUT_LABELS

router = APIRouter(prefix="/api/reports", tags=["报告导出"])


def _load_plan(session: Session, plan_id: int) -> MenuPlan:
    from fastapi import HTTPException
    p = session.get(MenuPlan, plan_id)
    if not p:
        raise HTTPException(404, "方案不存在")
    return p


@router.get("/plan/{plan_id}")
def report_data(plan_id: int, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    """报告页结构化数据（营养雷达、日趋势、KPI）。"""
    plan = _load_plan(session, plan_id)
    rep = build_report(session, plan)
    radar = [{"name": rep["plan"].name,
              "values": [rep["score"].get("attainment", {}).get(n, 0) for n in NUTRIENTS]}]
    trend = []
    for d in range(plan.days):
        dt = rep["day_totals"].get(str(d), {})
        trend.append({"day": f"第{d+1}天", "date": rep["dates"][d],
                      **{n: round(dt.get(n, 0), 1) for n in
                         ("energy_kcal", "protein_g", "sodium_mg",
                          "potassium_mg", "phosphorus_mg", "fiber_g")},
                      "cost": round(dt.get("cost", 0), 2)})
    return {"report_meta": {
                "plan_name": plan.name, "resident": rep["resident"].name,
                "dates": rep["dates"], "score": rep["score"],
                "rule_version": rep["rule_version"],
                "solver_params": rep["solver_params"],
                "assumptions": rep["assumptions"],
                "conflicts_calc": rep["conflicts_calc"],
                "soft_violations": rep["soft_violations"],
                "warnings": rep["warnings"],
            },
            "nutrients": NUTRIENTS,
            "nut_labels": NUT_LABELS,
            "radar": radar, "trend": trend,
            "targets": rep["targets"], "day_totals": rep["day_totals"]}


@router.get("/plan/{plan_id}/pdf")
def report_pdf(plan_id: int, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    plan = _load_plan(session, plan_id)
    pdf = export_pdf(session, plan)
    audit(session, user, "export", "plan_pdf", plan_id)
    session.commit()
    fname = f"mealplan_{plan_id}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{fname}"'})


@router.get("/plan/{plan_id}/excel")
def report_excel(plan_id: int, session: Session = Depends(get_session),
                 user: User = Depends(get_current_user)):
    plan = _load_plan(session, plan_id)
    data = export_excel(session, plan)
    audit(session, user, "export", "plan_excel", plan_id)
    session.commit()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="mealplan_{plan_id}.xlsx"'})


@router.get("/plan/{plan_id}/procurement")
def procurement(plan_id: int, session: Session = Depends(get_session),
                user: User = Depends(get_current_user)):
    plan = _load_plan(session, plan_id)
    return procurement_list(session, plan)
