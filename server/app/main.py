import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from server.app.api.auth import router as auth_router
from server.app.api.jobs import router as jobs_router
from server.app.api.mail import router as mail_router
from server.app.config import settings
from server.app.db import Base, engine, ensure_schema_compatibility
from server.app.mail_server import start_mail_server, stop_mail_server

# Ensure tables are created immediately and schema is compatible
Base.metadata.create_all(bind=engine)
ensure_schema_compatibility(engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility(engine)
    start_mail_server()
    try:
        yield
    finally:
        stop_mail_server()


app = FastAPI(
    title="Movie Agent API",
    version="0.1.0",
    lifespan=lifespan,
)


# Global error handler returning {"error": {"code": "...", "message": "..."}}
@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    code = "error"
    if exc.status_code == status.HTTP_401_UNAUTHORIZED:
        code = "not_authenticated"
    elif exc.status_code == status.HTTP_403_FORBIDDEN:
        code = "forbidden"
    elif exc.status_code == status.HTTP_404_NOT_FOUND:
        code = "not_found"
    elif exc.status_code == status.HTTP_409_CONFLICT:
        code = "conflict"
    elif exc.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
        code = "validation_failed"

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": str(exc.detail)}},
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return await starlette_http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": {"code": "internal_error", "message": "An unexpected error occurred."}},
    )


# Routes
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(mail_router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "provider": settings.VIDEO_PROVIDER,
        "queue": "idle",
    }


# Windows can register .js as text/plain; browsers then refuse to run the module bundle.
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("text/css", ".css")

# Server static files (serves built React bundle copied to server/app/static)
server_static_dir = Path(__file__).resolve().parent / "static"
if server_static_dir.exists() and any(f.name != ".gitkeep" for f in server_static_dir.iterdir()):
    app.mount("/", StaticFiles(directory=str(server_static_dir), html=True), name="static")
elif Path("client/dist").exists():
    app.mount("/", StaticFiles(directory="client/dist", html=True), name="static")
elif Path("client").exists():
    app.mount("/", StaticFiles(directory="client", html=True), name="static")
