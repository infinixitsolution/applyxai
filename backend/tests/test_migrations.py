"""
Alembic migrations must build exactly the schema the models describe, and tear it down again.
Runs on SQLite always; also on PostgreSQL when TEST_POSTGRES_URL is set, e.g.
    TEST_POSTGRES_URL=postgresql+psycopg://postgres:secret@127.0.0.1:5432/applyxai_test
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from backend.app.core.database import build_engine
from backend.app.models import Base

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
EXPECTED_TABLES = {
    "users", "user_profiles", "auth_tokens", "application_preferences", "search_configs", "resumes", "jobs", "applications",
    "automation_jobs", "plans", "subscriptions", "usage_counters",
}


@pytest.fixture(params=["sqlite", "postgresql"])
def database_url(request, tmp_path):
    if request.param == "sqlite":
        return f"sqlite:///{(tmp_path / 'migrate.db').as_posix()}"
    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("set TEST_POSTGRES_URL to also run migrations against PostgreSQL")
    return url


def _alembic_config(url):
    cfg = Config(str(ALEMBIC_INI))
    cfg.attributes["database_url"] = url
    return cfg


def test_upgrade_matches_models_then_downgrade_cleans_up(database_url):
    cfg = _alembic_config(database_url)
    engine = build_engine(database_url)
    try:
        command.downgrade(cfg, "base")          # clean slate on a reused Postgres database
        command.upgrade(cfg, "head")
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

        with engine.connect() as conn:
            drift = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
        assert drift == [], f"models and migrations disagree: {drift}"

        command.downgrade(cfg, "base")
        assert set(inspect(engine).get_table_names()) - {"alembic_version"} == set()
    finally:
        engine.dispose()
