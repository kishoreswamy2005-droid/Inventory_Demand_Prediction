"""Inventory CRUD endpoints."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import false as sqlalchemy_false, tuple_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, get_db, require_admin
from app.models.entities import InventoryRecord, Product, Store
from app.schemas import InventoryCreate, InventoryRecordOut, InventoryUpdate, Page
from app.services import inventory_service

router = APIRouter(
    prefix="/api/inventory", tags=["inventory"], dependencies=[Depends(get_current_user)]
)


def _filters(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, description="Matches product or store id"),
    store: str | None = Query(default=None),
    category: str | None = Query(default=None),
    region: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    sort: str = Query(default="date", pattern="^(date|inventory_level|units_sold|price|product_id|store_id)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
):
    q = db.query(InventoryRecord)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            (InventoryRecord.product_id.ilike(like)) | (InventoryRecord.store_id.ilike(like))
        )
    if store:
        q = q.filter(InventoryRecord.store_id == store)
    if category:
        q = q.filter(InventoryRecord.category == category)
    if region:
        q = q.filter(InventoryRecord.region == region)
    if start:
        q = q.filter(InventoryRecord.date >= start)
    if end:
        q = q.filter(InventoryRecord.date <= end)
    if status_filter:
        # Status derives from inventory level vs. average daily sales, so resolve
        # the matching (store, product) pairs first and filter with them.
        avgs = inventory_service.average_daily_sales(db)
        pairs = [
            (store_id, product_id)
            for (store_id, product_id), avg in avgs.items()
            if inventory_service.classify(
                _latest_level(db, store_id, product_id), avg
            )[0] == status_filter
        ]
        if not pairs:
            q = q.filter(sqlalchemy_false())
        else:
            q = q.filter(
                tuple_(InventoryRecord.store_id, InventoryRecord.product_id).in_(pairs)
            )
    return q, search, store, category, region, status_filter, start, end, sort, order, page, page_size


def _latest_level(db: Session, store_id: str, product_id: str) -> int:
    row = (
        db.query(InventoryRecord.inventory_level)
        .filter(
            InventoryRecord.store_id == store_id,
            InventoryRecord.product_id == product_id,
        )
        .order_by(InventoryRecord.date.desc())
        .first()
    )
    return int(row[0]) if row else 0


@router.get("", response_model=Page[InventoryRecordOut])
def list_inventory(db: Session = Depends(get_db), params=Depends(_filters)) -> Page[InventoryRecordOut]:
    (
        q, search, store, category, region, status_filter, start, end, sort, order, page, page_size
    ) = params

    total = q.count()
    sort_col = getattr(InventoryRecord, sort)
    q = q.order_by(sort_col.desc() if order == "desc" else sort_col.asc())
    rows = q.offset((page - 1) * page_size).limit(page_size).all()

    avgs = inventory_service.average_daily_sales(db)
    inventory_service.annotate(rows, avgs)

    if status_filter:
        rows = [r for r in rows if r.inventory_status == status_filter]

    items = [InventoryRecordOut.model_validate(r) for r in rows]
    pages = max((total + page_size - 1) // page_size, 1)
    return Page(items=items, total=total, page=page, page_size=page_size, pages=pages)


@router.get("/{product_id}", response_model=list[InventoryRecordOut])
def product_history(
    product_id: str,
    store: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
) -> list[InventoryRecordOut]:
    q = db.query(InventoryRecord).filter(InventoryRecord.product_id == product_id)
    if store:
        q = q.filter(InventoryRecord.store_id == store)
    rows = q.order_by(InventoryRecord.date.desc()).limit(limit).all()
    if not rows:
        raise HTTPException(status_code=404, detail="No inventory records for this product")
    avgs = inventory_service.average_daily_sales(db)
    inventory_service.annotate(rows, avgs)
    return [InventoryRecordOut.model_validate(r) for r in rows]


@router.post("", response_model=InventoryRecordOut, status_code=status.HTTP_201_CREATED)
def create_record(
    payload: InventoryCreate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> InventoryRecordOut:
    exists = (
        db.query(InventoryRecord)
        .filter_by(store_id=payload.store_id, product_id=payload.product_id, date=payload.date)
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Record already exists for this key")

    store = db.query(Store).filter_by(store_id=payload.store_id).first()
    if store is None:
        store = Store(store_id=payload.store_id, region=payload.region)
        db.add(store)
        db.flush()
    product = db.query(Product).filter_by(product_id=payload.product_id).first()
    if product is None:
        product = Product(
            product_id=payload.product_id, category=payload.category, price=payload.price
        )
        db.add(product)
        db.flush()

    rec = InventoryRecord(
        store_fk=store.id,
        product_fk=product.id,
        store_id=payload.store_id,
        product_id=payload.product_id,
        date=payload.date,
        category=payload.category,
        region=payload.region,
        inventory_level=payload.inventory_level,
        units_sold=payload.units_sold,
        units_ordered=payload.units_ordered,
        demand_forecast=payload.demand_forecast,
        price=payload.price,
        discount=payload.discount,
        weather_condition=payload.weather_condition,
        holiday_promotion=payload.holiday_promotion,
        competitor_pricing=payload.competitor_pricing,
        seasonality=payload.seasonality,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    avgs = inventory_service.average_daily_sales(db)
    inventory_service.annotate([rec], avgs)
    return InventoryRecordOut.model_validate(rec)


@router.put("/{record_id}", response_model=InventoryRecordOut)
def update_record(
    record_id: int,
    payload: InventoryUpdate,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> InventoryRecordOut:
    rec = db.get(InventoryRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields supplied to update")
    for key, value in data.items():
        setattr(rec, key, value)
    db.commit()
    db.refresh(rec)
    avgs = inventory_service.average_daily_sales(db)
    inventory_service.annotate([rec], avgs)
    return InventoryRecordOut.model_validate(rec)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    _admin=Depends(require_admin),
) -> None:
    rec = db.get(InventoryRecord, record_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    db.delete(rec)
    db.commit()
