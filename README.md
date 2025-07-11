# 분산 아키텍처 기반 STT 처리 시스템

이 프로젝트는 대용량 음성 파일을 효율적으로 처리하기 위한 분산 STT(Speech-to-Text) 시스템입니다. Microservice Architecture를 기반으로 설계되었으며, Kafka를 이용한 비동기 메시지 큐를 통해 각 컴포넌트가 독립적으로 확장 및 운영될 수 있도록 구성되었습니다.

## 주요 기능

- **비동기 STT 처리**: 대용량 음성 파일도 안정적으로 처리할 수 있는 비동기 처리 방식
- **다중 STT 모델 지원**: `Whisper`와 화자 분리를 지원하는 `WhisperX` 모델 선택 가능
- **실시간 처리 현황 알림**: WebSocket을 통해 클라이언트에게 STT 처리 상태를 실시간으로 전송
- **사용자 인증**: JWT(JSON Web Token) 기반의 안전한 인증 시스템
- **모니터링**: Prometheus와 Grafana를 이용한 시스템 상태 및 성능 모니터링 대시보드
- **확장성**: 각 서비스가 Docker 컨테이너로 구성되어 있어 수평 확장이 용이

## 시스템 아키텍처

```
+-----------------+      +-----------------+      +----------------------+
|   Client (UI)   |----->|  Nginx (Proxy)  |----->|  API Gateway (FastAPI) |
+-----------------+      +-----------------+      +----------------------+
       ^                                                     |
       | (WebSocket)                                         | (Kafka Message)
       |                                                     v
+-----------------+      +-----------------+      +----------------------+
| Kafka / Zookeeper|<-----| STT Workers     |<-----| MinIO (Object Storage) |
+-----------------+      +-----------------+      +----------------------+
       ^                                                     ^
       | (DB Update)                                         | (Audio File)
       |                                                     |
+-----------------+      +-----------------+      +----------------------+
| Result Handler  |----->| PostgreSQL (DB) |<-----| API Gateway (FastAPI) |
+-----------------+      +-----------------+      +----------------------+
```

1.  **Nginx**: 모든 외부 요청을 수신하는 리버스 프록시 서버. `/api` 경로는 `API Gateway`로, 그 외 경로는 `Admin UI`로 라우팅합니다.
2.  **API Gateway**: 사용자의 STT 요청 접수, 인증, 파일 업로드 처리 및 WebSocket을 통한 실시간 알림을 담당합니다.
3.  **MinIO**: 사용자가 업로드한 음성 파일을 저장하는 오브젝트 스토리지입니다.
4.  **Kafka**: 서비스 간 비동기 통신을 위한 메시지 큐. STT 처리 요청, 결과, 에러 등을 전달합니다.
5.  **STT Workers**: Kafka로부터 STT 처리 요청을 받아 실제 음성 인식을 수행합니다. (`whisper`, `whisperx` 두 종류)
6.  **Result Handler**: STT 처리 결과를 Kafka로부터 받아 PostgreSQL 데이터베이스에 저장하고, `API Gateway`에 알림을 보냅니다.
7.  **PostgreSQL**: 사용자 정보, STT 처리 결과 등 데이터를 저장하는 데이터베이스입니다.
8.  **Monitoring Stack**: Prometheus가 각 서비스의 메트릭을 수집하고, Grafana가 이를 시각화하여 보여줍니다.

## 시작하기

### 사전 요구 사항

- [Docker](https://www.docker.com/get-started)
- [Docker Compose](https://docs.docker.com/compose/install/)
- Git

### 설치 및 설정

1.  **프로젝트 클론**

    ```bash
    git clone <repository_url>
    cd <project_directory>
    ```

2.  **환경 변수 설정**

    `.env.example` 파일을 복사하여 `.env` 파일을 생성하고, 각 환경 변수에 맞는 값을 입력합니다.

    ```bash
    cp .env.example .env
    ```

    - `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`: PostgreSQL 데이터베이스 설정
    - `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`: MinIO 접속 정보
    - `JWT_SECRET_KEY`: JWT 토큰 생성을 위한 시크릿 키
    - `HUGGINGFACE_TOKEN` (선택 사항): `whisperx`의 화자 분리 기능 사용 시 필요한 Hugging Face 인증 토큰

### 실행 방법

- **개발 환경**:

  코드 변경 시 자동으로 재시작되어 개발에 용이합니다.

  ```bash
  docker-compose -f docker-compose.dev.yml up --build
  ```

- **프로덕션 환경**:

  백그라운드에서 안정적으로 서비스를 운영합니다.

  ```bash
  docker-compose -f docker-compose.prod.yml up -d --build
  ```

### 서비스 접속 정보

- **Admin UI & API Gateway**: `http://localhost:80`
- **MinIO Console**: `http://localhost:9001`
- **Grafana Dashboard**: `http://localhost:3000` (기본 계정: admin / admin)
- **Prometheus**: `http://localhost:9090`

## 프로젝트 구조

```
/
├── admin_ui/           # React 기반 관리자 페이지 UI
├── api_gateway/        # FastAPI 기반 API 게이트웨이
├── monitoring/         # Prometheus, Grafana 설정
├── nginx/              # Nginx 리버스 프록시 설정
├── result_handler/     # STT 결과 처리 및 DB 저장 서비스
├── stt_worker_base/    # STT 워커들의 공통 로직
├── stt_worker_whisper/ # Whisper 모델 기반 STT 워커
├── stt_worker_whisperx/# WhisperX 모델 기반 STT 워커 (화자 분리)
├── test/               # 테스트 스크립트
├── .env.example        # 환경 변수 예시 파일
├── docker-compose.dev.yml # 개발용 Docker Compose
└── docker-compose.prod.yml# 프로덕션용 Docker Compose
```
