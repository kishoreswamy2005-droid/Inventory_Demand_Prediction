"""Reorder recommendation and low-stock endpoint tests."""
from __future__ import annotations


def test_reorder_returns_list_with_assumptions(client, admin_headers):
    resp = client.get("/api/recommendations/reorder", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert isinstance(items, list) and items
    item = items[0]
    for key in (
        "product_id",
        "store_id",
        "current_inventory",
        "predicted_sales",
        "avg_daily_sales",
        "safety_stock",
        "recommended_reorder_quantity",
        "days_of_cover",
        "risk_level",
        "reason",
        "assumptions",
        "illustrative",
    ):
        assert key in item, f"missing {key}"
    # Recommendations are explicitly labelled illustrative per spec.
    assert item["illustrative"] is True
    assert item["assumptions"]["lead_time_days"] == 7
    assert item["assumptions"]["service_level"] == 0.95
    assert item["recommended_reorder_quantity"] >= 0


def test_reorder_configurable_thresholds(client, admin_headers):
    resp = client.get(
        "/api/recommendations/reorder?lead_time_days=14&service_level=0.99",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert items
    assert items[0]["assumptions"]["lead_time_days"] == 14
    assert items[0]["assumptions"]["service_level"] == 0.99


def test_reorder_rejects_invalid_service_level(client, admin_headers):
    resp = client.get(
        "/api/recommendations/reorder?service_level=0.3", headers=admin_headers
    )
    assert resp.status_code == 422


def test_low_stock_sorted_by_cover(client, admin_headers):
    resp = client.get("/api/recommendations/low-stock", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "threshold_days" in body and "items" in body
    covers = [i["days_of_cover"] for i in body["items"]]
    assert covers == sorted(covers)
    # Seeded inventory is high relative to sales, so few/no low-stock items.
    for item in body["items"]:
        assert item["days_of_cover"] <= body["threshold_days"]


def test_low_stock_tight_threshold_includes_items(client, admin_headers):
    resp = client.get(
        "/api/recommendations/low-stock?threshold_days=365", headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] > 0  # every pair has finite cover under a huge threshold
