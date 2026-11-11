"""Application configuration loaded from environment variables."""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = BASE_DIR / "backend"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
DATASET_PATH = BASE_DIR / "dataset" / "retail_store_inventory.csv"

# The supplied model ships at the project root; keep artifacts/ as a fallback
# location so operators can drop in an updated pickle without code changes.
_ROOT_MODEL = BASE_DIR / "inventory_demand_model.pkl"
MODEL_PATH = _ROOT_MODEL if _ROOT_MODEL.exists() else ARTIFACTS_DIR / "inventory_demand_model.pkl"


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    """Runtime settings. Secrets always come from the environment."""

    APP_NAME = os.getenv("APP_NAME", "Inventory Demand Prediction API")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    DEBUG = _bool("DEBUG", "true")

    # In production these MUST be provided through the environment.
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me")
    ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    ALGORITHM = os.getenv("ALGORITHM", "HS256")

    DATABASE_URL = os.getenv(
        "DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'inventory_demand.db'}"
    )

    # Artifact locations (overridable for deployments that relocate files).
    MODEL_PATH = Path(os.getenv("MODEL_PATH", str(MODEL_PATH))).resolve()
    DATASET_PATH = Path(os.getenv("DATASET_PATH", str(DATASET_PATH))).resolve()

    CORS_ORIGINS = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
        ).split(",")
        if o.strip()
    ]

    # Inventory business rules (days of cover based, configurable).
    DAYS_CRITICAL = float(os.getenv("DAYS_CRITICAL", "1"))
    DAYS_LOW = float(os.getenv("DAYS_LOW", "3"))
    DAYS_OVERSTOCK = float(os.getenv("DAYS_OVERSTOCK", "30"))

    # Replenishment assumptions (illustrative unless real lead-time data exists).
    DEFAULT_LEAD_TIME_DAYS = float(os.getenv("DEFAULT_LEAD_TIME_DAYS", "7"))
    DEFAULT_SERVICE_LEVEL = float(os.getenv("DEFAULT_SERVICE_LEVEL", "0.95"))
    DEFAULT_REORDER_THRESHOLD_DAYS = float(os.getenv("DEFAULT_REORDER_THRESHOLD_DAYS", "3"))

    # Simple in-memory rate limiting for prediction calls.
    PREDICTION_RATE_LIMIT = int(os.getenv("PREDICTION_RATE_LIMIT", "120"))
    PREDICTION_RATE_WINDOW_SECONDS = int(os.getenv("PREDICTION_RATE_WINDOW_SECONDS", "60"))

    # Seed the database from the bundled dataset when the table is empty.
    AUTO_SEED_DATASET = _bool("AUTO_SEED_DATASET", "true")

    MODEL_NAME = os.getenv("MODEL_NAME", "inventory_demand_random_forest")
    MODEL_VERSION = os.getenv("MODEL_VERSION", "1.0.0")

    # Notebook evaluation metrics (saved outputs, never invented).
    NOTEBOOK_METRICS = {
        "mae": 69.18,
        "rmse": 88.59,
        "r2": 0.3298,
        "wape_percent": 50.91,
        "train_rows": 58400,
        "test_rows": 14700,
        "split_date": "2023-08-08",
    }


settings = Settings()
