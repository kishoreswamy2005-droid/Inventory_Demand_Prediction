"""Prediction endpoints: run the trained pipeline and persist every result."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.ml.prediction_service import PredictionError, predict_units_sold
from app.models.entities import Prediction, Product, Store, User
from app.schemas import Page, PredictionHistoryOut, PredictionOut, PredictionRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/api/predictions", tags=["predictions"])

# Simple in-memory sliding-window limiter for prediction traffic.
_rate_hits: dict[str, deque] = defaultdict(deque)
_rate_lock = Lock()


def _rate_limit(request: Request) -> None:
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = settings.PREDICTION_RATE_WINDOW_SECONDS
    with _rate_lock:
        hits = _rate_hits[key]
        while hits and now - hits[0] > window:
            hits.popleft()
        if len(hits) >= settings.PREDICTION_RATE_LIMIT:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Prediction rate limit exceeded, please retry shortly",
            )
        hits.append(now)


@router.post("/predict", response_model=PredictionOut, status_code=status.HTTP_201_CREATED)
def create_prediction(
    payload: PredictionRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictionOut:
    _rate_limit(request)

    if not db.query(Store).filter_by(store_id=payload.store_id).limit(1).first():
        raise HTTPException(status_code=422, detail=f"Unknown Store ID: {payload.store_id}")
    if not db.query(Product).filter_by(product_id=payload.product_id).limit(1).first():
        raise HTTPException(status_code=422, detail=f"Unknown Product ID: {payload.product_id}")

    inputs = {
        "Store ID": payload.store_id,
        "Product ID": payload.product_id,
        "Category": payload.category,
        "Region": payload.region,
        "Inventory Level": payload.inventory_level,
        "Price": payload.price,
        "Discount": payload.discount,
        "Weather Condition": payload.weather_condition,
        "Holiday/Promotion": payload.holiday_promotion,
        "Competitor Pricing": payload.competitor_pricing,
        "Seasonality": payload.seasonality,
    }

    try:
        result = predict_units_sold(inputs, payload.prediction_date)
    except PredictionError as exc:
        logger.error("Prediction failed for %s/%s: %s", payload.store_id, payload.product_id, exc)
        raise HTTPException(status_code=503, detail="The prediction model is unavailable") from exc

    record = Prediction(
        user_id=user.id,
        store_id=payload.store_id,
        product_id=payload.product_id,
        prediction_date=payload.prediction_date,
        input_features={
            **inputs,
            "Year": payload.prediction_date.year,
            "Month": payload.prediction_date.month,
            "Day": payload.prediction_date.day,
            "DayOfWeek": payload.prediction_date.weekday(),
            "DayOfYear": payload.prediction_date.timetuple().tm_yday,
        },
        predicted_units_sold=result["predicted_units_sold"],
        model_name=result["model_name"],
        model_version=result["model_version"],
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return PredictionOut(
        id=record.id,
        store_id=record.store_id,
        product_id=record.product_id,
        prediction_date=record.prediction_date,
        predicted_units_sold=result["predicted_units_sold"],
        predicted_units_sold_raw=result["predicted_units_sold_raw"],
        model_name=result["model_name"],
        model_version=result["model_version"],
        status="completed",
        rounding=result["rounding"],
        created_at=record.created_at,
        input_features=record.input_features,
    )


@router.get("/history", response_model=Page[PredictionHistoryOut])
def history(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
    search: str | None = Query(default=None),
    store: str | None = Query(default=None),
    product: str | None = Query(default=None),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
) -> Page[PredictionHistoryOut]:
    q = db.query(Prediction)
    if search:
        like = f"%{search.strip()}%"
        q = q.filter(
            Prediction.store_id.ilike(like) | Prediction.product_id.ilike(like)
        )
    if store:
        q = q.filter(Prediction.store_id == store)
    if product:
        q = q.filter(Prediction.product_id == product)
    if start:
        q = q.filter(Prediction.prediction_date >= start)
    if end:
        q = q.filter(Prediction.prediction_date <= end)

    total = q.count()
    rows = (
        q.order_by(Prediction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    pages = max((total + page_size - 1) // page_size, 1)
    return Page(
        items=[PredictionHistoryOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.get("/{prediction_id}", response_model=PredictionOut)
def get_prediction(
    prediction_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> PredictionOut:
    record = db.get(Prediction, prediction_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Prediction not found")
    return PredictionOut(
        id=record.id,
        store_id=record.store_id,
        product_id=record.product_id,
        prediction_date=record.prediction_date,
        predicted_units_sold=int(record.predicted_units_sold),
        predicted_units_sold_raw=float(record.predicted_units_sold),
        model_name=record.model_name,
        model_version=record.model_version,
        status="completed",
        rounding="Stored integer prediction rounded half-up at creation time.",
        created_at=record.created_at,
        input_features=record.input_features,
    )
