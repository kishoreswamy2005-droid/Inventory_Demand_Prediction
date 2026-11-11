"""Prediction execution and validation."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.ml.feature_builder import build_feature_frame
from app.ml.feature_schema import MODEL_NAME, MODEL_VERSION
from app.ml.model_loader import ModelNotReadyError, model_manager

logger = get_logger(__name__)


class PredictionError(RuntimeError):
    """Raised when a prediction cannot be produced safely."""


def predict_units_sold(inputs: dict[str, Any], prediction_date: date) -> dict[str, Any]:
    """Run the supplied trained pipeline and validate its output.

    Raw predictions are retained for analytics; the user-facing integer value is
    rounded half-up to whole units and clipped at zero because you cannot sell a
    negative number of items.
    """
    if not model_manager.ready:
        model_manager.load()
    if not model_manager.ready:
        raise PredictionError(model_manager.error or "Model is not loaded")

    frame = build_feature_frame(inputs, prediction_date)
    try:
        raw = np.asarray(model_manager.model.predict(frame), dtype=float)
    except ModelNotReadyError as exc:
        raise PredictionError(str(exc)) from exc
    except Exception as exc:
        logger.exception("Prediction failed")
        raise PredictionError("The model failed to produce a prediction") from exc

    if raw.size != 1 or not np.all(np.isfinite(raw)):
        raise PredictionError("Model returned an invalid prediction value")

    value = float(raw[0])
    if value < 0:
        value = 0.0
    rounded = int(math.floor(value + 0.5))

    return {
        "predicted_units_sold_raw": value,
        "predicted_units_sold": rounded,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "rounding": "Raw model output rounded half-up to whole units; negatives clipped to 0.",
    }
