"""Apply Alembic migrations to the configured database."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config

logger = logging.getLogger("applyxai.migrate")

_ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


def upgrade_head(*, database_url: str | None = None) -> str:
    """
    Run `alembic upgrade head`. Returns the revision id after upgrade.
    Safe to call on every dev server start; no-op when already at head.
    """
    if not _ALEMBIC_INI.is_file():
        raise FileNotFoundError(f"Alembic config not found: {_ALEMBIC_INI}")
    cfg = Config(str(_ALEMBIC_INI))
    if database_url:
        cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")
    from alembic.runtime.migration import MigrationContext
    from sqlalchemy import create_engine

    from backend.app.core.config import settings

    url = database_url or settings.DATABASE_URL
    with create_engine(url).connect() as conn:
        rev = MigrationContext.configure(conn).get_current_revision()
    logger.info("Database schema at revision %s", rev or "base")
    return rev or "base"
