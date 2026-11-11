"""Dashboard analytics endpoints (every value comes from the database)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.schemas import DashboardSummary
from app.services import analytics_service as analytics

router = APIRouter(
    prefix="/api/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)]
)


def common_filters(
    db: Session = Depends(get_db),
    start: date | None = Query(default=None, description="YYYY-MM-DD"),
    end: date | None = Query(default=None, description="YYYY-MM-DD"),
    store: str | None = Query(default=None),
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
):
    return start, end, store, category, region


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db), filters=Depends(common_filters)) -> dict:
    return analytics.dashboard_summary(db, *filters)


@router.get("/sales-trend")
def sales_trend(
    granularity: str = Query(default="day", pattern="^(day|month)$"),
    db: Session = Depends(get_db),
    filters=Depends(common_filters),
) -> dict:
    return {"granularity": granularity, "points": analytics.sales_trend(db, *filters, granularity)}


@router.get("/product-performance")
def product_performance(
    top: int = Query(default=10, ge=1, le=50),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    filters=Depends(common_filters),
) -> dict:
    return {
        "items": analytics.product_performance(
            db, *filters, top=top, ascending=(order == "asc")
        ),
        "order": "best_selling" if order == "desc" else "low_selling",
    }


@router.get("/category-performance")
def category_performance(db: Session = Depends(get_db), filters=Depends(common_filters)) -> dict:
    return {"items": analytics.category_performance(db, *filters)}


@router.get("/store-performance")
def store_performance(db: Session = Depends(get_db), filters=Depends(common_filters)) -> dict:
    return {"items": analytics.store_performance(db, *filters)}


@router.get("/inventory-overview")
def inventory_overview(db: Session = Depends(get_db), filters=Depends(common_filters)) -> dict:
    return {"items": analytics.inventory_overview(db, *filters)}


@router.get("/actual-vs-predicted")
def actual_vs_predicted(db: Session = Depends(get_db), filters=Depends(common_filters)) -> dict:
    return {
        "note": "Predictions are shown only where predictions exist in the database; "
        "a prediction is never treated as an actual result.",
        "points": analytics.actual_vs_predicted(db, *filters),
    }


@router.get("/filters")
def filter_values(db: Session = Depends(get_db)) -> dict:
    return analytics.distinct_values(db)
