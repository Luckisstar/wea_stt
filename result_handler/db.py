import uuid
from sqlalchemy import create_engine, Column, String, DateTime, JSON, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Transcription(Base):
    """
    STT 처리 요청 및 결과를 저장하는 테이블 모델
    """
    __tablename__ = 'transcriptions'

    # 고유 식별자
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 요청 정보
    client_id = Column(String, index=True)
    filename = Column(String)
    
    # 처리 상태 및 메타데이터
    status = Column(String, index=True, nullable=False, default='processing') # (processing, completed, failed)
    model = Column(String, nullable=False)
    language = Column(String(10))
    diarization = Column(Boolean, default=False)

    # 결과 및 에러
    result = Column(JSON) # STT 결과 JSON 저장 (JSONB 타입으로 성능 최적화)
    error_message = Column(String)
    
    # 타임스탬프
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<Transcription(request_id='{self.request_id}', status='{self.status}')>"