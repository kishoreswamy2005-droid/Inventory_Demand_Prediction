"""Dashboard aggregations and report queries (all values come from the database)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.entities import InventoryRecord, Prediction, Product, Store
from app.services.inventory_service import (
    STATUS_CRITICAL,
    STATUS_LOW,
    STATUS_OVERSTOCK,
    average_daily_sales,
    classify,
)


def _date_bounds(db: Session, start: date | None, end: date | None) -> tuple[date, date]:
    if start is None or end is None:
        min_max = db.query(func.min(InventoryRecord.date), func.max(InventoryRecord.date)).one()
        min_d, max_d = min_max
    else:
        min_d, max_d = start, end
    return min_d or date.today(), max_d or date.today()


def _base(db: Session, start: date | None, end: date | None, store: str | None,
          category: str | None, region: str | None):
    q = db.query(InventoryRecord)
    lo, hi = _date_bounds(db, start, end)
    if start:
        q = q.filter(InventoryRecord.date >= start)
    else:
        q = q.filter(InventoryRecord.date >= lo)
    if end:
        q = q.filter(InventoryRecord.date <= end)
    else:
        q = q.filter(InventoryRecord.date <= hi)
    if store:
        q = q.filter(InventoryRecord.store_id == store)
    if category:
        q = q.filter(InventoryRecord.category == category)
    if region:
        q = q.filter(InventoryRecord.region == region)
    return q


def dashboard_summary(
    db: Session, start: date | None = None, end: date | None = None,
    store: str | None = None, category: str | None = None, region: str | None = None,
) -> dict[str, Any]:
    q = _base(db, start, end, store, category, region)
    totals = q.with_entities(
        func.count(func.distinct(InventoryRecord.product_id)),
        func.count(func.distinct(InventoryRecord.store_id)),
        func.sum(InventoryRecord.units_sold),
        func.max(InventoryRecord.date),
        func.min(InventoryRecord.date),
    ).one()

    # Latest record per store/product within the filtered scope.
    latest = _latest_records(db, start, end, store, category, region)
    avgs = average_daily_sales(db)
    current_inventory = sum(r.inventory_level for r in latest)
    low = critical = overstocked = 0
    for rec in latest:
        status, _cover = classify(rec.inventory_level, avgs.get((rec.store_id, rec.product_id), 0.0))
        if status == STATUS_LOW:
            low += 1
        elif status == STATUS_CRITICAL:
            critical += 1
        elif status == STATUS_OVERSTOCK:
            overstocked += 1

    predicted = db.query(func.coalesce(func.sum(Prediction.predicted_units_sold), 0.0)).scalar()

    lo, hi = _date_bounds(db, start, end)
    return {
        "total_products": int(totals[0] or 0),
        "total_stores": int(totals[1] or 0),
        "total_units_sold": int(totals[2] or 0),
        "current_inventory": int(current_inventory),
        "predicted_demand": int(round(float(predicted or 0))),
        "low_stock_products": low,
        "overstocked_products": overstocked,
        "critical_stock_products": critical,
        "date_range": {
            "start": str(lo),
            "end": str(hi),
            "min_record": str(totals[4]) if totals[4] else None,
            "max_record": str(totals[3]) if totals[3] else None,
        },
    }


def _latest_records(db: Session, start: date | None, end: date | None,
                    store: str | None, category: str | None, region: str | None):
    from sqlalchemy import and_

    sub = (
        _base(db, start, end, store, category, region)
        .with_entities(
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
            sub,
            and_(
                InventoryRecord.store_id == sub.c.store_id,
                InventoryRecord.product_id == sub.c.product_id,
                InventoryRecord.date == sub.c.max_date,
            ),
        )
        .all()
    )


def sales_trend(db: Session, start: date | None, end: date | None, store: str | None,
                category: str | None, region: str | None, granularity: str = "day") -> list[dict]:
    date_col = InventoryRecord.date
    if granularity == "month":
        bucket = func.strftime("%Y-%m", InventoryRecord.date)
    else:
        bucket = date_col
    rows = (
        _base(db, start, end, store, category, region)
        .with_entities(bucket, func.sum(InventoryRecord.units_sold))
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    return [{"label": str(r[0]), "value": float(r[1] or 0)} for r in rows]


def product_performance(db: Session, start, end, store, category, region,
                        top: int = 10, ascending: bool = False) -> list[dict]:
    rows = (
        _base(db, start, end, store, category, region)
        .with_entities(
            InventoryRecord.product_id,
            InventoryRecord.category,
            func.sum(InventoryRecord.units_sold),
        )
        .group_by(InventoryRecord.product_id, InventoryRecord.category)
        .order_by(func.sum(InventoryRecord.units_sold).asc() if ascending
                  else func.sum(InventoryRecord.units_sold).desc())
        .limit(top)
        .all()
    )
    return [
        {"label": r[0], "category": r[1], "value": float(r[2] or 0)}
        for r in rows
    ]


def store_performance(db: Session, start, end, store, category, region) -> list[dict]:
    rows = (
        _base(db, start, end, store, category, region)
        .with_entities(
            InventoryRecord.store_id,
            InventoryRecord.region,
            func.sum(InventoryRecord.units_sold),
            func.avg(InventoryRecord.units_sold),
        )
        .group_by(InventoryRecord.store_id, InventoryRecord.region)
        .order_by(func.sum(InventoryRecord.units_sold).desc())
        .all()
    )
    return [
        {
            "label": r[0],
            "region": r[1],
            "value": float(r[2] or 0),
            "avg_units": round(float(r[3] or 0), 2),
        }
        for r in rows
    ]


def category_performance(db: Session, start, end, store, category, region) -> list[dict]:
    rows = (
        _base(db, start, end, store, category, region)
        .with_entities(InventoryRecord.category, func.sum(InventoryRecord.units_sold))
        .group_by(InventoryRecord.category)
        .order_by(func.sum(InventoryRecord.units_sold).desc())
        .all()
    )
    return [{"label": r[0], "value": float(r[1] or 0)} for r in rows]


def inventory_overview(db: Session, start, end, store, category, region) -> list[dict]:
    avgs = average_daily_sales(db)
    latest = _latest_records(db, start, end, store, category, region)
    buckets = {"Critical Stock": 0, "Low Stock": 0, "Healthy Stock": 0, "Overstocked": 0}
    total = 0
    for rec in latest:
        status, _ = classify(rec.inventory_level, avgs.get((rec.store_id, rec.product_id), 0.0))
        buckets[status] += 1
        total += rec.inventory_level
    out = [{"label": k, "value": float(v)} for k, v in buckets.items()]
    out.append({"label": "Total Inventory Units", "value": float(total)})
    return out


def actual_vs_predicted(db: Session, start, end, store, category, region) -> list[dict]:
    actual_rows = (
        _base(db, start, end, store, category, region)
        .with_entities(InventoryRecord.date, func.sum(InventoryRecord.units_sold))
        .group_by(InventoryRecord.date)
        .order_by(InventoryRecord.date)
        .all()
    )
    predicted_rows = _predicted_series(db, start, end, store)
    pred_map = {r["label"]: r["value"] for r in predicted_rows}
    series = []
    for d, actual in actual_rows:
        key = str(d)
        series.append(
            {
                "label": key,
                "value": float(actual or 0),
                "secondary": pred_map.get(key),
            }
        )
    return series


def _predicted_series(db: Session, start, end, store) -> list[dict]:
    q = db.query(
        Prediction.prediction_date, func.sum(Prediction.predicted_units_sold)
    )
    if start:
        q = q.filter(Prediction.prediction_date >= start)
    if end:
        q = q.filter(Prediction.prediction_date <= end)
    if store:
        q = q.filter(Prediction.store_id == store)
    rows = q.group_by(Prediction.prediction_date).order_by(Prediction.prediction_date).all()
    return [{"label": str(r[0]), "value": float(r[1] or 0)} for r in rows]


def distinct_values(db: Session) -> dict[str, list[str]]:
    def col(c):
        return [r[0] for r in db.query(c).distinct().order_by(c).all()]

    return {
        "stores": col(InventoryRecord.store_id),
        "products": col(InventoryRecord.product_id),
        "categories": col(InventoryRecord.category),
        "regions": col(InventoryRecord.region),
    }
