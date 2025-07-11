from pydantic import BaseModel
from typing import List, Optional, Any
from datetime import datetime
import uuid

class TranscriptionLog(BaseModel):
    request_id: uuid.UUID
    client_id: Optional[str]
    status: str
    filename: Optional[str]
    model: str
    language: Optional[str]
    diarization: Optional[bool]
    error_message: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        orm_mode = True

class PaginatedTranscriptionResponse(BaseModel):
    total: int
    page: int
    size: int
    items: List[TranscriptionLog]

class SystemStats(BaseModel):
    total_requests: int
    completed: int
    failed: int
    processing: int
    success_rate_percent: float