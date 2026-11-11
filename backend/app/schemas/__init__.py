"""Pydantic request/response schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------- auth
class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- dashboard
class DashboardSummary(BaseModel):
    total_products: int
    total_stores: int
    total_units_sold: int
    current_inventory: int
    predicted_demand: int
    low_stock_products: int
    overstocked_products: int
    critical_stock_products: int
    date_range: dict[str, Any]


class ChartPoint(BaseModel):
    label: str
    value: float
    secondary: float | None = None


# ---------------------------------------------------------------- inventory
class InventoryRecordOut(ORMModel):
    id: int
    store_id: str
    product_id: str
    date: date
    category: str
    region: str
    inventory_level: int
    units_sold: int
    price: float
    discount: int
    weather_condition: str
    holiday_promotion: int
    competitor_pricing: float
    seasonality: str
    inventory_status: str | None = None
    days_of_cover: float | None = None


class InventoryUpdate(BaseModel):
    inventory_level: int | None = Field(default=None, ge=0)
    price: float | None = Field(default=None, ge=0)
    discount: int | None = Field(default=None, ge=0, le=100)
    units_sold: int | None = Field(default=None, ge=0)


class InventoryCreate(InventoryUpdate):
    store_id: str
    product_id: str
    date: date
    category: str
    region: str
    inventory_level: int = Field(ge=0)
    units_sold: int = Field(ge=0)
    units_ordered: int = Field(default=0, ge=0)
    demand_forecast: float = 0.0
    price: float = Field(ge=0)
    discount: int = Field(default=0, ge=0, le=100)
    weather_condition: str = "Sunny"
    holiday_promotion: int = Field(default=0, ge=0, le=1)
    competitor_pricing: float = Field(default=0.0, ge=0)
    seasonality: str = "Summer"


# ---------------------------------------------------------------- prediction
class PredictionRequest(BaseModel):
    store_id: str
    product_id: str
    category: str
    region: str
    inventory_level: int = Field(ge=0, le=1_000_000)
    price: float = Field(ge=0, le=100_000)
    discount: int = Field(ge=0, le=100)
    weather_condition: str
    holiday_promotion: int = Field(ge=0, le=1)
    competitor_pricing: float = Field(ge=0, le=100_000)
    seasonality: str
    prediction_date: date

    @field_validator("prediction_date")
    @classmethod
    def _reasonable_date(cls, v: date) -> date:
        if v.year < 2000 or v.year > 2100:
            raise ValueError("prediction_date must be between 2000 and 2100")
        return v


class PredictionOut(BaseModel):
    id: int | None = None
    store_id: str
    product_id: str
    prediction_date: date
    predicted_units_sold: int
    predicted_units_sold_raw: float
    model_name: str
    model_version: str
    status: str
    rounding: str
    created_at: datetime | None = None
    input_features: dict[str, Any] | None = None


class PredictionHistoryOut(ORMModel):
    id: int
    user_id: int | None
    store_id: str
    product_id: str
    prediction_date: date
    predicted_units_sold: float
    model_name: str
    model_version: str
    created_at: datetime
    input_features: dict[str, Any]


# ---------------------------------------------------------------- recommendations
class ReorderConfig(BaseModel):
    lead_time_days: float = Field(default=7, ge=0, le=365)
    service_level: float = Field(default=0.95, gt=0.5, lt=0.9999)
    reorder_threshold_days: float = Field(default=3, ge=0, le=365)


class ReorderRecommendation(BaseModel):
    product_id: str
    store_id: str
    category: str
    region: str
    current_inventory: int
    predicted_sales: float
    avg_daily_sales: float
    demand_std: float
    safety_stock: float
    demand_during_lead_time: float
    recommended_reorder_quantity: int
    days_of_cover: float | None = None  # None when the pair has no sales history
    risk_level: str
    reason: str
    assumptions: dict[str, Any]
    illustrative: bool = True


# ---------------------------------------------------------------- reports
class ReportRow(BaseModel):
    label: str
    metrics: dict[str, Any]


class ReportResponse(BaseModel):
    report_type: str
    generated_at: datetime
    filters: dict[str, Any]
    row_count: int
    rows: list[dict[str, Any]]


# ---------------------------------------------------------------- import
class ImportSummary(BaseModel):
    job_id: int
    filename: str
    status: str
    total_rows: int
    imported_rows: int
    updated_rows: int
    skipped_rows: int
    invalid_rows: int
    errors: list[dict[str, Any]]
    preview: list[dict[str, Any]]
    missing_columns: list[str]
    duplicate_rows: int
    missing_value_cells: int


# ---------------------------------------------------------------- model
class ModelStatus(BaseModel):
    ready: bool
    model_name: str
    model_version: str
    model_path: str
    error: str | None = None
    feature_columns: list[str]


class ModelMetadata(BaseModel):
    model_name: str
    model_version: str
    training_date: date | None
    metrics: dict[str, Any]
    limitations: list[str]
    feature_columns: list[str]
    categorical_columns: list[str]
    numerical_columns: list[str]
    validation: dict[str, Any]
