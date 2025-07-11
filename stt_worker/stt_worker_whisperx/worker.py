import os
import torch
import whisperx
import tempfile
import logging
import time
import subprocess
from prometheus_client import start_http_server, Counter, Histogram
from stt_worker.common.base_worker import create_kafka_consumer, create_kafka_producer, create_minio_client

# --- ⚙️ 설정 ---
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_TOKEN')
AUDIO_BUCKET_NAME = "audio"
MAX_RETRY = 3
PROMETHEUS_PORT = 8005
CHUNK_LENGTH_S = 30 # 30초 청크

# --- 🚀 초기화 ---
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {DEVICE}")
BATCH_SIZE = 16
COMPUTE_TYPE = "float16" if torch.cuda.is_available() else "int8"

consumer = create_kafka_consumer('stt_whisperx_worker_group', ['audio_requests'])
producer = create_kafka_producer()
minio_client = create_minio_client()

# --- Prometheus 메트릭 정의 ---
REQUESTS_TOTAL = Counter('stt_requests_total', 'Total number of STT requests', ['model'])
SUCCESSFUL_REQUESTS_TOTAL = Counter('stt_successful_requests_total', 'Total number of successful STT requests', ['model'])
FAILED_REQUESTS_TOTAL = Counter('stt_failed_requests_total', 'Total number of failed STT requests', ['model'])
PROCESSING_TIME = Histogram('stt_processing_time_seconds', 'Time spent processing STT requests', ['model'])

model_cache = {}
diarize_model_cache = None

def get_model(model_name, language):
    cache_key = f"{model_name}_{language}"
    if cache_key in model_cache:
        return model_cache[cache_key]

    logging.info(f"Loading whisperX model '{model_name}' for language '{language}'...")
    model = whisperx.load_model(model_name, DEVICE, compute_type=COMPUTE_TYPE, language=language)
    model_cache[cache_key] = model
    logging.info(f"Model '{model_name}' loaded.")
    return model

def get_diarize_model():
    global diarize_model_cache
    if diarize_model_cache is None:
        logging.info("Loading diarization pipeline...")
        diarize_model_cache = whisperx.DiarizationPipeline(use_auth_token=HUGGINGFACE_TOKEN, device=DEVICE)
        logging.info("Diarization pipeline loaded.")
    return diarize_model_cache

def get_audio_duration(file_path):
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())

# --- 🎧 메인 처리 루프 ---
if __name__ == '__main__':
    start_http_server(PROMETHEUS_PORT)
    logging.info(f"Prometheus server started on port {PROMETHEUS_PORT}")
    logging.info("WhisperX STT Worker is running and waiting for tasks...")
    for message in consumer:
        task = message.value

        if not task.get("diarization", False):
            continue

        request_id = task.get("request_id")
        model_name = task.get("model", "unknown")
        REQUESTS_TOTAL.labels(model=model_name).inc()
        logging.info(f"
Processing task: {request_id}")

        start_time = time.time()
        try:
            object_name = task["audio_object_name"]
            response = minio_client.get_object(AUDIO_BUCKET_NAME, object_name)

            with tempfile.NamedTemporaryFile(delete=True, suffix=".tmp") as original_audio_file:
                original_audio_file.write(response.read())
                original_audio_file.flush()

                duration = get_audio_duration(original_audio_file.name)
                full_segments = []

                model = get_model("large-v2", task.get("language"))

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
                        
                        audio = whisperx.load_audio(chunk_file.name)
                        chunk_result = model.transcribe(audio, batch_size=BATCH_SIZE)
                        full_segments.extend(chunk_result["segments"])

                model_a, metadata = whisperx.load_align_model(language_code=task.get("language"), device=DEVICE)
                result_aligned = whisperx.align(full_segments, model_a, metadata, audio, DEVICE, return_char_alignments=False)

                diarize_model = get_diarize_model()
                diarize_segments = diarize_model(audio)

                final_result = whisperx.assign_word_speakers(diarize_segments, result_aligned)

            response.close()
            response.release_conn()

            processing_time = time.time() - start_time
            PROCESSING_TIME.labels(model=model_name).observe(processing_time)
            SUCCESSFUL_REQUESTS_TOTAL.labels(model=model_name).inc()
            logging.info(f"✅ Transcription successful for task: {request_id}")
            producer.send('stt_results', {'request_id': request_id, 'result': final_result, 'original_task': task})

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
