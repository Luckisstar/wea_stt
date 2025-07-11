import os
import uuid
import json
from fastapi import APIRouter, UploadFile, File, Form, Depends, status
from minio import Minio
from kafka import KafkaProducer
from sqlalchemy.orm import Session

from .. import auth, models
from ..db_session import get_db
from ..models import Transcription

router = APIRouter()

MINIO_URL = os.getenv('MINIO_URL', 'minio:9000')
MINIO_ACCESS_KEY = os.getenv('MINIO_ACCESS_KEY')
MINIO_SECRET_KEY = os.getenv('MINIO_SECRET_KEY')
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')

minio_client = Minio(
    MINIO_URL,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)

producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

@router.post("/v1/audio/transcriptions", status_code=status.HTTP_200_OK, tags=["STT"])
async def create_transcription(
    file: UploadFile = File(...),
    model: str = Form(...),
    language: str = Form(None),
    prompt: str = Form(None),
    response_format: str = Form("json"),
    temperature: float = Form(0),
    timestamp_granularities: list[str] = Form(["segment"]),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    client_id = current_user.username

    file_id = uuid.uuid4()
    file_extension = os.path.splitext(file.filename)[1]
    object_name = f"{client_id}/{file_id}{file_extension}"
    bucket_name = "audio"

    if not minio_client.bucket_exists(bucket_name):
        minio_client.make_bucket(bucket_name)

    minio_client.put_object(
        bucket_name=bucket_name,
        object_name=object_name,
        data=file.file,
        length=-1,
        part_size=10*1024*1024
    )

    new_transcription = Transcription(
        request_id=file_id,
        client_id=client_id,
        filename=file.filename,
        model=model,
        language=language,
        status="processing"
    )
    db.add(new_transcription)
    db.commit()
    
    message = {
        "request_id": str(file_id),
        "audio_object_name": object_name,
        "model": model,
        "language": language,
        "filename": file.filename,
        "client_id": client_id,
        "retry": 0,
        "diarization": "diarization" in timestamp_granularities
    }
    producer.send('audio_requests', message)
    producer.flush()

    return {"text": "Transcription in progress..."}
