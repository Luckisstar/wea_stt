# 베이스 이미지 (CPU 버전 기준)
FROM python:3.10-slim

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- 1. 작업 디렉토리 설정 ---
# 프로젝트의 루트를 작업 디렉토리로 설정합니다.
WORKDIR /app

# --- 2. Python 라이브러리 설치 ---
# requirements.txt 파일을 먼저 복사하여 Docker의 레이어 캐시를 활용합니다.
COPY ./stt_worker/stt_worker_base/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# --- 3. 애플리케이션 소스 코드 복사 ---
# 전체 프로젝트를 컨테이너 안으로 복사합니다.
COPY . .

# --- 4. PYTHONPATH 환경 변수 설정 (핵심 수정) ---
# 파이썬이 모듈을 찾을 수 있도록 프로젝트 루트('/app')를 경로에 추가합니다.
ENV PYTHONPATH "${PYTHONPATH}:/app"

# --- 5. 컨테이너 실행 명령어 ---
# 실행할 파이썬 스크립트 경로를 정확히 지정합니다.
CMD ["python3", "./stt_worker/stt_worker_base/worker.py"]