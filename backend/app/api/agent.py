"""
Endpoints for the desktop agent (`python -m agent`). Authenticated with the device token in
`Authorization: Bearer ...`, never with cookies, so the browser CSRF rules don't apply.
"""

import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.app.api.deps import client_ip, get_current_device
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import AgentDevice
from backend.app.schemas.automation import EventBatchIn, PairIn, PollIn
from backend.app.services import agent_service, automation_service, resume_service, run_config_service

router = APIRouter(prefix="/agent", tags=["desktop agent"])


@router.post("/pair", summary="Exchange a pairing code for a device token")
def pair(body: PairIn, request: Request, db: Session = Depends(get_db),
         limiter: RateLimiter = Depends(get_rate_limiter)):
    ip = client_ip(request)
    limiter.hit("10/minute", "agent-pair", ip)
    limiter.hit("50/hour", "agent-pair-hourly", ip)
    device, token = agent_service.pair(db, body.code, name=body.name, platform=body.platform,
                                       agent_version=body.agent_version)
    db.commit()
    return ok({"token": token, "device_id": str(device.id), "user_id": str(device.user_id), "name": device.name})


@router.get("/me", summary="This computer, as the server sees it")
def me(device: AgentDevice = Depends(get_current_device)):
    return ok(agent_service.device_out(device))


@router.post("/unpair", summary="Disconnect this computer")
def unpair(device: AgentDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    agent_service.revoke(db, device.user_id, device.id)
    db.commit()
    return ok({"revoked": True})


@router.post("/poll", summary="Heartbeat; returns a queued run for an idle agent")
def poll(body: PollIn, device: AgentDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    run = automation_service.poll(db, device, active_run_id=body.active_run_id,
                                  agent_version=body.agent_version, platform=body.platform)
    db.commit()
    return ok({"run": run, "user_id": str(device.user_id)})


@router.get("/runs/{run_id}/resume", summary="The default resume for a run this computer holds")
def run_resume(run_id: uuid.UUID, device: AgentDevice = Depends(get_current_device), db: Session = Depends(get_db)):
    run = automation_service.agent_run(db, device, run_id)
    resume = run_config_service.default_resume(db, run.user_id) if automation_service.is_active(run) else None
    path = resume_service.absolute_path(resume) if resume else None
    if path is None or not path.is_file():
        raise AppError("NOT_FOUND", "Resume not found", 404)
    return FileResponse(path, media_type=resume_service.MIME_BY_TYPE[resume.file_type], filename=resume.filename,
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})


@router.post("/runs/{run_id}/events", summary="Report numbered engine events; returns run/pause/stop")
def post_events(run_id: uuid.UUID, body: EventBatchIn, device: AgentDevice = Depends(get_current_device),
                db: Session = Depends(get_db)):
    result = automation_service.ingest_batch(db, device, run_id, body.first_seq, body.events)
    db.commit()
    return ok(result)
