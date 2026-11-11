"""Auth endpoint tests: registration, login, roles, protection."""
from __future__ import annotations

from tests.conftest import login


def test_register_and_me(client, seeded):
    resp = client.post(
        "/api/auth/register",
        json={"name": "New User", "email": "new@example.com", "password": "StrongPass1!"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "new@example.com"
    # The seeded admin already exists, so this account is a regular user.
    assert body["user"]["is_admin"] is False

    headers = {"Authorization": f"Bearer {body['access_token']}"}
    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["name"] == "New User"


def test_register_duplicate_email_rejected(client, seeded):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Dup", "email": seeded["admin"], "password": "Whatever123"},
    )
    assert resp.status_code == 409


def test_register_validates_password_length(client):
    resp = client.post(
        "/api/auth/register",
        json={"name": "Weak", "email": "weak@example.com", "password": "short"},
    )
    assert resp.status_code == 422


def test_login_wrong_password(client, seeded):
    resp = client.post(
        "/api/auth/login", json={"email": seeded["admin"], "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_login_json_endpoint(client, seeded):
    headers = login(client, seeded["admin"], "AdminPass123!")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_admin"] is True


def test_oauth2_form_token_endpoint(client, seeded):
    resp = client.post(
        "/api/auth/token", data={"username": seeded["user"], "password": "UserPass123!"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]


def test_protected_routes_require_token(client, seeded):
    for path in (
        "/api/dashboard/summary",
        "/api/inventory",
        "/api/predictions/history",
        "/api/recommendations/reorder",
        "/api/reports/sales",
        "/api/model/status",
    ):
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} should require auth, got {resp.status_code}"


def test_first_registered_user_is_admin(client):
    """With no users in the DB, the first registration becomes admin."""
    resp = client.post(
        "/api/auth/register",
        json={"name": "First User", "email": "first@example.com", "password": "FirstPass123"},
    )
    assert resp.status_code == 201
    assert resp.json()["user"]["is_admin"] is True
