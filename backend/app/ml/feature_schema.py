from app.core.config import settings

# Feature order is fixed by the trained pipeline: never reorder or rename.
FEATURE_COLUMNS = [
    "Store ID",
    "Product ID",
    "Category",
    "Region",
    "Inventory Level",
    "Price",
    "Discount",
    "Weather Condition",
    "Holiday/Promotion",
    "Competitor Pricing",
    "Seasonality",
    "Year",
    "Month",
    "Day",
    "DayOfWeek",
    "DayOfYear",
]

CATEGORICAL_COLUMNS = [
    "Store ID",
    "Product ID",
    "Category",
    "Region",
    "Weather Condition",
    "Seasonality",
]

NUMERICAL_COLUMNS = [
    "Inventory Level",
    "Price",
    "Discount",
    "Holiday/Promotion",
    "Competitor Pricing",
    "Year",
    "Month",
    "Day",
    "DayOfWeek",
    "DayOfYear",
]

DATE_DERIVED_COLUMNS = ["Year", "Month", "Day", "DayOfWeek", "DayOfYear"]

# Known category vocabularies observed in the notebook/model. The pipeline also
# uses handle_unknown="ignore", so unknown values remain safe but uninformative.
ALLOWED_VALUES = {
    "Store ID": ["S001", "S002", "S003", "S004", "S005"],
    "Category": ["Clothing", "Electronics", "Furniture", "Groceries", "Toys"],
    "Region": ["East", "North", "South", "West"],
    "Weather Condition": ["Cloudy", "Rainy", "Snowy", "Sunny"],
    "Seasonality": ["Autumn", "Spring", "Summer", "Winter"],
    "Holiday/Promotion": [0, 1],
}

MODEL_NAME = settings.MODEL_NAME
MODEL_VERSION = settings.MODEL_VERSION
