"""报告导出路由：PDF / Excel / 采购清单 / 方案对比。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import Session

from ..database import get_session
from ..models import User, MealPlan
from ..services import reports
from ..services import audit
from .deps import get_current_user

router = APIRouter(prefix="/api/reports", tags=["报告导出"])


def _check(plan_id: int, session: Session):
    p = session.get(MealPlan, plan_id)
    if not p:
        raise HTTPException(404, "方案不存在")
    return p


@router.get("/plans/{plan_id}/pdf")
def plan_pdf(plan_id: int, session: Session = Depends(get_session),
             user: User = Depends(get_current_user)):
    _check(plan_id, session)
    data = reports.render_plan_pdf(session, plan_id)
    audit.log(session, user.username, "report.export_pdf", "plan", plan_id)
    return Response(content=data, media_type="application/pdf",
                    headers={"Content-Disposition":
                             f'attachment; filename="plan-{plan_id}.pdf"'})


@router.get("/plans/{plan_id}/excel")
def plan_excel(plan_id: int, session: Session = Depends(get_session),
               user: User = Depends(get_current_user)):
    _check(plan_id, session)
    data = reports.render_plan_excel(session, plan_id)
    audit.log(session, user.username, "report.export_excel", "plan", plan_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 f'attachment; filename="plan-{plan_id}.xlsx"'})


@router.get("/plans/{plan_id}/purchase")
def plan_purchase(plan_id: int, session: Session = Depends(get_session),
                  _: User = Depends(get_current_user)):
    _check(plan_id, session)
    rows = reports.purchase_summary(session, plan_id)
    total_cost = round(sum(r["cost"] for r in rows), 2)
    total_g = round(sum(r["gross_g"] for r in rows), 0)
    return {"plan_id": plan_id, "items": rows,
            "total_gross_g": total_g, "total_ingredient_cost": total_cost,
            "note": "采购建议仅为需求汇总清单，不含仓库库存管理"}


@router.get("/compare/excel")
def compare_excel(plan_ids: str = Query(..., description="逗号分隔的方案ID"),
                  session: Session = Depends(get_session),
                  user: User = Depends(get_current_user)):
    ids = [int(x) for x in plan_ids.split(",") if x.strip()]
    if not 2 <= len(ids) <= 6:
        raise HTTPException(400, "请提供 2~6 个方案ID进行对比")
    data = reports.render_compare_excel(session, ids)
    audit.log(session, user.username, "report.compare_excel", "plan",
              ",".join(map(str, ids)))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition":
                 'attachment; filename="plan-compare.xlsx"'})
