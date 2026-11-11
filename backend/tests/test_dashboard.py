"""Dashboard endpoint tests: values come from the seeded database only."""
from __future__ import annotations


def test_summary_shape_and_real_values(client, admin_headers):
    resp = client.get("/api/dashboard/summary", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in (
        "total_products",
        "total_stores",
        "total_units_sold",
        "current_inventory",
        "predicted_demand",
        "low_stock_products",
        "overstocked_products",
        "critical_stock_products",
        "date_range",
    ):
        assert key in body
    # Seeded fixture: 2 stores, 2 products, 20 records (5 days x 2 x 2)
    assert body["total_stores"] == 2
    assert body["total_products"] == 2
    assert body["total_units_sold"] == sum(range(11, 16)) * 4  # (11..15) * 4 rows/day


def test_sales_trend_monthly(client, admin_headers):
    resp = client.get(
        "/api/dashboard/sales-trend?granularity=month", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["granularity"] == "month"
    assert isinstance(body["points"], list) and body["points"]
    # All seeded dates fall in 2024-01
    assert body["points"][0]["label"].startswith("2024-01")


def test_sales_trend_rejects_bad_granularity(client, admin_headers):
    resp = client.get(
        "/api/dashboard/sales-trend?granularity=year", headers=admin_headers
    )
    assert resp.status_code == 422


def test_product_performance_ordering(client, admin_headers):
    resp = client.get("/api/dashboard/product-performance?top=5", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) <= 5
    values = [i.get("units_sold", i.get("value", 0)) for i in items]
    assert values == sorted(values, reverse=True)


def test_actual_vs_predicted_has_note(client, admin_headers):
    resp = client.get("/api/dashboard/actual-vs-predicted", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "note" in body and "never treated as an actual" in body["note"]
    assert isinstance(body["points"], list)


def test_filters_endpoint(client, admin_headers):
    resp = client.get("/api/dashboard/filters", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "S001" in body.get("stores", [])
    assert "Electronics" in body.get("categories", [])


def test_dashboard_respects_date_filter(client, admin_headers):
    resp = client.get(
        "/api/dashboard/summary?start=2024-01-01&end=2024-01-02", headers=admin_headers
    )
    assert resp.status_code == 200, resp.text
    # 2 days x 2 stores x 2 products = 8 rows worth of sales
    assert resp.json()["total_units_sold"] == sum(range(11, 13)) * 4
