# 베이스 이미지 (CPU 버전 기준)
FROM python:3.10-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y ffmpeg

# --- 1. 작업 디렉토리 설정 ---
# 프로젝트의 루트를 작업 디렉토리로 설정합니다.
WORKDIR /app

COPY ./stt_worker_base/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 2. Python 라이브러리 설치 ---
COPY ./common /app/common
COPY ./stt_worker_base /app/stt_worker_base

# --- 4. PYTHONPATH 환경 변수 설정 (핵심 수정) ---
# 파이썬이 모듈을 찾을 수 있도록 프로젝트 루트('/app')와 stt_worker 디렉토리를 경로에 추가합니다.
ENV PYTHONPATH "${PYTHONPATH}:/app:/app/stt_worker"

# --- 5. 컨테이너 실행 명령어 ---
# 실행할 파이썬 스크립트 경로를 정확히 지정합니다.
CMD ["python3", "/app/stt_worker_base/base_worker.py"]