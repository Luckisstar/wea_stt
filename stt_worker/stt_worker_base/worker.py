import os
import torch
import whisper
import tempfile
import logging
import time
import subprocess
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from stt_worker.common.base_worker import create_kafka_consumer, create_kafka_producer, create_minio_client

# --- ⚙️ 설정 ---
AUDIO_BUCKET_NAME = "audio"
MAX_RETRY = 3
PROMETHEUS_PORT = 8001
CHUNK_LENGTH_S = 30 # 30초 청크

KAFKA_TARGET_TOPIC = os.getenv("KAFKA_TARGET_TOPIC")
MODEL_NAME = os.getenv("MODEL_NAME", "base")

# --- 🚀 초기화 ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {DEVICE}")

if not KAFKA_TARGET_TOPIC:
    logging.critical("KAFKA_TARGET_TOPIC 환경 변수가 설정되지 않았습니다.")
    exit(1)

# consumer = create_kafka_consumer('stt_whisper_base_worker_group', ['audio_requests'])
consumer = create_kafka_consumer(KAFKA_TARGET_TOPIC, "stt_worker_group_" + MODEL_NAME)
producer = create_kafka_producer()
minio_client = create_minio_client()

# --- Prometheus 메트릭 정의 ---
REQUESTS_TOTAL = Counter('stt_requests_total', 'Total number of STT requests', ['model'])
SUCCESSFUL_REQUESTS_TOTAL = Counter('stt_successful_requests_total', 'Total number of successful STT requests', ['model'])
FAILED_REQUESTS_TOTAL = Counter('stt_failed_requests_total', 'Total number of failed STT requests', ['model'])
PROCESSING_TIME = Histogram('stt_processing_time_seconds', 'Time spent processing STT requests', ['model'])

model_cache = {}

def get_model(model_name: str):
    if model_name not in model_cache:
        logging.info(f"Loading whisper model '{model_name}' into memory...")
        model_cache[model_name] = whisper.load_model(model_name, device=DEVICE)
        logging.info(f"Model '{model_name}' loaded.")
    return model_cache[model_name]

def get_audio_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

# --- 🎧 메인 처리 루프 ---
logging.info(f"'{KAFKA_TARGET_TOPIC}' 토픽을 구독하며, '{MODEL_NAME}' 모델로 대기합니다.")

for message in consumer:
    task = message.value
    request_id = task.get("request_id")
    
    try:
        # MinIO에서 파일 다운로드 (기존 로직과 동일)
        object_name = task["audio_object_name"]
        response = minio_client.get_object(AUDIO_BUCKET_NAME, object_name)
        
        with tempfile.NamedTemporaryFile(delete=True) as tmp_file:
            tmp_file.write(response.read())
            tmp_file.flush()
            
            # ✨ 환경 변수로 받은 모델 이름으로 모델 로드
            model = get_model(MODEL_NAME)
            transcribe_options = {"language": task.get("language")}
            duration = get_audio_duration(tmp_file.name)
            full_transcription = ""
            
            # STT 처리 (기존 로직과 동일)
            for i in range(0, int(duration), CHUNK_LENGTH_S):
                with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as chunk_file:
                    cmd = [
                        "ffmpeg",
                        "-ss", str(i),
                        "-i", tmp_file.name,
                        "-t", str(CHUNK_LENGTH_S),
                        "-c", "copy",
                        chunk_file.name
                    ]
                    subprocess.run(cmd, check=True, capture_output=True)
                    
                    chunk_result = model.transcribe(chunk_file.name, **transcribe_options)
                    full_transcription += chunk_result["text"]
        
        response.close()
        response.release_conn()

        # 성공 결과 전송 (기존 로직과 동일)
        producer.send('stt_results', {'request_id': request_id, 'result': full_transcription, 'original_task': task})

    except Exception as e:
        FAILED_REQUESTS_TOTAL.labels(model=MODEL_NAME).inc()
        logging.error(f"❌ Error processing task {request_id}: {e}")
        
        current_retry = task.get('retry', 0)
        if current_retry < MAX_RETRY:
            task['retry'] = current_retry + 1
            logging.info(f"Retrying task {request_id} (Attempt: {task['retry']})")
            producer.send('audio_requests', task)
        else:
            logging.error(f"🚫 Task {request_id} failed after {MAX_RETRY} retries.")
            producer.send('stt_errors', {'request_id': request_id, 'error': str(e), 'original_task': task})
    finally:
        producer.flush()
