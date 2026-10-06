import csv
import io
import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.pagination import PageParams, page_params, page_response, paginate
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import ApplicationStatus, User
from backend.app.schemas.activity import ApplicationDetail, ApplicationOut
from backend.app.services import application_service
from backend.app.services.application_service import DEFAULT_SORT

router = APIRouter(prefix="/applications", tags=["applications"])

EXPORT_MAX_ROWS = 10_000
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class _Filters:
    def __init__(
        self,
        status: list[ApplicationStatus] | None = Query(None, description="Repeat to match several"),
        q: str | None = Query(None, max_length=200, description="Search title, company, location"),
        company: str | None = Query(None, max_length=255),
        applied_from: date | None = Query(None, description="YYYY-MM-DD (UTC), inclusive"),
        applied_to: date | None = Query(None, description="YYYY-MM-DD (UTC), inclusive"),
        automation_job_id: uuid.UUID | None = None,
        sort: str = Query(DEFAULT_SORT, max_length=20,
                          description="created_at, applied_at, updated_at, company, title; prefix - for descending"),
    ):
        if applied_from and applied_to and applied_from > applied_to:
            raise AppError("VALIDATION_ERROR", "applied_from must be on or before applied_to", status_code=422)
        self.kwargs = dict(status=status, q=q, company=company, applied_from=applied_from, applied_to=applied_to,
                           automation_job_id=automation_job_id, sort=sort)


def _out(app) -> dict:
    return ApplicationOut.model_validate(app).model_dump(mode="json")


def _csv_cell(value) -> str:
    text = "" if value is None else str(value)
    # Spreadsheet apps execute cells starting with these characters as formulas.
    return "'" + text if text.startswith(_FORMULA_PREFIXES) else text


@router.get("", summary="Your applications (filter, search, sort, paginate)")
def list_applications(filters: _Filters = Depends(), page: PageParams = Depends(page_params),
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    items, total = paginate(db, application_service.applications_query(user.id, **filters.kwargs), page)
    return ok(page_response([_out(a) for a in items], total, page))


@router.get("/export", summary="Download your applications as CSV (same filters as the list)")
def export_applications(filters: _Filters = Depends(), user: User = Depends(get_current_user),
                        db: Session = Depends(get_db), limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("20/hour", "applications-export", str(user.id))
    rows = db.scalars(application_service.applications_query(user.id, **filters.kwargs).limit(EXPORT_MAX_ROWS))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Title", "Company", "Location", "Status", "Applied at (UTC)", "Failure reason",
                     "Job URL", "Work setting", "Discovered at (UTC)"])
    for a in rows.unique():
        writer.writerow([_csv_cell(v) for v in (
            a.job.title, a.job.company, a.job.location, a.status.value,
            a.applied_at.isoformat() if a.applied_at else "", a.failure_reason, a.job.job_url,
            a.job.work_setting, a.job.discovered_at.isoformat(),
        )])
    filename = f"applyxai-applications-{datetime.now(timezone.utc):%Y%m%d}.csv"
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    })


@router.get("/{application_id}", summary="One of your applications, with the full job")
def get_application(application_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = application_service.get_application(db, user.id, application_id)
    return ok(ApplicationDetail.model_validate(app).model_dump(mode="json"))
