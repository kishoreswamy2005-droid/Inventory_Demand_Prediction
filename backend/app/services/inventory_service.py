"""Inventory status rules.

Status is derived from *days of cover*: available inventory divided by the
average daily units sold for that store/product over the observed history.
Thresholds are configurable through the environment (DAYS_CRITICAL, DAYS_LOW,
DAYS_OVERSTOCK) because no business-specific thresholds were supplied.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import InventoryRecord

STATUS_CRITICAL = "Critical Stock"
STATUS_LOW = "Low Stock"
STATUS_HEALTHY = "Healthy Stock"
STATUS_OVERSTOCK = "Overstocked"


def average_daily_sales(db: Session) -> dict[tuple[str, str], float]:
    rows = (
        db.query(
            InventoryRecord.store_id,
            InventoryRecord.product_id,
            func.avg(InventoryRecord.units_sold),
        )
        .group_by(InventoryRecord.store_id, InventoryRecord.product_id)
        .all()
    )
    return {(r[0], r[1]): float(r[2] or 0.0) for r in rows}


def classify(
    inventory_level: int,
    avg_daily_sales: float,
    days_critical: float | None = None,
    days_low: float | None = None,
    days_overstock: float | None = None,
) -> tuple[str, float]:
    """Return (status, days_of_cover)."""
    days_critical = settings.DAYS_CRITICAL if days_critical is None else days_critical
    days_low = settings.DAYS_LOW if days_low is None else days_low
    days_overstock = settings.DAYS_OVERSTOCK if days_overstock is None else days_overstock

    if avg_daily_sales <= 0:
        # No sales history: fall back to comparing with configured levels.
        if inventory_level <= days_critical:
            return STATUS_CRITICAL, float("inf")
        if inventory_level <= days_low:
            return STATUS_LOW, float("inf")
        if inventory_level >= days_overstock * 10:
            return STATUS_OVERSTOCK, float("inf")
        return STATUS_HEALTHY, float("inf")

    cover = inventory_level / avg_daily_sales
    if cover < days_critical:
        return STATUS_CRITICAL, cover
    if cover < days_low:
        return STATUS_LOW, cover
    if cover > days_overstock:
        return STATUS_OVERSTOCK, cover
    return STATUS_HEALTHY, cover


def annotate(records: list[InventoryRecord], avgs: dict[tuple[str, str], float]) -> None:
    for rec in records:
        avg = avgs.get((rec.store_id, rec.product_id), 0.0)
        status, cover = classify(rec.inventory_level, avg)
        rec.inventory_status = status
        rec.days_of_cover = round(cover, 2) if cover != float("inf") else None
