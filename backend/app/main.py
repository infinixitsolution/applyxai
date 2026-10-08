"""
ApplyXAI API. Run from the project root:

    uvicorn backend.app.main:app --reload --port 8000

OpenAPI docs: http://127.0.0.1:8000/api/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import (
    admin, agent, applications, auth, automation, billing, dashboard, health, jobs, notifications, plans, profile,
    resumes, site,
)
from backend.app.core.config import settings
from backend.app.core.csrf import CSRFMiddleware
from backend.app.core.errors import register_error_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.APP_NAME} API",
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
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
    app.include_router(resumes.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(applications.router, prefix="/api")
    app.include_router(dashboard.router, prefix="/api")
    app.include_router(notifications.router, prefix="/api")
    app.include_router(plans.router, prefix="/api")
    app.include_router(automation.router, prefix="/api")
    app.include_router(agent.router, prefix="/api")
    app.include_router(billing.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")
    app.include_router(site.router, prefix="/api")
    return app


app = create_app()
