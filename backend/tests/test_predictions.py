"""Model status/metadata and prediction endpoint tests (real model, no mocks)."""
from __future__ import annotations

from datetime import date


def _predict_payload(**overrides):
    payload = {
        "store_id": "S001",
        "product_id": "P001",
        "category": "Electronics",
        "region": "East",
        "inventory_level": 120,
        "price": 99.99,
        "discount": 5,
        "weather_condition": "Sunny",
        "holiday_promotion": 0,
        "competitor_pricing": 95.0,
        "seasonality": "Winter",
        "prediction_date": date.today().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_model_status(client, admin_headers):
    resp = client.get("/api/model/status", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ready"] is True, body.get("error")
    assert body["model_name"]
    assert len(body["feature_columns"]) == 16


def test_model_metadata(client, admin_headers):
    resp = client.get("/api/model/metadata", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    metrics = body["metrics"]
    # Metrics must be the notebook's saved values, not invented.
    assert metrics["mae"] == 69.18
    assert metrics["rmse"] == 88.59
    assert metrics["r2"] == 0.3298
    assert metrics["wape_percent"] == 50.91
    assert body["limitations"]
    assert any("Inventory Level" in lim for lim in body["limitations"])


def test_predict_persists_and_returns_real_model_output(client, user_headers):
    resp = client.post(
        "/api/predictions/predict", json=_predict_payload(), headers=user_headers
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["predicted_units_sold"] >= 0
    assert isinstance(body["predicted_units_sold_raw"], float)
    assert body["model_name"]

    # The prediction must appear in history (persisted, not ephemeral).
    history = client.get("/api/predictions/history", headers=user_headers)
    assert history.status_code == 200
    page = history.json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == body["id"]

    # And be retrievable individually.
    single = client.get(f"/api/predictions/{body['id']}", headers=user_headers)
    assert single.status_code == 200
    assert single.json()["predicted_units_sold"] == body["predicted_units_sold"]


def test_predict_unknown_store_rejected(client, user_headers):
    resp = client.post(
        "/api/predictions/predict",
        json=_predict_payload(store_id="S999"),
        headers=user_headers,
    )
    assert resp.status_code == 422
    assert "Unknown Store ID" in resp.json()["detail"]


def test_predict_unknown_product_rejected(client, user_headers):
    resp = client.post(
        "/api/predictions/predict",
        json=_predict_payload(product_id="P999"),
        headers=user_headers,
    )
    assert resp.status_code == 422
    assert "Unknown Product ID" in resp.json()["detail"]


def test_predict_validation_bounds(client, user_headers):
    resp = client.post(
        "/api/predictions/predict",
        json=_predict_payload(discount=150),
        headers=user_headers,
    )
    assert resp.status_code == 422


def test_predict_requires_auth(client):
    resp = client.post("/api/predictions/predict", json=_predict_payload())
    assert resp.status_code == 401


def test_prediction_history_filters(client, user_headers):
    client.post("/api/predictions/predict", json=_predict_payload(), headers=user_headers)
    client.post(
        "/api/predictions/predict",
        json=_predict_payload(product_id="P002", category="Toys"),
        headers=user_headers,
    )

    resp = client.get(
        "/api/predictions/history?product=P002", headers=user_headers
    )
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 1
    assert page["items"][0]["product_id"] == "P002"
