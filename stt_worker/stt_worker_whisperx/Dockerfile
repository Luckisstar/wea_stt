FROM nvidia/cuda:11.8.0-cudnn8-runtime-ubuntu22.04

# --- 시스템 의존성 설치 ---
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    python3-pip \
    git \
    && rm -rf /var/lib/apt/lists/*

# --- Python 의존성 설치 ---
# Copy the entire stt_worker directory into the container
COPY ./stt_worker ./stt_worker

# Install torch separately with its specific index URL
RUN pip3 install --no-cache-dir torch==2.1.0+cu118 torchvision==0.16.0+cu118 torchaudio==2.1.0+cu118 --index-url https://download.pytorch.org/whl/cu118

# Copy requirements.txt from the worker directory and install remaining dependencies
COPY ./stt_worker/stt_worker_whisperx/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# --- Hugging Face Token 설정 (화자분리 모델 다운로드용) ---
# docker-compose.yml의 environment나 .env 파일에서 주입
# ENV HUGGINGFACE_TOKEN="YOUR_HF_TOKEN" 

CMD ["python3", "./stt_worker/stt_worker_whisperx/worker.py"]
