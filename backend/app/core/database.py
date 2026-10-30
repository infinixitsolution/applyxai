"""SQLAlchemy engine, session factory, and the FastAPI session dependency."""

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


def build_engine(url: str, echo: bool = False, **engine_kwargs) -> Engine:
    parsed = make_url(url)
    connect_args = {}
    if parsed.get_backend_name() == "sqlite":
        connect_args["check_same_thread"] = False
        # Wait on locks instead of failing login/API with "database is locked" (common on Windows dev).
        connect_args["timeout"] = 30
        if parsed.database and parsed.database != ":memory:":
            Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url, echo=echo, pool_pre_ping=True, connect_args=connect_args, **engine_kwargs)

    if parsed.get_backend_name() == "sqlite":
        @event.listens_for(engine, "connect")
        def _configure_sqlite_connection(dbapi_connection, _record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

    return engine


engine = build_engine(settings.DATABASE_URL, echo=settings.DATABASE_ECHO)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
