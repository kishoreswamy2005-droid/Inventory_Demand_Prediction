"""Report and CSV export endpoints backed by real database queries."""
from __future__ import annotations

import csv
import io
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db
from app.models.entities import InventoryRecord, Prediction
from app.schemas import ReportResponse
from app.services import analytics_service as analytics

router = APIRouter(
    prefix="/api/reports", tags=["reports"], dependencies=[Depends(get_current_user)]
)


def _filters(
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    store: str | None = Query(default=None),
    product: str | None = Query(default=None),
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=5000),
):
    return {
        "start": start,
        "end": end,
        "store": store,
        "product": product,
        "category": category,
        "region": region,
        "limit": limit,
    }


def _filtered(db: Session, f: dict[str, Any]):
    q = db.query(InventoryRecord)
    if f["start"]:
        q = q.filter(InventoryRecord.date >= f["start"])
    if f["end"]:
        q = q.filter(InventoryRecord.date <= f["end"])
    if f["store"]:
        q = q.filter(InventoryRecord.store_id == f["store"])
    if f["product"]:
        q = q.filter(InventoryRecord.product_id == f["product"])
    if f["category"]:
        q = q.filter(InventoryRecord.category == f["category"])
    if f["region"]:
        q = q.filter(InventoryRecord.region == f["region"])
    return q


def _public_filters(f: dict[str, Any]) -> dict[str, Any]:
    return {k: (str(v) if v is not None else None) for k, v in f.items() if k != "limit"}


@router.get("/sales", response_model=ReportResponse)
def sales_report(db: Session = Depends(get_db), f: dict = Depends(_filters)) -> ReportResponse:
    rows = (
        _filtered(db, f)
        .with_entities(
            InventoryRecord.product_id,
            InventoryRecord.category,
            InventoryRecord.store_id,
            func.sum(InventoryRecord.units_sold),
            func.sum(InventoryRecord.demand_forecast),
            func.avg(InventoryRecord.price),
            func.count(InventoryRecord.id),
        )
        .group_by(
            InventoryRecord.product_id,
            InventoryRecord.category,
            InventoryRecord.store_id,
        )
        .order_by(func.sum(InventoryRecord.units_sold).desc())
        .limit(f["limit"])
        .all()
    )
    data = [
        {
            "product_id": r[0],
            "category": r[1],
            "store_id": r[2],
            "units_sold": int(r[3] or 0),
            "demand_forecast": round(float(r[4] or 0), 2),
            "avg_price": round(float(r[5] or 0), 2),
            "records": int(r[6]),
        }
        for r in rows
    ]
    return ReportResponse(
        report_type="sales",
        generated_at=datetime.now(timezone.utc),
        filters=_public_filters(f),
        row_count=len(data),
        rows=data,
    )


@router.get("/inventory", response_model=ReportResponse)
def inventory_report(db: Session = Depends(get_db), f: dict = Depends(_filters)) -> ReportResponse:
    from app.services.inventory_service import average_daily_sales, classify

    rows = (
        _filtered(db, f)
        .with_entities(
            InventoryRecord.store_id,
            InventoryRecord.product_id,
            InventoryRecord.category,
            InventoryRecord.region,
            func.max(InventoryRecord.date),
            func.avg(InventoryRecord.inventory_level),
            func.sum(InventoryRecord.units_sold),
            func.avg(InventoryRecord.price),
            func.avg(InventoryRecord.discount),
        )
        .group_by(
            InventoryRecord.store_id,
            InventoryRecord.product_id,
            InventoryRecord.category,
            InventoryRecord.region,
        )
        .order_by(func.sum(InventoryRecord.units_sold).asc())
        .limit(f["limit"])
        .all()
    )
    avgs = average_daily_sales(db)
    data = []
    for r in rows:
        avg_sales = avgs.get((r[0], r[1]), 0.0)
        status, cover = classify(int(r[5] or 0), avg_sales)
        data.append(
            {
                "store_id": r[0],
                "product_id": r[1],
                "category": r[2],
                "region": r[3],
                "last_record_date": str(r[4]),
                "avg_inventory_level": round(float(r[5] or 0), 2),
                "units_sold": int(r[6] or 0),
                "avg_price": round(float(r[7] or 0), 2),
                "avg_discount": round(float(r[8] or 0), 2),
                "inventory_status": status,
                "days_of_cover": round(cover, 2) if cover != float("inf") else None,
            }
        )
    return ReportResponse(
        report_type="inventory",
        generated_at=datetime.now(timezone.utc),
        filters=_public_filters(f),
        row_count=len(data),
        rows=data,
    )


@router.get("/predictions", response_model=ReportResponse)
def prediction_report(db: Session = Depends(get_db), f: dict = Depends(_filters)) -> ReportResponse:
    q = db.query(Prediction)
    if f["start"]:
        q = q.filter(Prediction.prediction_date >= f["start"])
    if f["end"]:
        q = q.filter(Prediction.prediction_date <= f["end"])
    if f["store"]:
        q = q.filter(Prediction.store_id == f["store"])
    if f["product"]:
        q = q.filter(Prediction.product_id == f["product"])
    rows = (
        q.with_entities(
            Prediction.store_id,
            Prediction.product_id,
            func.count(Prediction.id),
            func.sum(Prediction.predicted_units_sold),
            func.avg(Prediction.predicted_units_sold),
            func.max(Prediction.created_at),
        )
        .group_by(Prediction.store_id, Prediction.product_id)
        .order_by(func.sum(Prediction.predicted_units_sold).desc())
        .limit(f["limit"])
        .all()
    )
    actual = {
        (r[0], r[1]): int(r[2] or 0)
        for r in (
            _filtered(db, f)
            .with_entities(
                InventoryRecord.store_id,
                InventoryRecord.product_id,
                func.sum(InventoryRecord.units_sold),
            )
            .group_by(InventoryRecord.store_id, InventoryRecord.product_id)
            .all()
        )
    }
    data = []
    for r in rows:
        act = actual.get((r[0], r[1]))
        data.append(
            {
                "store_id": r[0],
                "product_id": r[1],
                "prediction_count": int(r[2]),
                "predicted_units_total": int(r[3] or 0),
                "predicted_units_avg": round(float(r[4] or 0), 2),
                "last_prediction_at": str(r[5]),
                "actual_units_sold": act,
                "note": "Actual sales are only displayed when sales records exist "
                "for the same store/product.",
            }
        )
    return ReportResponse(
        report_type="predictions",
        generated_at=datetime.now(timezone.utc),
        filters=_public_filters(f),
        row_count=len(data),
        rows=data,
    )


@router.get("/export/csv")
def export_csv(
    report: str = Query(default="sales", pattern="^(sales|inventory|predictions)$"),
    db: Session = Depends(get_db),
    f: dict = Depends(_filters),
) -> StreamingResponse:
    if report == "sales":
        result = sales_report(db, f)
    elif report == "inventory":
        result = inventory_report(db, f)
    else:
        result = prediction_report(db, f)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(result.rows[0].keys()) if result.rows else ["empty"])
    writer.writeheader()
    for row in result.rows:
        writer.writerow(row)
    buffer.seek(0)

    filename = f"{report}_report_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
