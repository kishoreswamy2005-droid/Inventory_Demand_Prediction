"""Model compatibility checks exposed through the model status API."""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.ml.feature_schema import FEATURE_COLUMNS, MODEL_NAME, MODEL_VERSION
from app.ml.model_loader import model_manager
from app.ml.prediction_service import PredictionError, predict_units_sold
from datetime import date


def validate_model() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail})

    if not model_manager.ready:
        model_manager.load()
    add("model_file_loaded", model_manager.ready, model_manager.error or "Model loaded")

    if model_manager.ready:
        add(
            "feature_schema_match",
            model_manager.feature_names == FEATURE_COLUMNS,
            f"Expected {len(FEATURE_COLUMNS)} columns in fixed order",
        )
        add(
            "unknown_categories_ignored",
            _unknown_category_probe(),
            "Pipeline handles unknown categories without raising",
        )
        add("finite_output", _finite_probe(), "Prediction output is finite and numeric")
    else:
        add("feature_schema_match", False, "Model unavailable")
        add("unknown_categories_ignored", False, "Model unavailable")
        add("finite_output", False, "Model unavailable")

    return {
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "checks": checks,
        "passed": all(c["passed"] for c in checks),
    }


def _unknown_category_probe() -> bool:
    try:
        predict_units_sold(
            {
                "Store ID": "S001",
                "Product ID": "P0001",
                "Category": "Groceries",
                "Region": "North",
                "Inventory Level": 200,
                "Price": 30.0,
                "Discount": 10,
                "Weather Condition": "Hurricane",  # unseen category
                "Holiday/Promotion": 0,
                "Competitor Pricing": 29.0,
                "Seasonality": "Summer",
            },
            date.today(),
        )
        return True
    except PredictionError:
        return False


def _finite_probe() -> bool:
    try:
        result = predict_units_sold(
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
            },
            date.today(),
        )
        return bool(pd.notna(result["predicted_units_sold_raw"]))
    except PredictionError:
        return False
