import os
import whisper
import logging
from common.common_worker import BaseWorker
import torch # ⬅️ torch 임포트 추가

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model_cache = {}

class WhisperBaseWorker(BaseWorker):
    """
    Whisper 'base' 모델을 사용하여 STT를 수행하는 워커.
    GPU 사용 및 모델 캐싱을 지원합니다.
    """
    model_cache = {}

    def _load_model(self):
        """Whisper 'base' 모델을 로드합니다."""
        model_name = os.getenv("STT_MODEL_NAME", "base")
        # ⬅️ 모델이 저장된 로컬 폴더 경로를 환경 변수에서 가져옴
        model_root_path = os.getenv("MODEL_PATH", "/app/models") 

        # 캐시 키를 모델 이름과 장치 조합으로 만듦 (예: "base-cuda")
        cache_key = f"{model_name}-{self.device}"
        
        if cache_key in model_cache:
            logger.info(f"Loading Whisper model '{model_name}' from cache for device '{self.device}'.")
            return model_cache[cache_key]
        
        logger.info(f"Loading Whisper model '{model_name}' from local path '{model_root_path}' for device '{self.device}'.")
        
        # ⬅️ whisper.load_model에 download_root 파라미터로 로컬 경로 지정
        # 이 경로에 'model_name.pt' 파일이 있는지 확인합니다.
        model = whisper.load_model(model_name, device=self.device, download_root=model_root_path)
        
        model_cache[cache_key] = model
        logger.info(f"Model '{model_name}' has been cached for device '{self.device}'.")
        
        return model

    def _transcribe(self, audio_path: str) -> dict:
        """Whisper 모델을 사용하여 오디오 파일을 텍스트로 변환합니다."""
        logger.info(f"Transcribing audio file: {audio_path}")
        
        # ⬅️ GPU 사용 시, fp16 옵션을 활성화하여 성능 향상
        # torch.cuda.is_available()는 PyTorch가 CUDA 지원으로 컴파일되었는지와
        # 실제로 사용 가능한 NVIDIA GPU가 있는지를 모두 확인합니다.
        use_fp16 = self.device == "cuda" and torch.cuda.is_available()
        
        if use_fp16:
            logger.info("Transcription running with FP16 (GPU).")
        
        result = self.model.transcribe(audio_path, fp16=use_fp16)
        logger.info("Transcription completed.")
        return result

if __name__ == "__main__":
    worker = WhisperBaseWorker()
    worker.run()
