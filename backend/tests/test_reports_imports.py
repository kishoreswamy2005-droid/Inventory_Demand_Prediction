"""Report, CSV import, and health endpoint tests."""
from __future__ import annotations

import io


def test_sales_report(client, admin_headers):
    resp = client.get("/api/reports/sales", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["report_type"]
    assert body["row_count"] == len(body["rows"])
    assert body["rows"]


def test_sales_report_csv_export(client, admin_headers):
    resp = client.get("/api/reports/export/csv?report=sales", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")
    text = resp.text
    assert text.splitlines()[0]  # has a header row


def test_inventory_report(client, admin_headers):
    resp = client.get("/api/reports/inventory", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["row_count"] == len(body["rows"])


def test_prediction_report(client, admin_headers):
    resp = client.get("/api/reports/predictions", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["row_count"] == len(body["rows"])


def _csv(content: str) -> dict:
    return {"files": {"file": ("test.csv", io.BytesIO(content.encode()), "text/csv")}}


def test_import_requires_admin(client, user_headers):
    resp = client.post(
        "/api/import/csv",
        files={"file": ("test.csv", io.BytesIO(b"Date,Store ID\n"), "text/csv")},
        headers=user_headers,
    )
    assert resp.status_code == 403


def test_import_rejects_non_csv(client, admin_headers):
    resp = client.post(
        "/api/import/csv",
        files={"file": ("test.txt", io.BytesIO(b"hello"), "text/plain")},
        headers=admin_headers,
    )
    assert resp.status_code == 415


def test_import_rejects_empty_file(client, admin_headers):
    resp = client.post(
        "/api/import/csv",
        files={"file": ("test.csv", io.BytesIO(b""), "text/csv")},
        headers=admin_headers,
    )
    assert resp.status_code == 400


def test_import_rejects_missing_columns(client, admin_headers):
    resp = client.post(
        "/api/import/csv",
        files={"file": ("bad.csv", io.BytesIO(b"foo,bar\n1,2\n"), "text/csv")},
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_import_valid_csv_is_idempotent(client, admin_headers):
    header = (
        "Date,Store ID,Product ID,Category,Region,Inventory Level,Units Sold,"
        "Units Ordered,Demand Forecast,Price,Discount,Weather Condition,"
        "Holiday/Promotion,Competitor Pricing,Seasonality\n"
    )
    row = "2024-06-01,S001,P001,Electronics,East,80,12,10,13.5,99.99,5,Sunny,0,95.0,Summer\n"
    payload = header + row

    first = client.post(
        "/api/import/csv",
        files={"file": ("seed.csv", io.BytesIO(payload.encode()), "text/csv")},
        headers=admin_headers,
    )
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["imported_rows"] + body["updated_rows"] >= 1
    assert body["missing_columns"] == []

    # Same file again: idempotent — rows update, never duplicate or silently drop.
    second = client.post(
        "/api/import/csv",
        files={"file": ("seed.csv", io.BytesIO(payload.encode()), "text/csv")},
        headers=admin_headers,
    )
    assert second.status_code == 201, second.text
    assert second.json()["imported_rows"] == 0

    jobs = client.get("/api/import/jobs", headers=admin_headers)
    assert jobs.status_code == 200
    assert len(jobs.json()) >= 2


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in {"ok", "degraded"}
    assert body["database"] in {"connected", "unavailable"}
    assert isinstance(body["model_loaded"], bool)
