"""Replenishment recommendations using configurable business rules.

Recommended Reorder Quantity =
    max(0, expected demand during lead time + safety stock - available inventory)

Safety stock uses a normal-approximation service factor:
    z(service level) * demand_std * sqrt(lead_time_days)

The historical demand statistics come from real database records; supplier lead
time and target service level are user-supplied assumptions, so every result is
labelled as an illustrative recommendation.
"""
from __future__ import annotations

import math
from statistics import NormalDist

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import InventoryRecord
from app.services.inventory_service import classify

RISK_CRITICAL = "Critical"
RISK_HIGH = "High"
RISK_MEDIUM = "Medium"
RISK_LOW = "Low"


def _z(service_level: float) -> float:
    try:
        return NormalDist().inv_cdf(service_level)
    except (ValueError, ArithmeticError):
        return 1.65


def latest_inventory(db: Session) -> list[InventoryRecord]:
    """Most recent inventory record per (store, product)."""
    latest_date = (
        db.query(
            InventoryRecord.store_id,
            InventoryRecord.product_id,
            func.max(InventoryRecord.date).label("max_date"),
        )
        .group_by(InventoryRecord.store_id, InventoryRecord.product_id)
        .subquery()
    )
    return (
        db.query(InventoryRecord)
        .join(
            latest_date,
            (InventoryRecord.store_id == latest_date.c.store_id)
            & (InventoryRecord.product_id == latest_date.c.product_id)
            & (InventoryRecord.date == latest_date.c.max_date),
        )
        .all()
    )


def demand_stats(db: Session) -> dict[tuple[str, str], tuple[float, float]]:
    rows = (
        db.query(
            InventoryRecord.store_id,
            InventoryRecord.product_id,
            func.avg(InventoryRecord.units_sold),
            func.avg(InventoryRecord.units_sold * InventoryRecord.units_sold),
        )
        .group_by(InventoryRecord.store_id, InventoryRecord.product_id)
        .all()
    )
    stats: dict[tuple[str, str], tuple[float, float]] = {}
    for store_id, product_id, mean_v, mean_sq in rows:
        mean = float(mean_v or 0.0)
        variance = max(float(mean_sq or 0.0) - mean**2, 0.0)
        stats[(store_id, product_id)] = (mean, math.sqrt(variance))
    return stats


def risk_level(days_of_cover: float, threshold_days: float) -> str:
    if days_of_cover <= 1:
        return RISK_CRITICAL
    if days_of_cover <= threshold_days:
        return RISK_HIGH
    if days_of_cover <= threshold_days * 2:
        return RISK_MEDIUM
    return RISK_LOW


def build_recommendations(
    db: Session,
    lead_time_days: float,
    service_level: float,
    reorder_threshold_days: float,
    predicted_sales_by_pair: dict[tuple[str, str], float] | None = None,
    limit: int = 200,
) -> list[dict]:
    stats = demand_stats(db)
    predicted_sales_by_pair = predicted_sales_by_pair or {}
    records = latest_inventory(db)

    results = []
    for rec in records:
        mean, std = stats.get((rec.store_id, rec.product_id), (0.0, 0.0))
        # Use the newest prediction for this pair when one exists, otherwise
        # fall back to observed average daily sales.
        expected_daily = predicted_sales_by_pair.get(
            (rec.store_id, rec.product_id), mean
        )
        lead_demand = expected_daily * lead_time_days
        z = _z(service_level)
        safety = z * std * math.sqrt(max(lead_time_days, 0))
        reorder = max(0.0, lead_demand + safety - rec.inventory_level)

        days_cover = rec.inventory_level / mean if mean > 0 else float("inf")
        level, _ = classify(rec.inventory_level, mean)
        risk = risk_level(days_cover, reorder_threshold_days)

        reason_parts = [
            f"Expected demand over the {lead_time_days:g}-day lead time is "
            f"{lead_demand:.1f} units.",
            f"Safety stock at {service_level:.0%} service level is {safety:.1f} units.",
            f"Available inventory is {rec.inventory_level} units "
            f"({days_cover:.1f} days of cover)." if days_cover != float("inf")
            else f"Available inventory is {rec.inventory_level} units (no sales history).",
            f"Inventory classification: {level}.",
        ]
        if reorder <= 0:
            reason_parts.append("No replenishment required at the configured assumptions.")

        results.append(
            {
                "product_id": rec.product_id,
                "store_id": rec.store_id,
                "category": rec.category,
                "region": rec.region,
                "current_inventory": rec.inventory_level,
                "predicted_sales": round(expected_daily, 2),
                "avg_daily_sales": round(mean, 2),
                "demand_std": round(std, 2),
                "safety_stock": round(safety, 1),
                "demand_during_lead_time": round(lead_demand, 1),
                "recommended_reorder_quantity": int(math.floor(reorder + 0.5)),
                "days_of_cover": round(days_cover, 2)
                if days_cover != float("inf")
                else None,
                "risk_level": risk,
                "reason": " ".join(reason_parts),
                "assumptions": {
                    "lead_time_days": lead_time_days,
                    "service_level": service_level,
                    "reorder_threshold_days": reorder_threshold_days,
                    "safety_stock_formula": "z(service_level) * demand_std * sqrt(lead_time_days)",
                },
                "illustrative": True,
            }
        )

    order = {RISK_CRITICAL: 0, RISK_HIGH: 1, RISK_MEDIUM: 2, RISK_LOW: 3}
    results.sort(key=lambda r: (order[r["risk_level"]], r["product_id"], r["store_id"]))
    return results[:limit]
