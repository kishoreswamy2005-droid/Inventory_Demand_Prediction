"""FastAPI application entry point."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api import auth, dashboard, imports, inventory, model, predictions, recommendations, reports
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.database import SessionLocal, init_db
from app.ml.model_loader import model_manager
from app.models.entities import ImportJob, InventoryRecord, ModelRegistry, User

logger = get_logger(__name__)


def _seed_admin(db: Session) -> None:
    """Create an admin from environment variables when provided."""
    email = os.getenv("ADMIN_EMAIL")
    password = os.getenv("ADMIN_PASSWORD")
    if not email or not password or len(password) < 8:
        return
    email = email.lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        if not existing.is_admin:
            existing.is_admin = True
            db.commit()
        return
    db.add(
        User(
            name=os.getenv("ADMIN_NAME", "Administrator"),
            email=email,
            password_hash=hash_password(password),
            is_admin=True,
        )
    )
    db.commit()
    logger.info("Seeded administrator account from environment variables")


def _register_baseline_model(db: Session) -> None:
    row = (
        db.query(ModelRegistry)
        .filter_by(model_name=settings.MODEL_NAME, model_version=settings.MODEL_VERSION)
        .first()
    )
    if row is None:
        db.add(
            ModelRegistry(
                model_name=settings.MODEL_NAME,
                model_version=settings.MODEL_VERSION,
                model_path=str(settings.MODEL_PATH),
                training_date=None,
                evaluation_metrics=settings.NOTEBOOK_METRICS,
                is_active=True,
                notes="Supplied Colab-trained RandomForest pipeline preserved as the baseline "
                "prediction engine. Not retrained.",
            )
        )
        db.commit()


def _seed_dataset_if_empty(db: Session) -> None:
    if not settings.AUTO_SEED_DATASET:
        return
    if db.query(InventoryRecord.id).first() is not None:
        return
    if db.query(ImportJob.id).first() is not None:
        return
    if not settings.DATASET_PATH.exists():
        logger.warning("Dataset not found at %s; skipping automatic import", settings.DATASET_PATH)
        return
    from app.services.import_service import import_csv

    logger.info("Seeding database from %s", settings.DATASET_PATH)
    job = import_csv(db, settings.DATASET_PATH.name, settings.DATASET_PATH.read_bytes())
    logger.info(
        "Dataset seed complete: imported=%s updated=%s invalid=%s",
        job.imported_rows,
        job.updated_rows,
        job.invalid_rows,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(os.getenv("LOG_LEVEL", "INFO"))
    logger.info("Starting %s (%s)", settings.APP_NAME, settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "production" and settings.SECRET_KEY == "dev-only-change-me":
        logger.warning("SECRET_KEY is unset in production; set a strong SECRET_KEY immediately")

    init_db()
    db = SessionLocal()
    try:
        _seed_admin(db)
        _register_baseline_model(db)
        _seed_dataset_if_empty(db)
    finally:
        db.close()

    loaded = model_manager.load()
    if not loaded:
        logger.error("Model failed to load: %s", model_manager.error)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "AI-powered inventory demand prediction API. The prediction engine is the supplied "
        "Colab-trained RandomForest pipeline, preserved as a baseline model."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(RequestValidationError)
async def validation_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [
        {"field": ".".join(str(p) for p in e.get("loc", []) if p != "body"), "message": e.get("msg")}
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    # Never expose stack traces or internals to clients.
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected server error occurred"},
    )


@app.middleware("http")
async def request_logging(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api"):
        logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


@app.get("/health", tags=["system"])
def health() -> dict:
    db_ok = True
    try:
        db = SessionLocal()
        try:
            db.query(InventoryRecord.id).limit(1).first()
        finally:
            db.close()
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "model_loaded": model_manager.ready,
        "environment": settings.ENVIRONMENT,
    }


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(inventory.router)
app.include_router(predictions.router)
app.include_router(recommendations.router)
app.include_router(reports.router)
app.include_router(imports.router)
app.include_router(model.router)
