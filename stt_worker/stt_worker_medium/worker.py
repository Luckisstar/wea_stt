import os
import torch
import tempfile
import logging
import time
import subprocess
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from stt_worker.common.base_worker import create_kafka_consumer, create_kafka_producer, create_minio_client
from transformers import pipeline

# --- ⚙️ 설정 ---
AUDIO_BUCKET_NAME = "audio"
MAX_RETRY = 3
PROMETHEUS_PORT = 8003
CHUNK_LENGTH_S = 30 # 30초 청크

# --- 🚀 초기화 ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {DEVICE}")

consumer = create_kafka_consumer('stt_whisper_fast_worker_group', ['audio_requests'])
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
        model_cache[model_name] = pipeline(
            "automatic-speech-recognition",
            model=model_name,
            torch_dtype=torch.float16 if DEVICE == "cuda" else torch.float32,
            device=DEVICE,
        )
        logging.info(f"Model '{model_name}' loaded.")
    return model_cache[model_name]

def get_audio_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

# --- 🎧 메인 처리 루프 ---
if __name__ == '__main__':
    start_http_server(PROMETHEUS_PORT)
    logging.info(f"Prometheus server started on port {PROMETHEUS_PORT}")
    logging.info("Whisper Fast STT Worker is running and waiting for tasks...")
    for message in consumer:
        task = message.value
        
        # 이 워커는 'distil-whisper' 모델만 처리
        if task.get("model") != "distil-whisper" or task.get("diarization", False):
            continue

        request_id = task.get("request_id")
        model_name = task.get("model", "unknown")
        REQUESTS_TOTAL.labels(model=model_name).inc()
        logging.info(f"\nProcessing task: {request_id}")

        start_time = time.time()
        try:
            object_name = task["audio_object_name"]
            response = minio_client.get_object(AUDIO_BUCKET_NAME, object_name)
            
            with tempfile.NamedTemporaryFile(delete=True, suffix=".tmp") as original_audio_file:
                original_audio_file.write(response.read())
                original_audio_file.flush()

                duration = get_audio_duration(original_audio_file.name)
                full_transcription = ""
                
                model = get_model(model_name)
                
                for i in range(0, int(duration), CHUNK_LENGTH_S):
                    with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as chunk_file:
                        cmd = [
                            "ffmpeg",
                            "-ss", str(i),
                            "-i", original_audio_file.name,
                            "-t", str(CHUNK_LENGTH_S),
                            "-c", "copy",
                            chunk_file.name
                        ]
                        subprocess.run(cmd, check=True, capture_output=True)
                        
                        chunk_result = model(chunk_file.name, generate_kwargs={"language": task.get("language")})
                        full_transcription += chunk_result["text"]

            response.close()
            response.release_conn()

            processing_time = time.time() - start_time
            PROCESSING_TIME.labels(model=model_name).observe(processing_time)
            SUCCESSFUL_REQUESTS_TOTAL.labels(model=model_name).inc()
            logging.info(f"✅ Transcription successful for task: {request_id}")
            producer.send('stt_results', {'request_id': request_id, 'result': {"text": full_transcription}, 'original_task': task})

        except Exception as e:
            FAILED_REQUESTS_TOTAL.labels(model=model_name).inc()
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
