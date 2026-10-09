from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.plans import PLAN_LIMITS
from backend.app.models import Plan, PlanKind

router = APIRouter(tags=["plans"])


def _limits(code: str, overrides: dict | None) -> dict:
    defaults = PLAN_LIMITS.get(code, {})
    merged = {**defaults, **(overrides or {})}
    return {"applications_per_month": merged.get("applications_per_month", 0), "resumes": merged.get("resumes", 0)}


@router.get("/plans", summary="Public plan catalogue (pricing page)")
def list_plans(db: Session = Depends(get_db)):
    rows = db.scalars(select(Plan).where(Plan.is_active.is_(True), Plan.kind == PlanKind.PERSONAL)
                      .order_by(Plan.sort_order, Plan.price_cents)).all()
    if rows:
        plans = [{"code": p.code, "name": p.name, "price_cents": p.price_cents, "currency": p.currency,
                  "interval": p.interval, "limits": _limits(p.code, p.limits)} for p in rows]
    else:
        # Until the plans table is seeded, serve the defaults from the single catalogue.
        plans = [{"code": code, "name": p["name"], "price_cents": p["price_cents"], "currency": "INR",
                  "interval": "month", "limits": _limits(code, None)}
                 for code, p in PLAN_LIMITS.items() if p.get("kind", "personal") == "personal"]
    return ok({"plans": plans})
