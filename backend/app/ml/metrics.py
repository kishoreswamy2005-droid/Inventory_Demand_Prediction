"""Model evaluation metrics.

`notebook_metrics()` returns the evaluation values saved in the Colab notebook
outputs. Those numbers are never invented; when they are unavailable the caller
must display the metric as unavailable.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from app.core.config import settings

LIMITATIONS = [
    "The model predicts observed Units Sold from contemporaneous tabular features; "
    "it does not use lagged sales (lag 1/7/14/28) or rolling means, so it is not a "
    "multi-day forecasting engine.",
    "Inventory Level timing is unverified: if it is measured after sales it leaks "
    "same-day information into the features.",
    "Units Sold is censored when a product is out of stock and may underestimate "
    "true demand.",
    "Evaluation WAPE of ~51% means predictions are directional planning aids, not "
    "guaranteed demand.",
]


def notebook_metrics() -> dict[str, Any]:
    m = dict(settings.NOTEBOOK_METRICS)
    m["source"] = "Inventory_Demand_Prediction.ipynb saved outputs"
    m["available"] = True
    return m


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true).sum()
    return {
        "mae": float(np.mean(np.abs(y_true - y_pred))),
        "rmse": float(np.sqrt(np.mean((y_true - y_pred) ** 2))),
        "r2": float(1 - np.sum((y_true - y_pred) ** 2) / np.sum((y_true - y_true.mean()) ** 2))
        if len(y_true) > 1
        else float("nan"),
        "wape_percent": float(np.abs(y_true - y_pred).sum() / denom * 100)
        if denom
        else float("nan"),
    }
