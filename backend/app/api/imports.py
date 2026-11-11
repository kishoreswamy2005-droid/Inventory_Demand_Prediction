"""Admin-only dataset import endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, require_admin
from app.models.entities import ImportJob, User
from app.schemas import ImportSummary
from app.services.import_service import ImportValidationError, import_csv

router = APIRouter(prefix="/api/import", tags=["import"], dependencies=[Depends(require_admin)])

ALLOWED_EXTENSIONS = {".csv"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _summary(job: ImportJob) -> ImportSummary:
    return ImportSummary(
        job_id=job.id,
        filename=job.filename,
        status=job.status,
        total_rows=job.total_rows,
        imported_rows=job.imported_rows,
        updated_rows=job.updated_rows,
        skipped_rows=job.skipped_rows,
        invalid_rows=job.invalid_rows,
        errors=job.errors or [],
        preview=(job.summary or {}).get("preview", []),
        missing_columns=(job.summary or {}).get("missing_columns", []),
        duplicate_rows=(job.summary or {}).get("duplicate_rows", 0),
        missing_value_cells=(job.summary or {}).get("missing_value_cells", 0),
    )


@router.post("/csv", response_model=ImportSummary, status_code=status.HTTP_201_CREATED)
async def upload_csv(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
) -> ImportSummary:
    if file.filename is None or "." not in file.filename:
        raise HTTPException(status_code=400, detail="A CSV file is required")
    ext = "." + file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Only .csv files are accepted")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 50 MB upload limit")

    try:
        job = import_csv(db, file.filename, content)
    except ImportValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if job.status == "failed":
        raise HTTPException(
            status_code=422,
            detail={
                "message": "No valid rows to import",
                "errors": job.errors,
                "summary": job.summary,
            },
        )
    return _summary(job)


@router.get("/jobs", response_model=list[ImportSummary])
def jobs(db: Session = Depends(get_db), _admin: User = Depends(require_admin)) -> list[ImportSummary]:
    rows = db.query(ImportJob).order_by(ImportJob.created_at.desc()).limit(20).all()
    return [_summary(r) for r in rows]
