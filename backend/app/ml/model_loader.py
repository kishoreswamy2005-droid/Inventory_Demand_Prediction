"""Thread-safe loader/manager for the trained scikit-learn pipeline."""
from __future__ import annotations

import threading
import warnings
from typing import Any

import joblib
import numpy as np
from sklearn.pipeline import Pipeline

from app.core.config import settings
from app.core.logging import get_logger
from app.ml.feature_schema import FEATURE_COLUMNS, MODEL_NAME, MODEL_VERSION

logger = get_logger(__name__)


class ModelNotReadyError(RuntimeError):
    """Raised when the trained model cannot be used for predictions."""


class ModelManager:
    """Loads the model once and reuses it for every prediction request."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model: Pipeline | None = None
        self._error: str | None = None
        self._loaded: bool = False
        self._feature_names: list[str] = []

    def load(self) -> bool:
        with self._lock:
            if self._loaded and self._model is not None:
                return True
            path = settings.MODEL_PATH
            if not path.exists():
                self._error = f"Model file not found: {path}"
                logger.error(self._error)
                return False
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    model = joblib.load(path)
                if not isinstance(model, Pipeline):
                    raise TypeError(f"Unexpected model type: {type(model)!r}")
                names = list(getattr(model, "feature_names_in_", []))
                if names and names != FEATURE_COLUMNS:
                    raise ValueError(
                        "Model feature schema mismatch: "
                        f"expected {FEATURE_COLUMNS}, model expects {names}"
                    )
                # Smoke test with an in-distribution row.
                import pandas as pd

                probe = pd.DataFrame(
                    [
                        {
                            "Store ID": "S001",
                            "Product ID": "P0001",
                            "Category": "Groceries",
                            "Region": "North",
                            "Inventory Level": 200,
                            "Price": 30.0,
                            "Discount": 10,
                            "Weather Condition": "Sunny",
                            "Holiday/Promotion": 0,
                            "Competitor Pricing": 29.0,
                            "Seasonality": "Summer",
                            "Year": 2024,
                            "Month": 6,
                            "Day": 15,
                            "DayOfWeek": 5,
                            "DayOfYear": 167,
                        }
                    ],
                    columns=FEATURE_COLUMNS,
                )
                sample = np.asarray(model.predict(probe), dtype=float)
                if not np.all(np.isfinite(sample)):
                    raise ValueError("Model produced non-finite probe prediction")
                self._model = model
                self._feature_names = names or list(FEATURE_COLUMNS)
                self._error = None
                self._loaded = True
                logger.info("Loaded model %s v%s from %s", MODEL_NAME, MODEL_VERSION, path)
                return True
            except Exception as exc:  # pragma: no cover - defensive
                self._error = str(exc)
                self._loaded = False
                logger.exception("Model loading failed")
                return False

    @property
    def model(self) -> Pipeline:
        if self._model is None:
            self.load()
        if self._model is None:
            raise ModelNotReadyError(self._error or "Model is not loaded")
        return self._model

    @property
    def ready(self) -> bool:
        return self._model is not None

    @property
    def error(self) -> str | None:
        return self._error

    @property
    def feature_names(self) -> list[str]:
        return list(self._feature_names)

    def status(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "model_name": MODEL_NAME,
            "model_version": MODEL_VERSION,
            "model_path": str(settings.MODEL_PATH),
            "error": self._error,
            "feature_columns": FEATURE_COLUMNS,
        }


model_manager = ModelManager()
