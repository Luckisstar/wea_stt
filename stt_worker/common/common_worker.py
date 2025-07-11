# stt_worker/common/base_worker.py

import os
from abc import ABC, abstractmethod
from kafka import KafkaConsumer, KafkaProducer
from minio import Minio
from pydub import AudioSegment
from pydub.silence import split_on_silence
import json
import logging
import uuid
import torch  # ⬅️ GPU 확인을 위해 torch 임포트

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseWorker(ABC):
    """
    STT Worker의 추상 기본 클래스.
    GPU 사용을 동적으로 지원하며, 공통 로직(Kafka, MinIO, 오디오 청크 분할)을 처리합니다.
    모델 로딩 및 STT 변환 로직은 서브클래스에서 구현하도록 강제합니다.
    """
    def __init__(self):
        # 환경 변수에서 설정값 로드
        self.kafka_bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        self.kafka_consumer_group_id = f'stt_worker_group_{os.getenv("STT_MODEL_NAME")}'
        self.kafka_target_topic = os.getenv("KAFKA_TARGET_TOPIC")
        self.kafka_results_topic = os.getenv("KAFKA_STT_RESULTS_TOPIC")

        self.minio_host = os.getenv("MINIO_HOST")
        self.minio_port = os.getenv("MINIO_PORT")
        self.minio_access_key = os.getenv("MINIO_ROOT_USER")
        self.minio_secret_key = os.getenv("MINIO_ROOT_PASSWORD")
        self.minio_audio_bucket = os.getenv("MINIO_AUDIO_BUCKET_NAME")

        # ⬅️ 장치(DEVICE) 설정: 환경변수 우선, 없으면 GPU 자동 감지
        device_env = os.getenv("DEVICE", "auto").lower()
        if device_env == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device_env
        
        logger.info(f"Using device: {self.device.upper()}")

        # 모델 로딩
        self.model = self._load_model()

        # Kafka, MinIO 클라이언트 초기화
        self.consumer = self._init_consumer()
        self.producer = self._init_producer()
        self.minio_client = self._init_minio_client()
        logger.info(f"Worker for model '{os.getenv('STT_MODEL_NAME')}' initialized.")

    @abstractmethod
    def _load_model(self):
        """
        STT 모델을 로드합니다. 서브클래스에서 반드시 구현해야 합니다.
        """
        pass

    @abstractmethod
    def _transcribe(self, audio_path: str) -> dict:
        """
        주어진 오디오 파일 경로를 사용하여 STT를 수행합니다.
        서브클래스에서 반드시 구현해야 합니다.
        반환값은 STT 결과 딕셔너리여야 합니다. (예: {"text": "..."})
        """
        pass

    def _init_consumer(self):
        return KafkaConsumer(
            self.kafka_target_topic,
            bootstrap_servers=self.kafka_bootstrap_servers.split(','),
            group_id=self.kafka_consumer_group_id,
            auto_offset_reset='earliest',
            value_deserializer=lambda v: json.loads(v.decode('utf-8'))
        )

    def _init_producer(self):
        return KafkaProducer(
            bootstrap_servers=self.kafka_bootstrap_servers.split(','),
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def _init_minio_client(self):
        return Minio(
            f"{self.minio_host}:{self.minio_port}",
            access_key=self.minio_access_key,
            secret_key=self.minio_secret_key,
            secure=False
        )
        
    def _download_from_minio(self, object_name: str) -> str:
        """MinIO에서 파일을 다운로드하고 로컬 경로를 반환합니다."""
        local_path = f"/tmp/{object_name}"
        self.minio_client.fget_object(self.minio_audio_bucket, object_name, local_path)
        logger.info(f"Downloaded {object_name} from MinIO.")
        return local_path
    
    def _split_audio_into_chunks(self, audio_path: str) -> list:
        """pydub을 사용하여 오디오를 조용한 구간 기준으로 청크로 나눕니다."""
        logger.info(f"Splitting audio file: {audio_path}")
        try:
            audio = AudioSegment.from_file(audio_path)
            chunks = split_on_silence(
                audio,
                min_silence_len=1000,  # 최소 1초의 침묵을 기준으로 분할
                silence_thresh=-40,    # -40 dBFS를 침묵으로 간주
                keep_silence=500       # 분할된 청크의 앞뒤에 0.5초의 침묵 유지
            )

            chunk_paths = []
            if not os.path.exists("/tmp/chunks"):
                os.makedirs("/tmp/chunks")

            for i, chunk in enumerate(chunks):
                chunk_id = str(uuid.uuid4())
                chunk_path = f"/tmp/chunks/chunk_{chunk_id}_{i}.wav"
                chunk.export(chunk_path, format="wav")
                chunk_paths.append(chunk_path)
            
            logger.info(f"Split into {len(chunk_paths)} chunks.")
            return chunk_paths
        except Exception as e:
            logger.error(f"Failed to split audio file {audio_path}: {e}")
            return []

    def run(self):
        """Kafka 메시지를 계속 수신하고 처리합니다."""
        logger.info(f"Listening for messages on topic: {self.kafka_target_topic}")
        for message in self.consumer:
            data = message.value
            transcription_id = data.get("transcription_id")
            audio_file_name = data.get("audio_file_name")

            if not transcription_id or not audio_file_name:
                logger.error(f"Invalid message received: {data}")
                continue

            logger.info(f"Processing transcription ID: {transcription_id}")

            local_audio_path = None
            chunk_files = []
            full_text = ""
            status = "completed"
            
            try:
                # 1. MinIO에서 오디오 파일 다운로드
                local_audio_path = self._download_from_minio(audio_file_name)

                # 2. 오디오 파일을 청크로 분할
                chunk_files = self._split_audio_into_chunks(local_audio_path)
                
                # 3. 각 청크를 순회하며 STT 변환 수행
                all_results = []
                for chunk_path in chunk_files:
                    stt_result = self._transcribe(chunk_path)
                    all_results.append(stt_result.get("text", ""))
                
                # 4. 전체 텍스트 조합
                full_text = " ".join(all_results)
                
            except Exception as e:
                logger.error(f"Error processing transcription ID {transcription_id}: {e}")
                result_message = {
                    "transcription_id": transcription_id,
                    "status": "failed",
                    "text": str(e)
                }
            
            finally:
                # 5. 임시 파일들(원본, 청크) 삭제
                if local_audio_path and os.path.exists(local_audio_path):
                    os.remove(local_audio_path)
                for chunk_file in chunk_files:
                    if os.path.exists(chunk_file):
                        os.remove(chunk_file)

            # 6. 최종 결과 메시지 구성
            result_message = {
                "transcription_id": transcription_id,
                "status": status,
                "text": full_text
            }

            # 7. Kafka로 결과 전송
            self.producer.send(self.kafka_results_topic, result_message)
            self.producer.flush()
            logger.info(f"Sent final result for transcription ID {transcription_id} to Kafka.")
