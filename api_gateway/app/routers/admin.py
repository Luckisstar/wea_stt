from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from .. import schemas, models
from ..db_session import get_db

router = APIRouter()

@router.get("/admin/transcriptions", response_model=schemas.PaginatedTranscriptionResponse, tags=["Admin"])
def get_transcription_logs(
    page: int = 1,
    size: int = Query(20, gt=0, le=100),
    status: str = None,
    client_id: str = None,
    db: Session = Depends(get_db)
):
    # ... (이전과 동일)
    pass

@router.get("/admin/stats", response_model=schemas.SystemStats, tags=["Admin"])
def get_system_stats(db: Session = Depends(get_db)):
    total_requests = db.query(models.Transcription).count()
    completed_requests = db.query(models.Transcription).filter(models.Transcription.status == "completed").count()
    failed_requests = db.query(models.Transcription).filter(models.Transcription.status == "failed").count()
    processing_requests = db.query(models.Transcription).filter(models.Transcription.status == "processing").count()

    success_rate_percent = 0.0
    if total_requests > 0:
        success_rate_percent = (completed_requests / total_requests) * 100

    return schemas.SystemStats(
        total_requests=total_requests,
        completed=completed_requests,
        failed=failed_requests,
        processing=processing_requests,
        success_rate_percent=round(success_rate_percent, 2)
    )
