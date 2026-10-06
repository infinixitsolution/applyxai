"""
Fixtures for the SaaS backend. These tests need backend/requirements.txt installed; without
it they're skipped, so the classic engine suite still runs on a plain engine install.
"""

import importlib.util

import pytest

if importlib.util.find_spec("fastapi") is None or importlib.util.find_spec("sqlalchemy") is None:
    collect_ignore_glob = ["test_*.py"]
else:
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from backend.app.core.database import build_engine, get_db
    from backend.app.main import create_app
    from backend.app.models import Base

    @pytest.fixture
    def engine():
        # One shared in-memory connection, so every session sees the same database.
        eng = build_engine("sqlite://", poolclass=StaticPool)
        Base.metadata.create_all(eng)
        yield eng
        eng.dispose()

    @pytest.fixture
    def db(engine):
        session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        yield session
        session.close()

    @pytest.fixture
    def app(engine):
        application = create_app()
        factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

        def _override_get_db():
            session = factory()
            try:
                yield session
            finally:
                session.close()

        application.dependency_overrides[get_db] = _override_get_db
        return application

    @pytest.fixture
    def api(app):
        return TestClient(app, raise_server_exceptions=False)
