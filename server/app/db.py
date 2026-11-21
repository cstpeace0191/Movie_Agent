import logging
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from server.app.config import settings

logger = logging.getLogger(__name__)


def get_engine(db_url: str | None = None):
    """Create and return a SQLAlchemy engine with appropriate connection arguments."""
    url = db_url or settings.DATABASE_URL
    connect_args = {}
    if url.startswith("sqlite"):
        connect_args["check_same_thread"] = False
        return create_engine(url, connect_args=connect_args)
    if url.startswith("mysql"):
        return create_engine(
            url,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args=connect_args,
        )
    return create_engine(url, connect_args=connect_args)


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_schema_compatibility(eng=None) -> None:
    """Ensure newly added columns exist in the database table without manual migration."""
    from sqlalchemy import inspect, text

    target_engine = eng or engine
    Base.metadata.create_all(bind=target_engine)
    inspector = inspect(target_engine)

    with target_engine.begin() as conn:
        quote = conn.dialect.identifier_preparer.quote
        for table, columns_to_add in _ADDED_COLUMNS.items():
            if not inspector.has_table(table):
                continue
            existing_columns = {col["name"] for col in inspector.get_columns(table)}
            for col_name, col_def in columns_to_add:
                if col_name in existing_columns:
                    continue
                try:
                    conn.execute(
                        text(f"ALTER TABLE {quote(table)} ADD COLUMN {quote(col_name)} {col_def}")
                    )
                except Exception:  # noqa: BLE001 - another process may have added it first
                    logger.warning("Could not add column %s.%s", table, col_name, exc_info=True)


# Columns added after a table was first created (no Alembic yet; research R13 of feature 002).
_ADDED_COLUMNS: dict[str, list[tuple[str, str]]] = {
    "users": [
        ("country", "VARCHAR(64) NULL"),
        ("phone", "VARCHAR(32) NULL"),
        ("email", "VARCHAR(255) NULL"),
        ("email_verified", "BOOLEAN NOT NULL DEFAULT 0"),
        ("verification_code", "VARCHAR(64) NULL"),
        ("verification_expires_at", "DATETIME NULL"),
    ],
    "jobs": [
        ("render_options", "JSON NULL"),
        ("text_assist_consent_at", "DATETIME NULL"),
        ("review_confirmed_at", "DATETIME NULL"),
        ("bgm_path", "VARCHAR(500) NULL"),
        ("subtitles_srt_path", "VARCHAR(500) NULL"),
        ("subtitles_ass_path", "VARCHAR(500) NULL"),
        ("final_duration_seconds", "FLOAT NULL"),
    ],
    "scenes": [
        ("kind", "VARCHAR(16) NOT NULL DEFAULT 'scene'"),
        ("caption", "TEXT NULL"),
        ("caption_source", "VARCHAR(16) NULL"),
        ("narration", "TEXT NULL"),
        ("transition", "VARCHAR(32) NULL"),
        ("motion", "VARCHAR(16) NULL"),
        ("start_seconds", "FLOAT NULL"),
        ("length_seconds", "FLOAT NULL"),
    ],
    "source_images": [
        ("note", "VARCHAR(500) NULL"),
    ],
}


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
