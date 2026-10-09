"""
Endpoints for the desktop agent (`python -m agent`). Authenticated with the device token in
`Authorization: Bearer ...`, never with cookies, so the browser CSRF rules don't apply.
"""

import uuid

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.deps import client_ip, get_current_device
from backend.app.core.database import get_db
from backend.app.core.errors import AppError, ok
from backend.app.core.rate_limit import RateLimiter, get_rate_limiter
from backend.app.models import AgentDevice, Application, ApplicationStatus, Job, User
from backend.app.schemas.automation import AgentAiAnswerIn, AgentTailorIn, ConnectPollIn, ConnectStartIn, EventBatchIn, PairIn, PollIn
from backend.app.services import agent_service, application_context, application_service, automation_service, preferences_service, resume_ai_service, resume_service, run_config_service
from backend.app.services.ai_service import AiTask, ai_available, complete

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


@router.post("/connect/start", status_code=201, summary="Begin one-click browser pairing")
def connect_start(body: ConnectStartIn, request: Request, db: Session = Depends(get_db),
                  limiter: RateLimiter = Depends(get_rate_limiter)):
    ip = client_ip(request)
    limiter.hit("30/hour", "agent-connect-start", ip)
    session, secret = agent_service.start_connect_session(
        db,
        name=body.name,
        platform=body.platform,
        agent_version=body.agent_version,
    )
    db.commit()
    return ok({
        "session_id": str(session.id),
        "secret": secret,
        "expires_at": session.expires_at.isoformat(),
    })


@router.post("/connect/poll", summary="Poll until the user approves in the browser")
def connect_poll(body: ConnectPollIn, db: Session = Depends(get_db)):
    data = agent_service.poll_connect_session(db, body.session_id, body.secret)
    db.commit()
    return ok(data)


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


@router.post("/runs/{run_id}/jobs/{external_job_id}/resume", status_code=201,
             summary="Upload a regenerated resume for a job and link it to the application")
async def upload_job_resume(
    run_id: uuid.UUID,
    external_job_id: str,
    file: UploadFile = File(...),
    device: AgentDevice = Depends(get_current_device),
    db: Session = Depends(get_db),
):
    from sqlalchemy import select

    run = automation_service.agent_run(db, device, run_id)
    user = db.get(User, run.user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    key = str(external_job_id).strip()
    if not key:
        raise AppError("VALIDATION", "Job id is required.", 422)
    job = db.scalar(select(Job).where(Job.external_id == key))
    if job is None:
        raise AppError("NOT_FOUND", "Job not found for this run.", 404)
    app = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))
    if app is None:
        app = Application(
            user_id=user.id,
            job_id=job.id,
            status=ApplicationStatus.DISCOVERED,
            automation_job_id=run.id,
        )
        db.add(app)
        db.flush()
    label = f"{job.title} at {job.company}".strip(" at ")[:255] or "Application resume"
    resume = await resume_service.upload_resume(db, user, file, name=label, counts_against_plan=False)
    resume.ai_metadata = {"generated_by": "automation", "job_id": key, "application_id": str(app.id)}
    application_service.attach_generated_resume(db, user.id, app.id, resume.id)
    db.commit()
    return ok({"resume_id": str(resume.id), "application_id": str(app.id)})


@router.post("/runs/{run_id}/jobs/{external_job_id}/tailor", summary="Tailor default resume to a job description (agent run)")
async def tailor_job_resume(
    run_id: uuid.UUID,
    external_job_id: str,
    body: AgentTailorIn,
    request: Request,
    device: AgentDevice = Depends(get_current_device),
    db: Session = Depends(get_db),
    limiter: RateLimiter = Depends(get_rate_limiter),
):
    ip = client_ip(request)
    limiter.hit("40/hour", "agent-tailor", f"{device.id}:{ip}")
    run = automation_service.agent_run(db, device, run_id)
    if not automation_service.is_active(run):
        raise AppError("RUN_INACTIVE", "This run is no longer active.", 409)
    if not ai_available(db, feature="resume"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for resume tailoring.", 503)
    user = db.get(User, run.user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    resume = run_config_service.default_resume(db, run.user_id)
    if resume is None:
        raise AppError("NOT_FOUND", "Default resume missing.", 404)
    resume_ai_service.persist_master_skills_from_profile(db, run.user_id, resume)
    if not list(resume.master_skills or []):
        raise AppError("MASTER_REQUIRED", "Analyze master skills on your default resume first.", 422)
    key = str(external_job_id).strip()
    if not key:
        raise AppError("VALIDATION", "Job id is required.", 422)
    job = application_service.upsert_job(
        db,
        external_id=key,
        title=(body.job_title or "Unknown").strip()[:500],
        company=(body.company or "").strip()[:255],
        description=body.job_description.strip()[:100_000],
    )
    app = db.scalar(select(Application).where(Application.user_id == user.id, Application.job_id == job.id))
    if app is None:
        app = Application(
            user_id=user.id,
            job_id=job.id,
            status=ApplicationStatus.DISCOVERED,
            automation_job_id=run.id,
        )
        db.add(app)
        db.flush()
    try:
        new = await resume_ai_service.tailor_and_save(
            db,
            user,
            resume_id=resume.id,
            job_description=body.job_description,
            job_id=key,
            application_id=app.id,
        )
    except AppError as exc:
        if exc.code == "GATE_FAILED":
            raise AppError("GATE_FAILED", exc.message, 422) from None
        raise
    db.commit()
    path = resume_service.absolute_path(new)
    if not path.is_file():
        raise AppError("NOT_FOUND", "Tailored file missing.", 500)
    meta = new.ai_metadata or {}
    return Response(
        content=path.read_bytes(),
        media_type=resume_service.MIME_BY_TYPE.get(new.file_type, "application/octet-stream"),
        headers={
            "X-Resume-Id": str(new.id),
            "X-Match-Score": str(meta.get("match_score", "")),
            "X-Fit-Score": str(meta.get("fit_score", "")),
            "Content-Disposition": f'attachment; filename="{new.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/runs/{run_id}/ai/answer", summary="Platform AI answer for an application question")
def ai_answer(run_id: uuid.UUID, body: AgentAiAnswerIn, request: Request,
              device: AgentDevice = Depends(get_current_device), db: Session = Depends(get_db),
              limiter: RateLimiter = Depends(get_rate_limiter)):
    ip = client_ip(request)
    limiter.hit("60/minute", "agent-ai", f"{device.id}:{ip}")
    run = automation_service.agent_run(db, device, run_id)
    if not automation_service.is_active(run):
        raise AppError("RUN_INACTIVE", "This run is no longer active.", 409)
    if not ai_available(db, feature="applications"):
        raise AppError("AI_DISABLED", "Platform AI is not enabled for applications.", 503)
    user = db.get(User, run.user_id)
    if user is None:
        raise AppError("NOT_FOUND", "User not found", 404)
    doc = preferences_service.application_document(db, user)
    if not doc.get("ai_applications_enabled"):
        raise AppError("AI_DISABLED", "AI assistance is turned off in application preferences.", 403)
    deny = (doc.get("ai_policy") or {}).get("deny_label_contains") or []
    label = body.question.lower()
    if any(d and d in label for d in deny):
        raise AppError("AI_DENIED", "This question is not eligible for AI answers.", 403)
    qtype = (body.question_type or "text").lower()
    if qtype not in ("text", "textarea", "select", "radio"):
        raise AppError("VALIDATION", "Unsupported question type.", 422)
    ctx = application_context.build_context(
        db, run.user_id, job_description=body.job_description, job_title=body.job_title, company=body.company,
    )
    system = (
        "You help fill job application forms. Answer briefly and truthfully using only the candidate context. "
        "Do not invent credentials, employers, or legal status. If unsure, say you prefer not to guess."
    )
    if qtype in ("select", "radio") and body.options:
        opts = "\n".join(f"- {o}" for o in body.options[:40])
        user = f"Context:\n{ctx}\n\nQuestion: {body.question}\n\nPick exactly one option (copy the option text verbatim):\n{opts}"
        task = AiTask.APP_ANSWER_SELECT
    else:
        user = f"Context:\n{ctx}\n\nQuestion ({qtype}): {body.question}\n\nAnswer:"
        task = AiTask.APP_ANSWER
    answer = complete(db, task, system=system, user=user, feature="applications", max_tokens=800)
    return ok({"answer": answer})
