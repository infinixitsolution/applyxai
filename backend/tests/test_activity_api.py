import csv
import io
from datetime import datetime, timedelta, timezone

import pytest

from backend.app.models import ApplicationStatus, AutomationJob, AutomationStatus
from backend.app.services import notification_service
from backend.tests.conftest import csrf_headers
from backend.tests.factories import add_application, user_id

EMAIL = "alice@example.com"
NOW = datetime.now(timezone.utc)


@pytest.fixture
def alice(make_user):
    return make_user(EMAIL)


@pytest.fixture
def history(alice, db):
    add_application(db, EMAIL, "1", title="Python Developer", company="Acme", applied_at=NOW - timedelta(days=2),
                    work_setting="Remote")
    add_application(db, EMAIL, "2", title="Backend Engineer", company="Globex", applied_at=NOW)
    add_application(db, EMAIL, "3", ApplicationStatus.FAILED, title="Data Engineer", company="Acme")
    add_application(db, EMAIL, "4", ApplicationStatus.SKIPPED, title="100% Remote_Dev", company="Initech")
    return alice


def items(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["items"]


# --- applications -----------------------------------------------------------------------

def test_list_applications_newest_first_with_job(history):
    data = history.get("/api/applications").json()["data"]
    assert data["total"] == 4 and data["page"] == 1 and data["page_size"] == 20
    assert [a["job"]["external_id"] for a in data["items"]] == ["4", "3", "2", "1"]
    assert "description" not in data["items"][0]["job"]


@pytest.mark.parametrize("query,expected", [
    ("status=applied", {"1", "2"}),
    ("status=applied&status=failed", {"1", "2", "3"}),
    ("q=engineer", {"2", "3"}),
    ("q=ACME", {"1", "3"}),
    ("q=100%25", {"4"}),                         # % is matched literally, not as a wildcard
    ("q=n_e", set()),                            # _ is literal too (as a wildcard it would match "Engineer")
    ("q=e_d", {"4"}),
    ("company=globex", {"2"}),
    (f"applied_from={(NOW - timedelta(days=1)).date()}", {"2"}),
    (f"applied_to={(NOW - timedelta(days=1)).date()}", {"1"}),
])
def test_application_filters(history, query, expected):
    assert {a["job"]["external_id"] for a in items(history.get(f"/api/applications?{query}"))} == expected


def test_sorting_and_pagination(history):
    by_title = items(history.get("/api/applications?sort=title"))
    assert [a["job"]["title"] for a in by_title][0] == "100% Remote_Dev"
    applied = items(history.get("/api/applications?sort=-applied_at"))
    assert [a["job"]["external_id"] for a in applied][:2] == ["2", "1"]       # unapplied rows last

    page2 = history.get("/api/applications?page=2&page_size=3").json()["data"]
    assert page2["total"] == 4 and len(page2["items"]) == 1


@pytest.mark.parametrize("query", ["sort=password_hash", "status=hired", "page=0", "page_size=101",
                                   "applied_from=2026-10-05&applied_to=2026-10-01", "applied_from=yesterday"])
def test_invalid_list_params(history, query):
    resp = history.get(f"/api/applications?{query}")
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_application_detail_includes_description(history, db):
    app = add_application(db, EMAIL, "5", description="Build APIs")
    data = history.get(f"/api/applications/{app.id}").json()["data"]
    assert data["job"]["description"] == "Build APIs" and data["status"] == "applied"


def test_export_csv_escapes_formulas(history, db):
    add_application(db, EMAIL, "6", title="=HYPERLINK(\"http://evil\")", company="+cmd")
    resp = history.get("/api/applications/export?status=applied")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert resp.headers["content-disposition"].startswith('attachment; filename="applyxai-applications-')
    rows = list(csv.reader(io.StringIO(resp.content.decode("utf-8-sig"))))
    assert rows[0][0] == "Title" and len(rows) == 4
    evil = next(r for r in rows if "HYPERLINK" in r[0])
    assert evil[0].startswith("'=") and evil[1] == "'+cmd"


# --- jobs -------------------------------------------------------------------------------

def test_jobs_list_and_detail(history, db):
    data = items(history.get("/api/jobs"))
    assert len(data) == 4 and data[0]["application"]["status"] in {s.value for s in ApplicationStatus}
    remote = items(history.get("/api/jobs?work_setting=Remote"))
    assert [j["external_id"] for j in remote] == ["1"]

    job_id = data[0]["id"]
    detail = history.get(f"/api/jobs/{job_id}").json()["data"]
    assert detail["id"] == job_id and "description" in detail and "application" in detail


# --- dashboard and usage ----------------------------------------------------------------

def test_dashboard_stats(history, db):
    uid = user_id(db, EMAIL)
    db.add(AutomationJob(user_id=uid, status=AutomationStatus.COMPLETED, successful_count=2, failed_count=1))
    db.add(AutomationJob(user_id=uid, status=AutomationStatus.RUNNING, current_job="Python Developer"))
    db.commit()

    data = history.get("/api/dashboard/stats").json()["data"]
    assert data["applications_by_status"]["applied"] == 2
    assert data["applications_by_status"]["failed"] == 1
    assert data["applications_by_status"]["skipped"] == 1
    assert data["total_applied"] == 2 and data["applied_today"] == 1
    assert data["success_rate"] == pytest.approx(2 / 3, abs=1e-4)
    assert len(data["daily"]) == 30 and data["daily"][-1]["date"] == NOW.date().isoformat()
    assert sum(d["applied"] for d in data["daily"]) == 2 and sum(d["failed"] for d in data["daily"]) == 1
    assert data["top_companies"] == [{"company": "Acme", "applied": 1}, {"company": "Globex", "applied": 1}]
    assert len(data["recent_applications"]) == 4
    assert data["automation"]["active"]["status"] == "running"
    assert data["automation"]["last"]["successful_count"] == 2
    assert data["usage"]["applications"]["used"] == 2


def test_dashboard_for_a_new_user(alice):
    data = alice.get("/api/dashboard/stats").json()["data"]
    assert data["total_applied"] == 0 and data["success_rate"] is None
    assert data["automation"] == {"active": None, "last": None}


def test_usage_endpoint(history):
    data = history.get("/api/usage").json()["data"]
    assert data["plan"] == "free" and data["plan_name"] == "Free"
    assert data["applications"] == {"used": 2, "limit": 10, "remaining": 8}
    assert data["jobs_discovered"] == 4 and data["resumes"]["used"] == 0
    assert data["period"] == NOW.strftime("%Y-%m") and data["limit_reached"] is False


# --- notifications ----------------------------------------------------------------------

def test_notifications_flow(alice, db):
    uid = user_id(db, EMAIL)
    first = notification_service.notify(db, uid, "run_finished", "Run finished", "2 applied", "/automation")
    notification_service.notify(db, uid, "limit_reached", "Monthly limit reached", link="/billing")
    first.created_at -= timedelta(seconds=1)       # Windows clocks can give both the same timestamp
    db.commit()

    data = alice.get("/api/notifications").json()["data"]
    assert data["total"] == 2 and data["unread_count"] == 2
    assert data["items"][0]["title"] == "Monthly limit reached"

    h = csrf_headers(alice)
    assert alice.post(f"/api/notifications/{first.id}/read").status_code == 403          # CSRF required
    read = alice.post(f"/api/notifications/{first.id}/read", headers=h).json()["data"]
    assert read["read_at"] is not None
    assert alice.get("/api/notifications?unread_only=true").json()["data"]["total"] == 1

    assert alice.post("/api/notifications/read-all", headers=h).json()["data"] == {"marked": 1}
    assert alice.get("/api/notifications").json()["data"]["unread_count"] == 0


@pytest.mark.parametrize("path", ["/api/applications", "/api/applications/export", "/api/jobs",
                                  "/api/dashboard/stats", "/api/usage", "/api/notifications"])
def test_endpoints_require_login(api, path):
    assert api.get(path).status_code == 401
