import asyncio
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaConsumer
from dotenv import load_dotenv
# # from prometheus_fastapi_instrumentator import Instrumentator

from . import models
from .db_session import engine
from .websocket_manager import manager
from .routers import stt, auth, admin

load_dotenv()

if os.getenv("TESTING") != "True":
    models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Distributed STT System API")

# Prometheus Instrumentator 추가
# Instrumentator().instrument(app).expose(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용하도록 변경해야 합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stt.router)
app.include_router(auth.router)
app.include_router(admin.router)

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(client_id)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(consume_notifications())

async def consume_notifications():
    consumer = KafkaConsumer(
        'notifications',
        bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS"),
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="api_gateway_notification_group"
    )
    for message in consumer:
        client_id = message.value.get("client_id")
        payload = message.value.get("payload")
        if client_id and payload:
            await manager.send_personal_message(payload, client_id)

@app.get("/health", tags=["System"])
def health_check():
    return {"status": "ok"}
