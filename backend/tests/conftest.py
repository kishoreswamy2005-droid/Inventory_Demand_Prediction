"""Shared pytest fixtures: in-memory SQLite app, seeded users, auth headers."""
from __future__ import annotations

import os
import sys
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.core.deps import get_db  # noqa: E402
from app.models.entities import InventoryRecord, Product, Store, User  # noqa: E402
from app.core.security import hash_password  # noqa: E402


@pytest.fixture()
def db_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    yield factory
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture()
def client(db_session_factory):
    def _override_db():
        session = db_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def seeded(db_session_factory):
    """Seed a minimal but realistic dataset: 2 stores, 2 products, records."""
    session = db_session_factory()
    admin = User(
        name="Test Admin",
        email="admin@test.dev",
        password_hash=hash_password("AdminPass123!"),
        is_admin=True,
    )
    regular = User(
        name="Test User",
        email="user@test.dev",
        password_hash=hash_password("UserPass123!"),
        is_admin=False,
    )
    session.add_all([admin, regular])

    stores = [
        Store(store_id="S001", region="East"),
        Store(store_id="S002", region="West"),
    ]
    products = [
        Product(product_id="P001", category="Electronics", price=99.99),
        Product(product_id="P002", category="Toys", price=19.99),
    ]
    session.add_all(stores + products)

    rows = []
    for day in range(1, 6):
        for store in ("S001", "S002"):
            for product in ("P001", "P002"):
                rows.append(
                    InventoryRecord(
                        date=date(2024, 1, day),
                        store_id=store,
                        product_id=product,
                        category="Electronics" if product == "P001" else "Toys",
                        region="East" if store == "S001" else "West",
                        inventory_level=100 + day,
                        units_sold=10 + day,
                        demand_forecast=11 + day,
                        price=99.99 if product == "P001" else 19.99,
                        discount=5,
                        weather_condition="Sunny",
                        holiday_promotion=0,
                        competitor_pricing=95.0 if product == "P001" else 18.0,
                        seasonality="Winter",
                        units_ordered=20,
                    )
                )
    session.add_all(rows)
    session.commit()
    session.close()
    return {"admin": "admin@test.dev", "user": "user@test.dev"}


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client, seeded):
    return login(client, seeded["admin"], "AdminPass123!")


@pytest.fixture()
def user_headers(client, seeded):
    return login(client, seeded["user"], "UserPass123!")
