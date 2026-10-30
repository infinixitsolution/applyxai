"""Smoke tests for Naukri staging flag (ENABLE_NAUKRI)."""

from backend.app.schemas.platform_settings import JobSourcesIn
from backend.app.services import platform_settings_service as ps


def test_enable_naukri_flag_exposes_naukri_without_admin_toggle(db, monkeypatch):
    from backend.app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ENABLE_NAUKRI", True)
    ps.update_job_sources(db, JobSourcesIn(linkedin=True, naukri=False))
    db.commit()
    assert ps.get_job_sources(db)["naukri"] is True
