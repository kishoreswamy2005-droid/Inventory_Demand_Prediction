"""Builds the exact feature frame expected by the trained pipeline."""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from app.ml.feature_schema import CATEGORICAL_COLUMNS, DATE_DERIVED_COLUMNS, FEATURE_COLUMNS, NUMERICAL_COLUMNS


def date_features(prediction_date: date) -> dict[str, int]:
    return {
        "Year": prediction_date.year,
        "Month": prediction_date.month,
        "Day": prediction_date.day,
        "DayOfWeek": prediction_date.weekday(),
        "DayOfYear": prediction_date.timetuple().tm_yday,
    }


def build_feature_frame(inputs: dict[str, Any], prediction_date: date) -> pd.DataFrame:
    """Return a single-row DataFrame with the model's exact feature order."""
    row: dict[str, Any] = {}
    for col in FEATURE_COLUMNS:
        if col in DATE_DERIVED_COLUMNS:
            row[col] = date_features(prediction_date)[col]
        else:
            row[col] = inputs[col]

    df = pd.DataFrame([row], columns=FEATURE_COLUMNS)

    for col in CATEGORICAL_COLUMNS:
        df[col] = df[col].astype(str)
    for col in NUMERICAL_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype(float)
    if df[NUMERICAL_COLUMNS].isna().any().any():
        bad = df[NUMERICAL_COLUMNS].columns[df[NUMERICAL_COLUMNS].isna().any()].tolist()
        raise ValueError(f"Non-numeric values in columns: {bad}")
    return df
