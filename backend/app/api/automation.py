import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user
from backend.app.core.database import get_db
from backend.app.core.errors import ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import User
from backend.app.schemas.automation import StartRunIn
from backend.app.services import agent_service, automation_service
from backend.app.services.automation_service import run_out

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("", summary="Current and recent runs, connected computers, and readiness")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(automation_service.overview(db, user.id))


@router.post("/start", status_code=201, summary="Queue a run for your desktop agent")
def start(body: StartRunIn | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db),
          limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("30/hour", "automation-start", str(user.id))
    run = automation_service.start_run(db, user, dry_run=bool(body and body.dry_run))
    db.commit()
    return ok(run_out(run))


# Device routes come before /{run_id} so "devices" isn't parsed as a run id.
@router.get("/devices", summary="Computers connected to your account")
def list_devices(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok({"devices": [agent_service.device_out(d) for d in agent_service.list_devices(db, user.id)]})


@router.post("/devices/pairing-code", status_code=201, summary="Get a code to connect the desktop agent")
def pairing_code(user: User = Depends(get_current_user), db: Session = Depends(get_db),
                 limiter: RateLimiter = Depends(get_rate_limiter)):
    limiter.hit("10/hour", "pairing-code", str(user.id))
    code, expires = agent_service.create_pairing_code(db, user)
    db.commit()
    return ok({"code": code, "expires_at": expires.isoformat()})


@router.delete("/devices/{device_id}", summary="Disconnect a computer")
def revoke_device(device_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    agent_service.revoke(db, user.id, device_id)
    db.commit()
    return ok({"revoked": True})


@router.get("/{run_id}", summary="One run")
def get_run(run_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(run_out(automation_service.get_run(db, user.id, run_id)))


@router.get("/{run_id}/logs", summary="A run's activity log; pass the last seq you have as `after`")
def get_logs(run_id: uuid.UUID, after: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=500),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return ok(automation_service.logs(db, user.id, run_id, after=after, limit=limit))


@router.post("/{run_id}/pause", summary="Pause after the current job")
def pause(run_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = automation_service.pause_run(db, user.id, run_id)
    db.commit()
    return ok(run_out(run))


@router.post("/{run_id}/resume", summary="Resume a paused run")
def resume(run_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = automation_service.resume_run(db, user.id, run_id)
    db.commit()
    return ok(run_out(run))


@router.post("/{run_id}/stop", summary="Stop after the current job")
def stop(run_id: uuid.UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    run = automation_service.stop_run(db, user.id, run_id)
    db.commit()
    return ok(run_out(run))
