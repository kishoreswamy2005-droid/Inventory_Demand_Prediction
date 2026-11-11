"""CSV dataset import with validation, preview and idempotent upsert."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.entities import ImportJob, InventoryRecord, Product, Store

logger = get_logger(__name__)

REQUIRED_COLUMNS = [
    "Date",
    "Store ID",
    "Product ID",
    "Category",
    "Region",
    "Inventory Level",
    "Units Sold",
    "Units Ordered",
    "Demand Forecast",
    "Price",
    "Discount",
    "Weather Condition",
    "Holiday/Promotion",
    "Competitor Pricing",
    "Seasonality",
]

NUMERIC_DTYPES: dict[str, str] = {
    "Inventory Level": "Int64",
    "Units Sold": "Int64",
    "Units Ordered": "Int64",
    "Demand Forecast": "float",
    "Price": "float",
    "Discount": "Int64",
    "Holiday/Promotion": "Int64",
    "Competitor Pricing": "float",
}


class ImportValidationError(ValueError):
    pass


def validate_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ImportValidationError(
            f"Missing required columns: {', '.join(missing)}"
        )
    errors: list[dict[str, Any]] = []

    parsed_dates = pd.to_datetime(df["Date"], errors="coerce")
    bad_dates = parsed_dates.isna()
    if bad_dates.any():
        errors.append(
            {
                "type": "invalid_date",
                "count": int(bad_dates.sum()),
                "rows": [int(i) + 2 for i in df.index[bad_dates][:10]],
                "message": "Rows with unparseable Date values",
            }
        )

    for col, dtype in NUMERIC_DTYPES.items():
        converted = pd.to_numeric(df[col], errors="coerce")
        bad = converted.isna() & df[col].notna()
        if bad.any():
            errors.append(
                {
                    "type": "invalid_numeric",
                    "column": col,
                    "count": int(bad.sum()),
                    "rows": [int(i) + 2 for i in df.index[bad][:10]],
                    "message": f"Rows with non-numeric values in {col}",
                }
            )

    duplicates = int(df.duplicated(subset=["Date", "Store ID", "Product ID"]).sum())
    missing_cells = int(df[REQUIRED_COLUMNS].isna().sum().sum())

    clean = df.copy()
    clean["Date"] = parsed_dates
    for col in NUMERIC_DTYPES:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
    clean = clean.dropna(subset=list(NUMERIC_DTYPES) + ["Date"])
    clean = clean.drop_duplicates(subset=["Date", "Store ID", "Product ID"], keep="first")

    return {
        "missing_columns": [],
        "errors": errors,
        "duplicate_rows": duplicates,
        "missing_value_cells": missing_cells,
        "total_rows": int(len(df)),
        "valid_rows": int(len(clean)),
        "clean": clean,
        "preview": df.head(10).astype(str).to_dict(orient="records"),
    }


def parse_csv(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(io.BytesIO(content))
    except Exception as exc:
        raise ImportValidationError(f"Could not parse CSV file: {exc}") from exc


def upsert_records(db: Session, clean: pd.DataFrame) -> dict[str, int]:
    """Insert valid rows, updating existing (store, product, date) rows.

    Repeated imports are therefore safe and never duplicate records.
    """
    imported = 0
    updated = 0

    stores = {s.store_id: s for s in db.query(Store).all()}
    products = {p.product_id: p for p in db.query(Product).all()}

    for _, row in clean.iterrows():
        store_id = str(row["Store ID"])
        product_id = str(row["Product ID"])
        row_date = row["Date"].date()

        if store_id not in stores:
            store = Store(store_id=store_id, region=str(row["Region"]))
            db.add(store)
            db.flush()
            stores[store_id] = store
        if product_id not in products:
            product = Product(
                product_id=product_id,
                category=str(row["Category"]),
                price=float(row["Price"]),
            )
            db.add(product)
            db.flush()
            products[product_id] = product

        payload = {
            "store_fk": stores[store_id].id,
            "product_fk": products[product_id].id,
            "store_id": store_id,
            "product_id": product_id,
            "date": row_date,
            "category": str(row["Category"]),
            "region": str(row["Region"]),
            "inventory_level": int(row["Inventory Level"]),
            "units_sold": int(row["Units Sold"]),
            "units_ordered": int(row["Units Ordered"]),
            "demand_forecast": float(row["Demand Forecast"]),
            "price": float(row["Price"]),
            "discount": int(row["Discount"]),
            "weather_condition": str(row["Weather Condition"]),
            "holiday_promotion": int(row["Holiday/Promotion"]),
            "competitor_pricing": float(row["Competitor Pricing"]),
            "seasonality": str(row["Seasonality"]),
        }

        existing = (
            db.query(InventoryRecord)
            .filter_by(store_id=store_id, product_id=product_id, date=row_date)
            .one_or_none()
        )
        if existing:
            for key, value in payload.items():
                if key in {"store_fk", "product_fk"}:
                    continue
                setattr(existing, key, value)
            updated += 1
        else:
            db.add(InventoryRecord(**payload))
            imported += 1

    db.commit()
    return {"imported_rows": imported, "updated_rows": updated}


def import_csv(db: Session, filename: str, content: bytes) -> ImportJob:
    df = parse_csv(content)
    result = validate_dataframe(df)

    job = ImportJob(
        filename=filename,
        status="completed",
        total_rows=result["total_rows"],
        imported_rows=0,
        updated_rows=0,
        skipped_rows=max(result["total_rows"] - result["valid_rows"], 0),
        invalid_rows=max(result["total_rows"] - result["valid_rows"], 0),
        errors=result["errors"],
        summary={
            "missing_columns": result["missing_columns"],
            "duplicate_rows": result["duplicate_rows"],
            "missing_value_cells": result["missing_value_cells"],
            "valid_rows": result["valid_rows"],
            "preview": result["preview"],
        },
    )
    db.add(job)
    db.commit()

    if result["valid_rows"] > 0:
        counts = upsert_records(db, result["clean"])
        job.imported_rows = counts["imported_rows"]
        job.updated_rows = counts["updated_rows"]
        db.commit()
    else:
        job.status = "failed"
        db.commit()

    db.refresh(job)
    logger.info(
        "Import %s: total=%s imported=%s updated=%s invalid=%s",
        filename,
        job.total_rows,
        job.imported_rows,
        job.updated_rows,
        job.invalid_rows,
    )
    return job
