"""Admin API: access control, analytics, user management, complimentary plans, plan editing, lists."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.models import (
    AdminAction, AgentDevice, Application, ApplicationStatus, AutomationJob, AutomationLog, AutomationStatus, Job,
    Plan, Subscription, SubscriptionStatus, User,
)
from backend.app.services import admin_service, dashboard_service
from backend.app.services.payments import get_payment_provider
from backend.app.services.payments.null import NullProvider
from backend.tests.conftest import csrf_headers


@pytest.fixture
def admin(app, db, make_user):
    client = make_user("boss@example.com", client=TestClient(app, raise_server_exceptions=False))
    user = db.scalar(select(User).where(User.email == "boss@example.com"))
    user.is_admin = True
    db.commit()
    client.user = user
    return client


@pytest.fixture
def alice(app, db, make_user):
    client = make_user("alice@example.com", client=TestClient(app, raise_server_exceptions=False))
    client.user = db.scalar(select(User).where(User.email == "alice@example.com"))
    return client


@pytest.fixture(autouse=True)
def null_provider(app):
    app.dependency_overrides[get_payment_provider] = lambda: NullProvider()


def get(client, path, **params):
    return client.get(f"/api/admin{path}", params=params)


def send(client, method, path, body=None):
    return client.request(method, f"/api/admin{path}", json=body, headers=csrf_headers(client))


def data(resp):
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def plan_of(client):
    return client.get("/api/usage").json()["data"]["plan"]


def add_run(db, user, status=AutomationStatus.RUNNING, **kw):
    run = AutomationJob(user_id=user.id, status=status, **kw)
    db.add(run)
    db.commit()
    return run


# ----------------------------------------------------------------------------- access
ADMIN_GETS = ["/analytics", "/users", "/subscriptions", "/automation-jobs", "/applications", "/logs",
              "/audit-log", "/workers", "/plans"]


@pytest.mark.parametrize("path", ADMIN_GETS)
def test_regular_users_get_403_and_anonymous_401(api, alice, path):
    assert get(alice, path).status_code == 403
    assert get(alice, path).json()["error"]["code"] == "FORBIDDEN"
    assert TestClient(api.app).get(f"/api/admin{path}").status_code == 401


def test_regular_users_cannot_change_anything(alice, db):
    assert send(alice, "PATCH", f"/users/{alice.user.id}", {"is_admin": True}).status_code == 403
    assert send(alice, "PUT", "/plans/free", {"name": "Free", "price_cents": 0, "applications_per_month": 9999,
                                               "resumes": 9}).status_code == 403
    db.refresh(alice.user)
    assert alice.user.is_admin is False


# ----------------------------------------------------------------------------- analytics
def test_analytics_counts_users_plans_and_runs(admin, alice, db):
    add_run(db, alice.user)
    out = data(get(admin, "/analytics"))
    assert out["users"]["total"] == 2 and out["users"]["admins"] == 1 and out["users"]["new_7d"] == 2
    assert out["automation"]["active_runs"] == 1
    assert out["automation"]["last_24h_by_status"]["running"] == 1
    assert len(out["applications"]["daily"]) == dashboard_service.CHART_DAYS
    assert out["subscriptions"]["by_plan"] == [] and out["subscriptions"]["mrr_cents"] == {}

    data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "pro", "months": 1}))
    out = data(get(admin, "/analytics"))
    assert out["subscriptions"]["by_plan"] == [{"code": "pro", "name": "Pro", "count": 1}]
    assert out["subscriptions"]["mrr_cents"] == {}, "complimentary plans aren't revenue"


# ----------------------------------------------------------------------------- users
def test_users_list_search_and_filters(admin, alice, make_user, app, db):
    make_user("bob@example.com", client=TestClient(app))
    assert data(get(admin, "/users"))["total"] == 3
    assert [u["email"] for u in data(get(admin, "/users", q="ALI"))["items"]] == ["alice@example.com"]
    assert [u["email"] for u in data(get(admin, "/users", status="admin"))["items"]] == ["boss@example.com"]
    assert data(get(admin, "/users", q="100%"))["total"] == 0

    data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "starter", "months": 2}))
    assert [u["email"] for u in data(get(admin, "/users", plan="starter"))["items"]] == ["alice@example.com"]
    assert data(get(admin, "/users", plan="free"))["total"] == 2
    row = data(get(admin, "/users", q="alice"))["items"][0]
    assert row["plan"] == "starter" and row["plan_name"] == "Starter" and "password_hash" not in row


def test_user_detail_and_unknown_user(admin, alice):
    out = data(get(admin, f"/users/{alice.user.id}"))
    assert out["user"]["email"] == "alice@example.com"
    assert out["usage"]["applications"]["limit"] == 10
    assert out["subscription"] is None and out["runs"] == [] and out["devices"] == []
    assert get(admin, "/users/00000000-0000-0000-0000-000000000000").status_code == 404


def test_disabling_a_user_signs_them_out_disconnects_agents_and_stops_their_run(admin, alice, db):
    device = AgentDevice(user_id=alice.user.id, name="Laptop", token_hash="h" * 64,
                         paired_at=datetime.now(timezone.utc))
    db.add(device)
    db.commit()
    run = add_run(db, alice.user, device_id=device.id)
    assert alice.get("/api/auth/me").status_code == 200

    out = data(send(admin, "PATCH", f"/users/{alice.user.id}", {"is_active": False}))
    assert out["user"]["is_active"] is False

    assert alice.get("/api/auth/me").status_code == 401
    login = alice.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"})
    assert login.status_code in (401, 403)
    db.expire_all()
    assert db.get(AgentDevice, device.id).revoked_at is not None
    run = db.get(AutomationJob, run.id)
    assert run.control == "stop" and run.stop_reason == "admin"
    action = db.scalar(select(AdminAction))
    assert action.action == "user.update" and action.target == "alice@example.com"
    assert action.details == {"is_active": [True, False]} and action.admin_email == "boss@example.com"

    data(send(admin, "PATCH", f"/users/{alice.user.id}", {"is_active": True}))
    login = alice.post("/api/auth/login", json={"email": "alice@example.com", "password": "correct horse battery"})
    assert login.status_code == 200


def test_admins_cannot_lock_themselves_out(admin, db):
    for body in ({"is_active": False}, {"is_admin": False}):
        resp = send(admin, "PATCH", f"/users/{admin.user.id}", body)
        assert resp.status_code == 400 and resp.json()["error"]["code"] == "CANNOT_CHANGE_SELF"
    assert data(get(admin, "/analytics"))


def test_promoting_a_user_to_admin(admin, alice):
    data(send(admin, "PATCH", f"/users/{alice.user.id}", {"is_admin": True}))
    assert get(alice, "/analytics").status_code == 200


# ----------------------------------------------------------------------------- complimentary plans
def test_grant_and_revoke_a_complimentary_plan(admin, alice, db):
    out = data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan",
                    {"plan": "pro", "months": 3, "note": "Beta tester"}))
    assert out["subscription"]["plan"]["code"] == "pro" and out["subscription"]["provider"] == "admin"
    assert plan_of(alice) == "pro"
    assert alice.get("/api/usage").json()["data"]["applications"]["limit"] == 500
    notes = alice.get("/api/notifications").json()["data"]["items"]
    assert any(n["type"] == "plan_granted" for n in notes)

    # The user can't "cancel" it at the payment provider: there's nothing to cancel.
    resp = alice.post("/api/billing/cancel", headers=csrf_headers(alice))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "COMPLIMENTARY_PLAN"

    # A second grant replaces the first.
    data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "starter", "months": 1}))
    assert plan_of(alice) == "starter"
    assert db.scalar(select(Subscription).where(Subscription.status == SubscriptionStatus.ACTIVE)).plan.code == "starter"

    data(send(admin, "POST", f"/users/{alice.user.id}/revoke-plan"))
    assert plan_of(alice) == "free"
    resp = send(admin, "POST", f"/users/{alice.user.id}/revoke-plan")
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "NO_GRANT"
    actions = [a.action for a in db.scalars(select(AdminAction).order_by(AdminAction.created_at))]
    assert actions.count("plan.grant") == 2 and "plan.revoke" in actions


@pytest.mark.parametrize("body,code,status", [
    ({"plan": "free", "months": 1}, "FREE_PLAN", 400),
    ({"plan": "gold", "months": 1}, "PLAN_NOT_FOUND", 404),
    ({"plan": "pro", "months": 0}, "VALIDATION_ERROR", 422),
    ({"plan": "pro", "months": 25}, "VALIDATION_ERROR", 422),
])
def test_grant_validation(admin, alice, body, code, status):
    resp = send(admin, "POST", f"/users/{alice.user.id}/grant-plan", body)
    assert resp.status_code == status and resp.json()["error"]["code"] == code


def test_no_grant_over_a_paid_plan(admin, alice):
    assert alice.post("/api/billing/checkout", json={"plan": "starter"}, headers=csrf_headers(alice)).status_code == 200
    resp = send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "pro", "months": 1})
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "HAS_SUBSCRIPTION"
    assert plan_of(alice) == "starter"


def test_buying_a_plan_ends_a_complimentary_one(admin, alice, db):
    data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "starter", "months": 6}))
    assert alice.post("/api/billing/checkout", json={"plan": "pro"}, headers=csrf_headers(alice)).status_code == 200
    assert plan_of(alice) == "pro"
    grant = db.scalar(select(Subscription).where(Subscription.provider == "admin"))
    db.refresh(grant)
    assert grant.status == SubscriptionStatus.CANCELLED


# ----------------------------------------------------------------------------- runs, lists
def test_admin_stops_a_users_run(admin, alice, db):
    run = add_run(db, alice.user)
    out = data(send(admin, "POST", f"/automation-jobs/{run.id}/stop"))
    assert out["control"] == "stop" and out["stop_reason"] == "admin"
    assert send(admin, "POST", "/automation-jobs/00000000-0000-0000-0000-000000000000/stop").status_code == 404

    finished = add_run(db, alice.user, status=AutomationStatus.COMPLETED)
    assert send(admin, "POST", f"/automation-jobs/{finished.id}/stop").status_code == 409
    assert db.scalar(select(AdminAction).where(AdminAction.action == "run.stop")).details == {"run_id": str(run.id)}


def test_lists_across_users(admin, alice, db):
    run = add_run(db, alice.user)
    add_run(db, admin.user, status=AutomationStatus.COMPLETED)
    job = Job(external_id="42", title="Backend Engineer", company="Acme")
    db.add(job)
    db.flush()
    db.add(Application(user_id=alice.user.id, job_id=job.id, status=ApplicationStatus.APPLIED,
                       applied_at=datetime.now(timezone.utc)))
    now = datetime.now(timezone.utc)
    db.add_all([AutomationLog(automation_job_id=run.id, user_id=alice.user.id, seq=1, ts=now, level="info",
                              event="started", message="Opening LinkedIn"),
                AutomationLog(automation_job_id=run.id, user_id=alice.user.id, seq=2, ts=now + timedelta(seconds=1),
                              level="error", event="failed", message="Form had an unknown question")])
    db.commit()

    runs = data(get(admin, "/automation-jobs"))
    assert runs["total"] == 2
    active = data(get(admin, "/automation-jobs", status="active"))["items"]
    assert [r["user_email"] for r in active] == ["alice@example.com"]
    assert get(admin, "/automation-jobs", status="bogus").status_code == 422

    apps = data(get(admin, "/applications", q="acme"))["items"]
    assert apps[0]["job"]["title"] == "Backend Engineer" and apps[0]["user_email"] == "alice@example.com"
    assert data(get(admin, "/applications", status="failed"))["total"] == 0

    assert [l["message"] for l in data(get(admin, "/logs"))["items"]] == ["Form had an unknown question"]
    every = admin.get("/api/admin/logs", params=[("level", "info"), ("level", "error")])
    assert data(every)["total"] == 2
    assert data(get(admin, "/logs", level="info", q="linkedin"))["total"] == 1


def test_subscriptions_list(admin, alice):
    data(send(admin, "POST", f"/users/{alice.user.id}/grant-plan", {"plan": "pro", "months": 1}))
    subs = data(get(admin, "/subscriptions"))["items"]
    assert subs[0]["user_email"] == "alice@example.com" and subs[0]["plan"]["code"] == "pro"
    assert data(get(admin, "/subscriptions", status="cancelled"))["total"] == 0
    assert data(get(admin, "/subscriptions", plan="starter"))["total"] == 0


def test_workers_never_fail_when_redis_is_down(admin, alice, db, monkeypatch):
    db.add(AgentDevice(user_id=alice.user.id, name="Laptop", token_hash="x" * 64,
                       last_seen_at=datetime.now(timezone.utc)))
    db.commit()
    monkeypatch.setattr(admin_service, "celery_workers", lambda: {"broker": "unreachable", "workers": []})
    out = data(get(admin, "/workers"))
    assert out["celery"]["broker"] == "unreachable"
    assert out["devices"][0]["user_email"] == "alice@example.com" and out["devices"][0]["online"] is True
    assert out["devices"][0]["running"] is False


def test_celery_ping_reports_an_unreachable_broker(monkeypatch):
    from backend.app import worker

    def boom(*a, **k):
        raise ConnectionError("no redis")
    monkeypatch.setattr(worker.celery_app, "connection_for_read", boom)
    assert admin_service.celery_workers() == {"broker": "unreachable", "workers": []}


def test_a_run_stopped_by_an_admin_says_so_in_its_last_log_line():
    from backend.app.services.ingest_service import _stopped_message
    assert _stopped_message("admin") == "Run stopped by ApplyXAI support."


def test_make_admin_command(alice, engine, monkeypatch, capsys):
    from sqlalchemy.orm import sessionmaker

    from backend.app import cli
    monkeypatch.setattr(cli, "SessionLocal", sessionmaker(bind=engine, expire_on_commit=False))
    assert cli.main(["make-admin", "--email", "ALICE@example.com"]) == 0
    assert get(alice, "/analytics").status_code == 200
    assert cli.main(["make-admin", "--email", "alice@example.com", "--revoke"]) == 0
    assert get(alice, "/analytics").status_code == 403
    assert cli.main(["make-admin", "--email", "nobody@example.com"]) == 1
    assert "Register it first" in capsys.readouterr().err


# ----------------------------------------------------------------------------- plans
def plan_body(**kw):
    return {"name": "Starter", "price_cents": 49900, "applications_per_month": 100, "resumes": 3,
            "is_active": True, "sort_order": 1, **kw}


def test_plans_list_includes_limits_and_subscribers(admin):
    plans = data(get(admin, "/plans"))["plans"]
    assert [p["code"] for p in plans] == ["free", "starter", "pro", "premium"]
    starter = plans[1]
    assert starter["limits"] == {"applications_per_month": 100, "resumes": 3} and starter["subscribers"] == 0


def test_editing_a_plan_changes_limits_for_everyone_on_it(admin, alice, db):
    out = data(send(admin, "PUT", "/plans/free", {"name": "Free", "price_cents": 0, "applications_per_month": 25,
                                                 "resumes": 2, "is_active": True, "sort_order": 0}))
    assert out["limits"] == {"applications_per_month": 25, "resumes": 2}
    assert alice.get("/api/usage").json()["data"]["applications"]["limit"] == 25
    public = {p["code"]: p for p in alice.get("/api/plans").json()["data"]["plans"]}
    assert public["free"]["limits"]["applications_per_month"] == 25
    action = db.scalar(select(AdminAction).where(AdminAction.action == "plan.update"))
    assert action.target == "plan:free"
    assert action.details["limits"][1] == {"applications_per_month": 25, "resumes": 2}


def test_hiding_a_plan_stops_new_purchases(admin, alice):
    data(send(admin, "PUT", "/plans/premium", plan_body(name="Premium", price_cents=199900, is_active=False)))
    assert "premium" not in [p["code"] for p in alice.get("/api/plans").json()["data"]["plans"]]
    resp = alice.post("/api/billing/checkout", json={"plan": "premium"}, headers=csrf_headers(alice))
    assert resp.status_code == 404


@pytest.mark.parametrize("code,body,error", [
    ("free", {"name": "Free", "price_cents": 100, "applications_per_month": 10, "resumes": 1}, "INVALID_PRICE"),
    ("free", {"name": "Free", "price_cents": 0, "applications_per_month": 10, "resumes": 1, "is_active": False},
     "CANNOT_DISABLE_FREE"),
    ("starter", plan_body(price_cents=50), "INVALID_PRICE"),
    ("gold", plan_body(), "PLAN_NOT_FOUND"),
    ("starter", plan_body(applications_per_month=-1), "VALIDATION_ERROR"),
    ("starter", plan_body(name=""), "VALIDATION_ERROR"),
])
def test_plan_validation(admin, code, body, error):
    resp = send(admin, "PUT", f"/plans/{code}", body)
    assert resp.status_code in (404, 422) and resp.json()["error"]["code"] == error


def test_price_change_creates_a_new_provider_plan(admin, app, db):
    created = []

    class Provider(NullProvider):
        name = "razorpay"

        def create_plan(self, plan):
            created.append((plan.code, plan.price_cents))
            return f"plan_new_{len(created)}"

    app.dependency_overrides[get_payment_provider] = lambda: Provider()
    data(send(admin, "PUT", "/plans/starter", plan_body(name="Starter Plus")))
    assert created == [], "no new provider plan when the price is unchanged"
    out = data(send(admin, "PUT", "/plans/starter", plan_body(price_cents=59900)))
    assert created == [("starter", 59900)] and out["provider_plan_id"] == "plan_new_1"
    db.expire_all()
    assert db.scalar(select(Plan).where(Plan.code == "starter")).price_cents == 59900
