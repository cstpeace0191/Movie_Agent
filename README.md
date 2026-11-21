# Movie Maker

Movie Maker is an AI-powered movie and video generation web service that turns scenario text and uploaded photos into concatenated MP4 movies.

## Architecture

- **Backend**: Python 3.11, FastAPI, SQLAlchemy 2.0 (MySQL 9.3 / SQLite), Celery 5 (Redis broker), Argon2id session authentication + CSRF protection, built-in Python `aiosmtpd` SMTP mail server system (port 1025) with Celery async email worker, In-App Mailbox API, FFmpeg video processing pipeline.
- **Frontend / Client**: React 18 + TypeScript SPA bundled with Vite, conforming to WCAG 2.2 AA accessibility standards. Features Korean/English bilingual interface, Google-style white responsive authentication UI with real-time uniqueness validation for username, email, and phone number, 6-digit email verification with live In-App Mailbox & SMTP delivery, success notification ("인증되었습니다 / You are Verified"), and automatic 2-second redirect to login.
- **Video Engines**:
  - `ltx-2.3`: Local ComfyUI GPU provider (default).
  - `gemini-omni-1.2-flash`: Google Gemini cloud provider with explicit data disclosure & consent gating.
  - `mock`: Fast local FFmpeg-based mock generator for unit/integration testing and development without a GPU.

## Quickstart

### 1. Server Setup (Python 3.11)

```bash
# Set up virtual environment
python -m venv .venv
source .venv/Scripts/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r server/requirements.txt
cp server/.env.example server/.env
```

### 2. Client Setup (React + TypeScript)

```bash
cd client
npm install
npm run build   # Produces production bundle in client/dist/
cd ..
```

### 3. Run the Service

```bash
# 1. API Server (serves React frontend at http://127.0.0.1:8000/)
fastapi dev --port 8000

# 2. Celery Worker (in a separate terminal)
celery -A server.worker.celery_app worker --pool=solo --concurrency=1 -l info

# 3. Celery Beat Scheduler (retention cleanup)
celery -A server.worker.celery_app beat -l info
```

For frontend development with hot-module replacement (HMR), run Vite dev server:
```bash
cd client
npm run dev     # Starts Vite dev server at http://localhost:3000/ with /api proxy
```

## Docker Setup

[Dockerfile](file:///d:/CublickDigital-Codes/Movie_Agent/Dockerfile)을 사용하여 멀티 스테이지 빌드로 클라이언트와 백엔드가 결합된 프로덕션 컨테이너를 빌드하고 실행할 수 있습니다:

```bash
# 프로덕션 이미지 빌드 (React 빌드, 테스트 검증, FastAPI 및 FFmpeg 포함)
docker build -t movie-maker .

# 컨테이너 실행 (포트 8000)
docker run -p 8000:8000 --env-file server/.env movie-maker

# 개발용 클라이언트 타겟 빌드
docker build --target client-dev -t movie-maker-client-dev .
```

## Testing & Quality Gates

```bash
# Linting & Type Checking
ruff check .
ruff format --check .
mypy server tests

# Automated Tests (Unit, Contract, Integration)
pytest tests/unit tests/contract tests/integration -v
```

