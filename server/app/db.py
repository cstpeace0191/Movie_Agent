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


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped SQLAlchemy database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
