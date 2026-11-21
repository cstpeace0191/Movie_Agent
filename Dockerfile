###################################################
# Movie Maker - Multi-Stage Dockerfile
#
# References: Dockerfile.example
# Builds:
#   1. React 18 + TypeScript + Vite Client
#   2. FastAPI + Celery + FFmpeg Python Backend
#   3. Build-time Test Validation Stage
#   4. Production Final Stage with Built Static SPA
###################################################

###################################################
################  CLIENT STAGES  ##################
###################################################

###################################################
# Stage: client-base
#
# Base stage for client dependency installation and
# source code copying.
###################################################
FROM node:22-slim AS client-base
WORKDIR /usr/local/app/client

# Copy package manifests and install dependencies
COPY client/package.json client/package-lock.json ./
RUN npm ci

# Copy client source code, configuration and build scripts
COPY client/tsconfig.json client/tsconfig.node.json client/vite.config.ts client/index.html client/style.css ./
COPY client/src ./src
COPY client/scripts ./scripts

###################################################
# Stage: client-dev
#
# Development stage for the React/Vite client.
###################################################
FROM client-base AS client-dev
EXPOSE 3000
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3000"]

###################################################
# Stage: client-build
#
# Production build stage compiling React/TypeScript
# into optimized static assets in dist/.
###################################################
FROM client-base AS client-build
RUN npm run build


###################################################
################  BACKEND STAGES  #################
###################################################

###################################################
# Stage: backend-base
#
# Base Python runtime stage with system dependencies
# (FFmpeg, curl) and Python package requirements.
###################################################
FROM python:3.11-slim AS backend-base
WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install required system packages (FFmpeg is essential for video assembly and frame extraction)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python backend dependencies
COPY server/requirements.txt ./server/requirements.txt
RUN pip install -r server/requirements.txt

# Copy server application source code and configuration
COPY server ./server
COPY pyproject.toml ./

###################################################
# Stage: backend-dev
#
# Development stage for FastAPI server with hot-reload.
###################################################
FROM backend-base AS backend-dev
EXPOSE 8000
CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

###################################################
# Stage: worker
#
# Dedicated stage for running the Celery pipeline worker.
###################################################
FROM backend-base AS worker
# Consumes both queues when run alone; compose.yaml splits them into two services.
CMD ["celery", "-A", "server.worker.celery_app", "worker", "-Q", "generation,planning", "--concurrency=1", "-l", "info"]

###################################################
# Stage: test
#
# Automated test execution stage during container build.
# Ensures quality gates pass before final image creation.
###################################################
FROM backend-base AS test
COPY tests ./tests
RUN pytest tests/unit tests/contract -v

###################################################
# Stage: final
#
# Production final stage containing the FastAPI backend
# and the compiled static React frontend assets.
###################################################
FROM backend-base AS final
ENV ENVIRONMENT=production

# Enforce build-time test stage dependency
COPY --from=test /app/server/app/main.py /tmp/.test-passed
RUN rm /tmp/.test-passed

# Copy built React client static bundle into FastAPI static serving directory
COPY --from=client-build /usr/local/app/client/dist ./server/app/static

# Prepare storage directory for media assets
RUN mkdir -p /app/storage

EXPOSE 8000
CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

