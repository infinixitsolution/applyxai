import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.pagination import PageParams, page_params, page_response, paginate
from backend.app.models import User
from backend.app.schemas.activity import ApplicationBrief, JobDetailWithApplication, JobWithApplication
from backend.app.services import application_service
from automation.options import WORK_SETTINGS

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _with_application(app, schema: type[JobWithApplication] | type[JobDetailWithApplication]) -> dict:
    job_fields = {name: getattr(app.job, name) for name in schema.model_fields if name != "application"}
    return schema(**job_fields, application=ApplicationBrief.model_validate(app)).model_dump(mode="json")


@router.get("", summary="Jobs your automation has encountered (newest first)")
def list_jobs(q: str | None = Query(None, max_length=200), company: str | None = Query(None, max_length=255),
              work_setting: str | None = Query(None, description=", ".join(WORK_SETTINGS)),
              page: PageParams = Depends(page_params), user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    stmt = application_service.jobs_query(user.id, q=q, company=company, work_setting=work_setting)
    items, total = paginate(db, stmt, page)
    return ok(page_response([_with_application(a, JobWithApplication) for a in items], total, page))


@router.get("/{job_id}", summary="One job, if your automation encountered it")
def get_job(job_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    app = application_service.get_job(db, user.id, job_id)
    return ok(_with_application(app, JobDetailWithApplication))
