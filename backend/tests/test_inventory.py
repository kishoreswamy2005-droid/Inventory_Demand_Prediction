"""Inventory endpoint tests: list, filters, CRUD, role enforcement."""
from __future__ import annotations

from datetime import date


def test_list_inventory(client, admin_headers):
    resp = client.get("/api/inventory", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 20  # 5 days x 2 stores x 2 products
    assert len(body["items"]) == 20
    item = body["items"][0]
    for key in ("store_id", "product_id", "date", "inventory_level", "inventory_status", "days_of_cover"):
        assert key in item


def test_list_inventory_pagination(client, admin_headers):
    resp = client.get(
        "/api/inventory?page=1&page_size=5", headers=admin_headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 5
    assert body["pages"] == 4


def test_list_inventory_store_filter(client, admin_headers):
    resp = client.get("/api/inventory?store=S001", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert all(i["store_id"] == "S001" for i in body["items"])


def test_list_inventory_search(client, admin_headers):
    resp = client.get("/api/inventory?search=P002", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 10
    assert all(i["product_id"] == "P002" for i in body["items"])


def test_product_history(client, admin_headers):
    resp = client.get("/api/inventory/P001", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert len(rows) == 10  # 5 days x 2 stores
    assert all(r["product_id"] == "P001" for r in rows)


def test_product_history_unknown_product_404(client, admin_headers):
    resp = client.get("/api/inventory/NOPE", headers=admin_headers)
    assert resp.status_code == 404


def test_create_record_requires_admin(client, user_headers, admin_headers):
    payload = {
        "store_id": "S001",
        "product_id": "P001",
        "date": "2024-02-01",
        "category": "Electronics",
        "region": "East",
        "inventory_level": 50,
        "units_sold": 5,
        "price": 99.99,
    }
    resp = client.post("/api/inventory", json=payload, headers=user_headers)
    assert resp.status_code == 403

    resp = client.post("/api/inventory", json=payload, headers=admin_headers)
    assert resp.status_code == 201, resp.text
    assert resp.json()["inventory_level"] == 50


def test_create_duplicate_record_409(client, admin_headers):
    payload = {
        "store_id": "S001",
        "product_id": "P001",
        "date": "2024-01-01",
        "category": "Electronics",
        "region": "East",
        "inventory_level": 50,
        "units_sold": 5,
        "price": 99.99,
    }
    resp = client.post("/api/inventory", json=payload, headers=admin_headers)
    assert resp.status_code == 409


def test_update_record(client, admin_headers):
    # Find any record id first
    listing = client.get("/api/inventory?page_size=1", headers=admin_headers).json()
    record_id = listing["items"][0]["id"]
    resp = client.put(
        f"/api/inventory/{record_id}",
        json={"inventory_level": 42},
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["inventory_level"] == 42


def test_update_record_empty_body_400(client, admin_headers):
    listing = client.get("/api/inventory?page_size=1", headers=admin_headers).json()
    record_id = listing["items"][0]["id"]
    resp = client.put(
        f"/api/inventory/{record_id}", json={}, headers=admin_headers
    )
    assert resp.status_code == 400


def test_delete_record_admin_only(client, user_headers, admin_headers):
    payload = {
        "store_id": "S002",
        "product_id": "P002",
        "date": "2024-03-01",
        "category": "Toys",
        "region": "West",
        "inventory_level": 10,
        "units_sold": 1,
        "price": 19.99,
    }
    created = client.post("/api/inventory", json=payload, headers=admin_headers)
    assert created.status_code == 201
    record_id = created.json()["id"]

    resp = client.delete(f"/api/inventory/{record_id}", headers=user_headers)
    assert resp.status_code == 403

    resp = client.delete(f"/api/inventory/{record_id}", headers=admin_headers)
    assert resp.status_code == 204

    resp = client.get("/api/inventory/NOPE", headers=admin_headers)
    assert resp.status_code == 404
