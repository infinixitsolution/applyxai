"""Health endpoint and the `{success, data | error}` envelope."""

from fastapi import APIRouter
from pydantic import BaseModel


def test_health_reports_ok_with_envelope(api):
    resp = api.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["app"] == "ApplyXAI"


def test_unknown_route_uses_error_envelope(api):
    resp = api.get("/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.json() == {"success": False, "error": {"code": "NOT_FOUND", "message": "Not Found"}}


def _add_probe_routes(app):
    router = APIRouter()

    class Payload(BaseModel):
        job_type: list[str]

    @router.post("/probe/validate")
    def validate(payload: Payload):
        return {"success": True, "data": payload.model_dump()}

    @router.get("/probe/crash")
    def crash():
        raise RuntimeError("secret internal detail /etc/passwd")

    app.include_router(router, prefix="/api")


def test_validation_errors_use_envelope(app, api):
    _add_probe_routes(app)
    resp = api.post("/api/probe/validate", json={"job_type": "Full-time"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"][0]["field"] == "job_type"


def test_unhandled_errors_never_leak_internals(app, api):
    _add_probe_routes(app)
    resp = api.get("/api/probe/crash")
    assert resp.status_code == 500
    text = resp.text
    assert "secret internal detail" not in text and "Traceback" not in text
    assert resp.json()["error"]["code"] == "INTERNAL_ERROR"


def test_cors_allows_only_configured_origins(api):
    allowed = api.options("/api/health", headers={"Origin": "http://localhost:5173",
                                                  "Access-Control-Request-Method": "GET"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
    denied = api.get("/api/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in denied.headers
