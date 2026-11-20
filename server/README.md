# Movie Maker - Server (Backend & Worker)

Movie Maker의 백엔드는 **FastAPI** 기반의 REST/SSE 웹 API 서버와 **Celery 5 (Redis)** 기반의 비동기 분산 작업 워커로 구성되어 있습니다.

---

## 1. 코드 구조 (Directory Structure)

```text
server/
├── requirements.txt       # 백엔드 핵심 Python 의존성 목록
├── .env.example           # 환경 변수 템플릿
├── app/                   # FastAPI 웹 애플리케이션 계층
│   ├── main.py            # FastAPI 앱 인스턴스, 예외 처리기, 정적 클라이언트 마운트, 헬스체크
│   ├── static/            # 클라이언트 빌드 산출물(client/dist)이 복사되어 서빙되는 정적 디렉터리
│   ├── config.py          # Pydantic Settings 기반 중앙 환경 설정 및 제한 상수
│   ├── db.py              # SQLAlchemy 2.0 엔진 및 SessionLocal 세션 제너레이터
│   ├── models.py          # ORM 데이터 모델 (User, Session, Job, Scene, Shot, SourceImage)
│   ├── schemas.py         # Pydantic 요청/응답 직렬화 및 유효성 검사 스키마
│   ├── storage.py         # 디스크 스토리지 관리, 매직 바이트 이미지 검증, 경로 생성
│   ├── auth.py            # Argon2id 비밀번호 해싱, SHA-256 토큰, CSRF 보호
│   └── api/
│       ├── auth.py        # 인증 라우터 (/api/auth/register, /login, /logout, /me)
│       └── jobs.py        # 작업 및 엔진 라우터 (/api/jobs, /events, /video, /providers)
├── worker/                # Celery 비동기 작업 및 파이프라인 처리 계층
│   ├── celery_app.py      # Celery 애플리케이션 설정 (concurrency=1, 타임아웃, Beat 스케줄러)
│   ├── tasks.py           # run_job 비동기 태스크, run_job_sync 실행기, expire_old_jobs
│   ├── pipeline/          # 비디오 생성 단계별 파이프라인 모듈
│   │   ├── ffmpeg.py      # 시스템 및 내장 FFmpeg 바이너리 탐색 및 실행 래퍼
│   │   ├── frames.py      # FFmpeg 기반 샷의 마지막 프레임 이미지 추출 (프레임 체이닝용)
│   │   ├── split.py       # 문단 분할 및 Anthropic Claude Haiku LLM 분할기
│   │   ├── mapping.py     # 사진 전용 및 결합 모드 씬 매핑, 미사용 사진 카운트
│   │   ├── progress.py    # 0~100% 범위 보장 및 단조 증가 DB 진행률 업데이트
│   │   └── join.py        # FFmpeg Concat 비디오 결합기 (스트림 복사 우선, 재인코딩 폴백)
│   └── providers/         # 비디오 생성 엔진 어댑터
│       ├── base.py        # VideoProvider 프로토콜, ShotRequest/ShotResult 데이터클래스
│       ├── registry.py    # 중앙 프로바이더 레지스트리 (FR-016: 엔진명 누출 방지)
│       ├── mock.py        # FFmpeg 기반 고속 Mock 생성기 (결함 주입 지원)
│       ├── ltx.py         # 로컬 ComfyUI LTX-2.3 API 클라이언트 어댑터
│       └── gemini.py      # Google Gemini Cloud API 클라이언트 어댑터
└── workflows/             # ComfyUI API 형식 워크플로우 템플릿
    ├── ltx_t2v.json       # LTX-2.3 Text-to-Video 워크플로우
    └── ltx_i2v.json       # LTX-2.3 Image-to-Video 워크플로우
```

---

## 2. 주요 아키텍처 및 원칙

1. **상태 관리 및 데이터베이스**:
   - MySQL 9.3 (프로덕션/Docker 기본값, PyMySQL 드라이버) 또는 SQLite(로컬 경량 개발) 기반 SQLAlchemy 2.0 ORM 사용.
   - 세션 토큰은 SHA-256 해시값으로 DB에 저장되며, 브라우저에는 HttpOnly 쿠키로 전달됩니다.
   - 모든 상태 변경 요청(POST, DELETE)은 `X-CSRF-Token` 검증을 거칩니다.
2. **비동기 큐잉 및 단일 워커 (FR-026)**:
   - GPU VRAM 보호를 위해 Celery `concurrency=1`로 설정되어 FIFO 순서로 1개씩 안전하게 처리됩니다.
3. **견고한 파이프라인 (Fault-Tolerance)**:
   - 각 샷 생성 실패 시 1회 자동 재시도(`attempts=2`) 후 실패 처리.
   - LLM 시나리오 분석 실패 시 규칙 기반 문단 분할로 무중단 폴백.
4. **엔진 독립성 (FR-016)**:
   - `server/worker/providers/registry.py`를 통해 모든 비디오 엔진이 관리되며, 설정(`VIDEO_PROVIDER`) 변경만으로 엔진 스왑이 가능합니다.
5. **정적 클라이언트 서빙 (Static File Serving)**:
   - 클라이언트에서 `npm run build`를 실행하면 `client/dist/` 산출물이 `server/app/static/` 디렉터리로 자동 복사됩니다.
   - `server/app/main.py`는 `server/app/static/`이 존재하고 비어있지 않으면 최우선으로 루트(`/`)에 마운트하여 Vite 개발 서버 없이도 통합 웹 애플리케이션을 단독 서빙합니다.
6. **데이터 보존 정책 (FR-034)**:
   - Celery Beat에 등록된 `expire_old_jobs` 태스크가 주기적으로 실행되어 생성 후 2일이 지난 작업의 미디어를 삭제하고 상태를 `expired`로 전환합니다.

---

## 3. 실행 방법 (How to Run)

### 사전 요구사항

- **Python**: 3.11.x
- **FFmpeg**: 시스템 PATH에 등록되어 있거나 `imageio-ffmpeg` 패키지 설치
- **Redis**: 7.x (로컬 실행 또는 Docker)

### 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/Scripts/activate      # Linux / macOS
# Windows: .venv\Scripts\activate

# 의존성 설치
pip install -r server/requirements.txt

# 환경변수 파일 준비
cp server/.env.example server/.env
```

`server/.env` 기본 설정 예시:
```text
VIDEO_PROVIDER=mock
SESSION_SECRET=a-secure-random-secret-key-at-least-32-characters
ANTHROPIC_API_KEY=               # 비워둘 경우 기본 문단 분할 사용
GEMINI_API_KEY=                  # 비워둘 경우 Gemini 클라우드 엔진 비활성화
LTX_COMFYUI_URL=http://127.0.0.1:8188
REDIS_URL=redis://localhost:6379/0
DATABASE_URL=mysql+pymysql://movie_user:movie_password@localhost:3306/movie_agent?charset=utf8mb4
# 로컬 개발 시 SQLite 대체 사용 예시: sqlite:///./movie_agent.db
STORAGE_DIR=./storage
```

---

### 프로세스 실행

루트 디렉터리에서 각각 별도의 터미널을 열고 실행합니다:

#### 1. MySQL 및 Redis 브로커 시작
```bash
docker compose up -d mysql redis
```

#### 2. FastAPI API 서버 실행 (포트 8000)
```bash
fastapi dev --port 8000
# 프로덕션 실행 시: fastapi run server/app/main.py --port 8000
```
- 헬스체크 확인: `curl http://127.0.0.1:8000/api/health`
- Swagger 문서 확인: `http://127.0.0.1:8000/docs`

#### 3. Celery 백그라운드 워커 실행
```bash
# Windows 환경 (반드시 --pool=solo 필요):
celery -A server.worker.celery_app worker --pool=solo --concurrency=1 -l info

# Linux / macOS 환경:
celery -A server.worker.celery_app worker --concurrency=1 -l info
```

#### 4. Celery Beat 보존 스케줄러 실행 (선택 사항)
```bash
celery -A server.worker.celery_app beat -l info
```

---

## 4. 테스트 및 품질 검사

```bash
# 코드 스타일 및 린트 검사
ruff check .
ruff format --check .

# 정적 타입 검사
mypy server tests

# 전체 자동화 테스트 실행 (단위, 계약, 통합)
pytest tests/unit tests/contract tests/integration -v
```

