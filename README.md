# AI Inventory Demand Prediction System

A production-oriented inventory demand prediction platform: **FastAPI** backend,
**React + TypeScript + Vite + Tailwind** frontend, **SQLAlchemy + Alembic**
persistence (SQLite for local dev, PostgreSQL for production), and the supplied
**Colab-trained RandomForest pipeline** preserved as the baseline prediction
engine.

> **Important:** predictions are **predicted sales**, not guaranteed demand.
> See [Model limitations](#model-limitations--leakage-risks).

---

## Repository layout

```
.
├── Inventory_Demand_Prediction.ipynb   # Supplied notebook (source of truth for metrics)
├── inventory_demand_model.pkl          # Supplied trained pipeline (never retrained/overwritten)
├── dataset/retail_store_inventory.csv  # Supplied dataset (73,100 rows)
├── archive (2).zip                     # Original archive (preserved)
├── backend/                            # FastAPI application + tests
│   ├── app/
│   │   ├── api/                        # auth, dashboard, inventory, predictions,
│   │   │                               # recommendations, reports, imports, model
│   │   ├── core/                       # config, security (JWT+bcrypt), deps, logging
│   │   ├── ml/                         # feature schema, model loader, prediction,
│   │   │                               # metrics, validation
│   │   ├── models/                     # SQLAlchemy entities
│   │   ├── schemas/                    # Pydantic request/response models
│   │   ├── services/                   # inventory, import, recommendation, analytics
│   │   └── main.py                     # app factory, CORS, lifespan, auto-seed
│   ├── alembic/                        # migrations (initial schema)
│   └── tests/                          # 49 pytest tests
├── frontend/                           # React + TS + Vite + Tailwind + Recharts
│   └── src/
│       ├── pages/                      # dashboard, inventory, predict, recommendations,
│       │                               # reports, history, model, login, register
│       ├── components/                 # layout, shared UI
│       └── context/                    # auth, toast
├── docker-compose.yml                  # postgres + backend + frontend
├── Dockerfile.backend / Dockerfile.frontend
├── .env.example                        # all configuration keys (no secrets)
└── prompt.txt                          # original build specification
```

---

## Quick start (local, no Docker)

Requires **Python 3.11** (the model was pickled with scikit-learn 1.6.1 and is
not loadable by newer sklearn major versions).

### 1. Backend

```powershell
# from the repository root (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --port 8000
```

On first start the backend:
1. creates tables (`init_db`),
2. seeds an admin if `ADMIN_EMAIL`/`ADMIN_PASSWORD` are set,
3. registers the baseline model in the registry,
4. **auto-seeds the dataset** into the empty database (73,100 rows, ~3 min),
5. loads `inventory_demand_model.pkl`.

Verify: <http://127.0.0.1:8000/health> · docs at <http://127.0.0.1:8000/docs>.

### 2. Frontend

```powershell
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

### 3. Tests

```powershell
# backend: 49 tests
cd backend ; python -m pytest tests/ -q

# frontend: 10 tests + type-checked production build
cd frontend ; npm test ; npm run build
```

---

## Docker Compose (PostgreSQL + both apps)

```powershell
# provide secrets first — never commit them
Copy-Item .env.example .env   # then edit SECRET_KEY, ADMIN_*, POSTGRES_PASSWORD

docker compose up --build
```

| Service  | URL                      |
|----------|--------------------------|
| Frontend | <http://localhost:8080>  |
| API      | <http://localhost:8000>  |
| Postgres | `localhost:5432`         |

Docker is optional — the local SQLite flow above is fully supported.

---

## Configuration

All keys are documented in [`.env.example`](.env.example). Highlights:

| Key | Default | Purpose |
|-----|---------|---------|
| `SECRET_KEY` | dev placeholder | **Must be set in production** (JWT signing) |
| `DATABASE_URL` | SQLite file | PostgreSQL in production |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | unset | Bootstrap admin (≥8 char password) |
| `AUTO_SEED_DATASET` | `true` | Seed DB from CSV when empty |
| `DAYS_CRITICAL/LOW/OVERSTOCK` | 1 / 3 / 30 | Days-of-cover status thresholds |
| `DEFAULT_LEAD_TIME_DAYS` | 7 | Reorder lead-time assumption |
| `DEFAULT_SERVICE_LEVEL` | 0.95 | Safety-stock service level |
| `PREDICTION_RATE_LIMIT` | 120/min | Per-IP prediction rate limit |

Secrets are read from the environment only; no credential is hardcoded or
committed. `.env` is git-ignored.

---

## API overview

All routes below require `Authorization: Bearer <token>` except `/health`,
`/api/auth/register` and `/api/auth/login`.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/auth/register` | Register (first user becomes admin) |
| POST | `/api/auth/login` | JWT login (JSON) |
| POST | `/api/auth/token` | OAuth2 form login (Swagger Authorize) |
| GET | `/api/auth/me` | Current user |
| GET | `/api/dashboard/summary` | KPI cards (real DB aggregates) |
| GET | `/api/dashboard/sales-trend` | `granularity=day\|month` |
| GET | `/api/dashboard/product-performance` | Top/bottom products |
| GET | `/api/dashboard/category-performance` | By category |
| GET | `/api/dashboard/store-performance` | By store |
| GET | `/api/dashboard/inventory-overview` | Status buckets |
| GET | `/api/dashboard/actual-vs-predicted` | Actual vs saved predictions |
| GET | `/api/dashboard/filters` | Distinct filter values |
| GET | `/api/inventory` | Paginated list + search/filters/status |
| GET | `/api/inventory/{product_id}` | Product history |
| POST | `/api/inventory` | Create (admin) |
| PUT | `/api/inventory/{id}` | Update (admin) |
| DELETE | `/api/inventory/{id}` | Delete (admin) |
| POST | `/api/predictions/predict` | Run model + persist result |
| GET | `/api/predictions/history` | Paginated prediction history |
| GET | `/api/predictions/{id}` | Single prediction |
| GET | `/api/recommendations/reorder` | Reorder suggestions (configurable) |
| GET | `/api/recommendations/low-stock` | Low-stock list |
| GET | `/api/reports/sales` · `/inventory` · `/predictions` | Reports |
| GET | `/api/reports/export/csv?report=…` | CSV download |
| POST | `/api/import/csv` | Admin CSV import (idempotent upsert) |
| GET | `/api/import/jobs` | Import history (admin) |
| GET | `/api/model/status` | Model readiness + path |
| GET | `/api/model/metadata` | Metrics, features, limitations |
| GET | `/api/model/performance` | Notebook metrics + live monitoring |
| GET | `/health` | Liveness/readiness |

---

## Database tables

| Table | Purpose |
|-------|---------|
| `users` | Accounts (bcrypt hashes, admin flag) |
| `stores` / `products` | Dimensions (created automatically by import) |
| `inventory_records` | Daily facts; unique `(store, product, date)` |
| `predictions` | Every model run with full input features (audit trail) |
| `model_registry` | Registered models + notebook metrics |
| `import_jobs` | CSV import audit (rows, errors, preview) |
| `alembic_version` | Migration state |

Migrations: `cd backend ; alembic upgrade head`

---

## Model limitations & leakage risks

The prediction engine is the **supplied model, used as-is** — never retrained,
never substituted. Known caveats (also surfaced in the UI at `/model`):

1. **`Inventory Level` timing is unverified.** If it is measured *after* same-day
   sales, it leaks same-day information into the features.
2. **`Units Sold` is censored by stockouts.** Out-of-stock rows understate true
   demand, so the model may under-predict.
3. **No lag/rolling features.** The pipeline uses contemporaneous tabular
   features only — it is a same-day estimator, not a multi-day forecasting
   engine.
4. **WAPE ≈ 51%** on the chronological 80/20 split (MAE 69.18, RMSE 88.59,
   R² 0.33). Use outputs as directional planning aids, **not guaranteed demand**.

Notebook metrics shown in the UI come from the notebook's saved outputs
(`MAE 69.18 / RMSE 88.59 / R² 0.3298 / WAPE 50.91%`, split `2023-08-08`) and are
reproduced exactly by `tests` — no metric is invented.

---

## Business rules

- **Inventory status** derives from *days of cover* (`inventory / avg daily
  sales`) using the configurable thresholds above:
  `Critical ≤ 1 d`, `Low ≤ 3 d`, `Healthy ≤ 30 d`, `Overstocked > 30 d`.
- **Reorder quantity** = `max(0, expected_daily × lead_time + z(service) × σ ×
  √lead_time − inventory)`. Lead time and service level are **assumptions** —
  every result is labelled *illustrative* in the API and UI.
- **CSV import** is an idempotent upsert on `(store, product, date)`: repeated
  imports update instead of duplicating, and invalid rows are reported (never
  silently discarded).
- **Rate limiting** applies to `/api/predictions/predict` (default 120/min/IP).

---

## Responsive & themes

The UI is tested at **1440 / 1024 / 768 / 390 / 360 px** breakpoints with a
collapsible sidebar under `lg`, and ships **light/dark themes** (persisted in
`localStorage`, respecting `prefers-color-scheme`).

---

## Verification status

| Check | Result |
|-------|--------|
| Backend tests | ✅ 49/49 (`pytest -q`) |
| Frontend tests | ✅ 10/10 (`vitest`) |
| Type-check + build | ✅ `tsc -b && vite build` |
| Live API smoke (seeded 73,100 rows) | ✅ health, auth, dashboard, predict, reorder, reports, model |
| Model loads from supplied pickle | ✅ sklearn 1.6.1 / Python 3.11 |
