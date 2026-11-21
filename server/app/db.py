from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from server.app.config import settings


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
    if not inspector.has_table("users"):
        return

    existing_columns = {col["name"] for col in inspector.get_columns("users")}
    columns_to_add = [
        ("country", "VARCHAR(64) NULL"),
        ("phone", "VARCHAR(32) NULL"),
        ("email", "VARCHAR(255) NULL"),
        ("email_verified", "BOOLEAN NOT NULL DEFAULT 0"),
        ("verification_code", "VARCHAR(64) NULL"),
        ("verification_expires_at", "DATETIME NULL"),
    ]

    with target_engine.begin() as conn:
        for col_name, col_def in columns_to_add:
            if col_name not in existing_columns:
                try:
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}"))
                except Exception:
                    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
