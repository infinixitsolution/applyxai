"""
ApplyXAI API. Run from the project root:

    uvicorn backend.app.main:app --reload --port 8010

OpenAPI docs: http://127.0.0.1:8010/api/docs
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("applyxai")

from backend.app.api import (
    admin, admin_outreach, agent, applications, auth, automation, billing, dashboard, health, institute,
    institute_outreach, internal_outreach, jobs, live_interviews, mock_interviews, notifications, partner, plans, profile,
    profile_linkedin, questions, referrals, resumes, settings_automation, site, support,
)
from backend.app.core.config import settings
from backend.app.core.csrf import CSRFMiddleware
from backend.app.core.errors import register_error_handlers


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    from backend.app.core.database import SessionLocal
    from backend.app.core.migrate import upgrade_head
    from backend.app.services import platform_settings_service as ps

    if settings.APP_ENV in ("development", "test"):
        try:
            upgrade_head()
        except Exception:
            logger.exception(
                "Database migration failed. Run: alembic -c backend/alembic.ini upgrade head"
            )

    try:
        with SessionLocal() as db:
            if ps.sync_platform_defaults(db):
                db.commit()
                logger.info("Synced platform notification and email template defaults")
    except Exception:
        logger.exception("Platform template default sync failed")
    if settings.APP_ENV == "production":
        logger.info(
            "Production runtime: db_postgres=%s rate_limit_redis=%s payment_provider=%s clamav=%s",
            not settings.is_sqlite,
            not settings.RATE_LIMIT_STORAGE_URL.startswith("memory"),
            settings.PAYMENT_PROVIDER,
            bool((settings.CLAMAV_HOST or "").strip()),
        )
    yield


def create_app() -> FastAPI:
    public_docs = settings.APP_ENV != "production"
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        docs_url="/api/docs" if public_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if public_docs else None,
        lifespan=_lifespan,
    )
    app.add_middleware(CSRFMiddleware)
    # Added last so it runs first: CORS preflights are answered before CSRF checks.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth.router, prefix="/api")
    app.include_router(profile.router, prefix="/api")
    app.include_router(profile_linkedin.router, prefix="/api")
    app.include_router(questions.router, prefix="/api")
    app.include_router(settings_automation.router, prefix="/api")
    app.include_router(resumes.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(mock_interviews.router, prefix="/api")
    app.include_router(live_interviews.router, prefix="/api")
    app.include_router(support.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(plans.router, prefix="/api")
    app.include_router(automation.router, prefix="/api")
    app.include_router(agent.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(admin_outreach.router, prefix="/api")
    app.include_router(internal_outreach.router, prefix="/api")
    app.include_router(institute.router, prefix="/api")
    app.include_router(institute_outreach.router, prefix="/api")
    app.include_router(institute.invites, prefix="/api")
    app.include_router(partner.router, prefix="/api")
    app.include_router(referrals.router, prefix="/api")
    app.include_router(site.router, prefix="/api")
    app.include_router(site.public_files)
    return app


app = create_app()
