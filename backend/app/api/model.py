"""Model status, metadata and performance endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user, get_db
from app.models.entities import Prediction
from app.ml.feature_schema import CATEGORICAL_COLUMNS, FEATURE_COLUMNS, NUMERICAL_COLUMNS
from app.ml.metrics import LIMITATIONS, notebook_metrics
from app.ml.model_loader import model_manager
from app.ml.model_validation import validate_model

router = APIRouter(prefix="/api/model", tags=["model"], dependencies=[Depends(get_current_user)])


@router.get("/status")
def status_endpoint() -> dict:
    if not model_manager.ready:
        model_manager.load()
    return model_manager.status()


@router.get("/metadata")
def metadata(db: Session = Depends(get_db)) -> dict:
    if not model_manager.ready:
        model_manager.load()
    return {
        "model_name": settings.MODEL_NAME,
        "model_version": settings.MODEL_VERSION,
        "training_date": None,
        "metrics": notebook_metrics(),
        "limitations": LIMITATIONS,
        "feature_columns": FEATURE_COLUMNS,
        "categorical_columns": CATEGORICAL_COLUMNS,
        "numerical_columns": NUMERICAL_COLUMNS,
        "validation": validate_model(),
    }


@router.get("/performance")
def performance(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict:
    """Prediction monitoring. Error metrics appear only when actual sales exist."""
    metrics = notebook_metrics()

    counts = db.query(func.count(Prediction.id)).scalar() or 0
    avg_pred = db.query(func.avg(Prediction.predicted_units_sold)).scalar() or 0.0

    # Matched predictions with actual sales for the same store/product/date.
    from app.models.entities import InventoryRecord

    matches = (
        db.query(Prediction.predicted_units_sold, InventoryRecord.units_sold)
        .join(
            InventoryRecord,
            (Prediction.store_id == InventoryRecord.store_id)
            & (Prediction.product_id == InventoryRecord.product_id)
            & (Prediction.prediction_date == InventoryRecord.date),
        )
        .all()
    )
    error_metrics = {"available": False, "matched_rows": len(matches)}
    if matches:
        import numpy as np

        from app.ml.metrics import compute_metrics

        y_pred = np.array([m[0] for m in matches], dtype=float)
        y_true = np.array([m[1] for m in matches], dtype=float)
        error_metrics = {"available": True, "matched_rows": len(matches), **{
            k: round(v, 2) for k, v in compute_metrics(y_true, y_pred).items()
        }}

    return {
        "generated_at": datetime.now(timezone.utc),
        "model_name": settings.MODEL_NAME,
        "model_version": settings.MODEL_VERSION,
        "notebook_metrics": metrics,
        "live_monitoring": {
            "prediction_count": int(counts),
            "average_prediction": round(float(avg_pred), 2),
            "error_metrics": error_metrics,
        },
        "limitations": LIMITATIONS,
        "note": "Prediction error is only computed where actual sales records exist "
        "for the same store, product and date.",
    }
