import os
import json
import logging
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from kafka import KafkaConsumer, KafkaProducer
from db import Transcription

# --- 로깅 설정 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 설정 ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS')
POSTGRES_DSN = os.getenv('DATABASE_URL')

# --- DB 설정 ---
engine = create_engine(POSTGRES_DSN)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Kafka Consumer & Producer ---
consumer = KafkaConsumer(
    'stt_results', 'stt_errors',
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_deserializer=lambda m: json.loads(m.decode('utf-8')),
    group_id='result_handler_group'
)
producer = KafkaProducer(
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# --- 메인 루프 ---
logging.info("Result Handler is running...")
for message in consumer:
    db = SessionLocal()
    data = message.value
    request_id = data.get('request_id')
    
    try:
        if message.topic == 'stt_results':
            logging.info(f"Processing successful result for request_id: {request_id}")
            result_text = data['result']['text']
            stmt = (
                update(Transcription)
                .where(Transcription.request_id == request_id)
                .values(status='completed', result=data['result'])
            )
            notification_payload = {'status': 'completed', 'request_id': request_id, 'text': result_text}
        else: # stt_errors 토픽
            logging.error(f"Processing failed result for request_id: {request_id}")
            stmt = (
                update(Transcription)
                .where(Transcription.request_id == request_id)
                .values(status='failed', error_message=data.get('error'))
            )
            notification_payload = {'status': 'failed', 'request_id': request_id, 'error': data.get('error')}

        db.execute(stmt)
        db.commit()

        # Kafka를 통해 클라이언트에게 알림
        task = data.get('original_task', {})
        client_id = task.get('client_id')
        if client_id:
            producer.send('notifications', {'client_id': client_id, 'payload': notification_payload})
            producer.flush()
            logging.info(f"Sent notification for client_id: {client_id}")

    except Exception as e:
        logging.error(f"Error processing result for request_id {request_id}: {e}")
        db.rollback()
    finally:
        db.close()