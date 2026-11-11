"""Replenishment recommendation endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.entities import InventoryRecord, Prediction
from app.schemas import ReorderRecommendation, ReorderConfig
from app.services import recommendation_service

router = APIRouter(
    prefix="/api/recommendations", tags=["recommendations"], dependencies=[Depends(get_current_user)]
)


def _config(
    lead_time_days: float = Query(default=7, ge=0, le=365),
    service_level: float = Query(default=0.95, gt=0.5, lt=0.9999),
    reorder_threshold_days: float = Query(default=3, ge=0, le=365),
    limit: int = Query(default=200, ge=1, le=500),
) -> ReorderConfig:
    return ReorderConfig(
        lead_time_days=lead_time_days,
        service_level=service_level,
        reorder_threshold_days=reorder_threshold_days,
    )


def _latest_predicted_daily(db: Session) -> dict[tuple[str, str], float]:
    """Most recent prediction per (store, product), treated as expected daily sales."""
    sub = (
        db.query(
            Prediction.store_id,
            Prediction.product_id,
            func.max(Prediction.created_at).label("max_created"),
        )
        .group_by(Prediction.store_id, Prediction.product_id)
        .subquery()
    )
    rows = (
        db.query(Prediction.store_id, Prediction.product_id, Prediction.predicted_units_sold)
        .join(
            sub,
            (Prediction.store_id == sub.c.store_id)
            & (Prediction.product_id == sub.c.product_id)
            & (Prediction.created_at == sub.c.max_created),
        )
        .all()
    )
    return {(r[0], r[1]): float(r[2]) for r in rows}


@router.get("/reorder", response_model=list[ReorderRecommendation])
def reorder_recommendations(
    db: Session = Depends(get_db),
    config: ReorderConfig = Depends(_config),
    limit: int = Query(default=200, ge=1, le=500),
) -> list[ReorderRecommendation]:
    predicted = _latest_predicted_daily(db)
    results = recommendation_service.build_recommendations(
        db,
        lead_time_days=config.lead_time_days,
        service_level=config.service_level,
        reorder_threshold_days=config.reorder_threshold_days,
        predicted_sales_by_pair=predicted,
        limit=limit,
    )
    return [ReorderRecommendation(**r) for r in results]


@router.get("/low-stock")
def low_stock(
    db: Session = Depends(get_db),
    threshold_days: float = Query(default=3, ge=0, le=365),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    avgs = recommendation_service.demand_stats(db)
    records = recommendation_service.latest_inventory(db)
    items = []
    for rec in records:
        mean, _std = avgs.get((rec.store_id, rec.product_id), (0.0, 0.0))
        if mean <= 0:
            continue
        cover = rec.inventory_level / mean
        if cover <= threshold_days:
            items.append(
                {
                    "product_id": rec.product_id,
                    "store_id": rec.store_id,
                    "category": rec.category,
                    "region": rec.region,
                    "current_inventory": rec.inventory_level,
                    "avg_daily_sales": round(mean, 2),
                    "days_of_cover": round(cover, 2),
                    "risk_level": recommendation_service.risk_level(cover, threshold_days),
                }
            )
    items.sort(key=lambda x: x["days_of_cover"])
    return {
        "threshold_days": threshold_days,
        "count": min(len(items), limit),
        "items": items[:limit],
    }
