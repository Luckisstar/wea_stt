import os
import json
import logging
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker
from kafka import KafkaConsumer, KafkaProducer
from db import Transcription

# --- 로깅 설정 ---
# 다른 라이브러리 로그와 섞이지 않도록 핸들러에 이름을 부여합니다.
logger = logging.getLogger("result_handler")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# --- 2. 설정 및 초기화 ---
KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092')
POSTGRES_DSN = os.getenv('DATABASE_URL')
if not POSTGRES_DSN:
    logger.critical("DATABASE_URL 환경 변수가 설정되지 않았습니다.")
    exit(1)

# DB 엔진 및 세션
engine = create_engine(POSTGRES_DSN)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Kafka Consumer & Producer
try:
    consumer = KafkaConsumer(
        'stt_results', 'stt_errors',
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id='result_handler_group',
        auto_offset_reset='latest'
    )
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
except Exception as e:
    logger.critical(f"Kafka 연결에 실패했습니다: {e}")
    exit(1)

# --- 3. 메인 처리 루프 ---
logger.info("Result Handler가 시작되었습니다. 메시지를 기다립니다...")
for message in consumer:
    db: Session = SessionLocal()
    data = message.value
    request_id = data.get('request_id')

    if not request_id:
        logger.warning(f"request_id가 없는 메시지를 건너뜁니다: {data}")
        continue

    logger.info(f"'{message.topic}' 토픽에서 request_id: {request_id} 처리 시작")
    
    try:
        if message.topic == 'stt_results':
            # 성공 메시지 처리
            result_data = data.get('result', {})
            # 더 안전하게 text 필드에 접근
            result_text = result_data.get('text', '')
            
            stmt = (
                update(Transcription)
                .where(Transcription.request_id == request_id)
                .values(status='completed', result=result_data)
                .returning(Transcription.client_id) # 업데이트된 레코드의 client_id를 반환받음
            )
            notification_payload = {'status': 'completed', 'request_id': request_id, 'text': result_text}

        else:  # stt_errors 토픽
            # 실패 메시지 처리
            error_msg = data.get('error', 'Unknown error')
            stmt = (
                update(Transcription)
                .where(Transcription.request_id == request_id)
                .values(status='failed', error_message=error_msg)
                .returning(Transcription.client_id)
            )
            notification_payload = {'status': 'failed', 'request_id': request_id, 'error': error_msg}

        # DB 업데이트 실행 및 client_id 가져오기
        result_proxy = db.execute(stmt)
        updated_row = result_proxy.fetchone()
        db.commit()

        if not updated_row:
            logger.warning(f"request_id '{request_id}'에 해당하는 레코드가 DB에 없어 업데이트하지 못했습니다.")
            continue

        # Kafka를 통해 클라이언트에게 알림 전송
        client_id = updated_row[0] # returning으로 받아온 client_id
        if client_id:
            full_notification = {'client_id': client_id, 'payload': notification_payload}
            producer.send('notifications', full_notification)
            producer.flush()
            logger.info(f"클라이언트 '{client_id}'에게 알림을 전송했습니다. (request_id: {request_id})")
        else:
            logger.warning(f"client_id가 없어 알림을 보내지 못했습니다. (request_id: {request_id})")

    except Exception as e:
        logger.error(f"결과 처리 중 예상치 못한 에러 발생 (request_id: {request_id}): {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()