"""Institute and partner workspaces: register, approve, seats, referrals, commissions."""

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.models import (
    AssignmentStatus, CommissionStatus, Institute, InstituteAssignment, InstituteSeat, InstituteStatus,
    KycStatus, Partner, PartnerCommission, PartnerStatus, Payment, Plan, PlanKind, SeatStatus,
    Subscription, SubscriptionStatus, User,
)
from backend.tests.conftest import PASSWORD, csrf_headers


def _register(api, email, account_type="candidate", **extra):
    body = {"email": email, "password": PASSWORD, "first_name": "Pat", "last_name": "User",
            "account_type": account_type, **extra}
    return api.post("/api/auth/register", json=body)


def _verify_login(api, outbox, email):
    assert api.post("/api/auth/verify-email", json={"token": outbox.last_token(email)}).status_code == 200
    resp = api.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["user"]


def _grant_campus(db, inst_id):
    import uuid
    from backend.app.services import institute_service
    institute = db.get(Institute, uuid.UUID(str(inst_id)))
    institute_service.grant_plan(db, institute, "campus", 1)
    db.commit()


def _admin(api, db):
    db.add(User(email="admin@applyxai.local", password_hash=hash_password(PASSWORD),
                is_verified=True, is_admin=True))
    db.commit()
    client = api
    assert client.post("/api/auth/login", json={"email": "admin@applyxai.local", "password": PASSWORD}).status_code == 200
    return client


def test_register_institute_and_partner_sets_workspace(api, db, outbox):
    assert _register(api, "campus@example.com", "institute", institute_name="Acme College",
                     contact_name="Dean", agreed=True).status_code == 202
    user = _verify_login(api, outbox, "campus@example.com")
    assert user["workspace"] == "institute" and user["institute_status"] == "pending"
    me = api.get("/api/auth/me").json()["data"]["user"]
    assert me["workspace"] == "institute"
    assert api.get("/api/institute/dashboard").status_code == 200
    assert api.get("/api/partner/dashboard").status_code == 403

    api.post("/api/auth/logout", headers=csrf_headers(api))
    assert _register(api, "ally@example.com", "partner", organization="Ally Partners", agreed=True).status_code == 202
    partner_user = _verify_login(api, outbox, "ally@example.com")
    assert partner_user["workspace"] == "partner" and partner_user["partner_status"] == "pending"
    assert api.get("/api/partner/dashboard").status_code == 200
    assert api.get("/api/institute/dashboard").status_code == 403


def test_candidate_register_unchanged_and_cannot_use_institute_api(api, outbox, make_user):
    make_user()
    me = api.get("/api/auth/me").json()["data"]["user"]
    assert me["workspace"] == "app"
    assert api.get("/api/institute/students").status_code == 403


def test_admin_approves_institute_and_partner(api, db, outbox):
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    resp = admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    assert resp.status_code == 200 and resp.json()["data"]["status"] == "active"

    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    # still logged in as admin from the other client cookies? use a fresh client via same api after logout
    api.post("/api/auth/logout", headers=csrf_headers(api))
    assert api.post("/api/auth/login", json={"email": "admin@applyxai.local", "password": PASSWORD}).status_code == 200
    partners = api.get("/api/admin/partners").json()["data"]["items"]
    partner_id = partners[0]["id"]
    assert api.post(f"/api/admin/partners/{partner_id}/status", json={"status": "approved"},
                    headers=csrf_headers(api)).json()["data"]["status"] == "approved"
    assert api.post(f"/api/admin/partners/{partner_id}/kyc", json={"status": "verified"},
                    headers=csrf_headers(api)).json()["data"]["kyc_status"] == "verified"


def test_invite_requires_active_institute_and_free_seat(api, db, outbox):
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    resp = api.post("/api/institute/students/invite", json={"email": "student@example.com"},
                    headers=csrf_headers(api))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "INSTITUTE_NOT_ACTIVE"

    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    resp = api.post("/api/institute/students/invite", json={"email": "student@example.com"},
                    headers=csrf_headers(api))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "NO_SEATS"

    _grant_campus(db, inst_id)
    api.post("/api/auth/logout", headers=csrf_headers(api))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    seats = api.get("/api/institute/seats").json()["data"]["counts"]
    assert seats["available"] == 10
    invited = api.post("/api/institute/students/invite", json={"email": "student@example.com"},
                       headers=csrf_headers(api))
    assert invited.status_code == 200, invited.text
    assert invited.json()["data"]["assignment"]["status"] == "invited"


def test_accept_invite_assigns_seat_and_release_frees_it(api, db, outbox):
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    _grant_campus(db, inst_id)
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    api.post("/api/institute/students/invite", json={"email": "student@example.com"}, headers=csrf_headers(api))
    token = outbox.last_token("student@example.com")
    assignment_id = api.get("/api/institute/invitations").json()["data"]["items"][0]["id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))

    _register(api, "student@example.com")
    _verify_login(api, outbox, "student@example.com")
    preview = api.get(f"/api/invites/{token}")
    assert preview.status_code == 200 and preview.json()["data"]["email"] == "student@example.com"
    accepted = api.post(f"/api/invites/{token}/accept", headers=csrf_headers(api))
    assert accepted.status_code == 200
    assert accepted.json()["data"]["assignment"]["status"] == "active"

    usage = api.get("/api/usage").json()["data"]
    assert usage["plan"] == "campus"
    assert usage["applications"]["limit"] == 100

    api.post("/api/auth/logout", headers=csrf_headers(api))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    released = api.post(f"/api/institute/students/{assignment_id}/release", headers=csrf_headers(api))
    assert released.status_code == 200
    seats = api.get("/api/institute/seats").json()["data"]["counts"]
    assert seats["available"] == 10 and seats["assigned"] == 0


def test_partner_referral_attributes_institute(api, db, outbox):
    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    _verify_login(api, outbox, "ally@example.com")
    code = api.get("/api/partner/me").json()["data"]["referral_code"]
    api.post("/api/auth/logout", headers=csrf_headers(api))

    captured = api.get(f"/api/r/{code}")
    assert captured.status_code == 200
    assert captured.json()["data"]["referral_code"] == code

    _register(api, "campus@example.com", "institute", institute_name="Referred College", agreed=True,
              referral_code=code)
    _verify_login(api, outbox, "campus@example.com")
    inst = db.scalars(select(Institute)).one()
    partner = db.scalars(select(Partner)).one()
    assert inst.partner_id == partner.id and inst.source == "partner"


def test_partner_enroll_creates_institute(api, db, outbox):
    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    _verify_login(api, outbox, "ally@example.com")
    partner_id = api.get("/api/auth/me").json()["data"]["user"]["partner_id"]
    resp = api.post("/api/partner/institutes", json={
        "name": "Enrolled Campus", "email": "enrolled@example.com", "password": PASSWORD,
        "contact_name": "Campus Admin",
    }, headers=csrf_headers(api))
    assert resp.status_code == 403

    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/partners/{partner_id}/status", json={"status": "approved"}, headers=csrf_headers(admin))
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "ally@example.com", "password": PASSWORD})
    enrolled = api.post("/api/partner/institutes", json={
        "name": "Enrolled Campus", "email": "enrolled@example.com", "password": PASSWORD,
        "contact_name": "Campus Admin",
    }, headers=csrf_headers(api))
    assert enrolled.status_code == 200, enrolled.text
    assert enrolled.json()["data"]["name"] == "Enrolled Campus"
    assert enrolled.json()["data"]["source"] == "partner"


def test_commission_accrues_only_when_approved_and_kyc(api, db, outbox):
    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    _verify_login(api, outbox, "ally@example.com")
    partner = db.scalars(select(Partner)).one()
    api.post("/api/auth/logout", headers=csrf_headers(api))

    _register(api, "campus@example.com", "institute", institute_name="Pay College", agreed=True,
              referral_code=partner.referral_code)
    _verify_login(api, outbox, "campus@example.com")
    institute = db.scalars(select(Institute)).one()
    api.post("/api/auth/logout", headers=csrf_headers(api))

    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{institute.id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    campus = db.scalar(select(Plan).where(Plan.code == "campus"))
    if campus is None:
        from backend.app.services import billing_service
        billing_service.seed_plans(db)
        db.commit()
        campus = db.scalar(select(Plan).where(Plan.code == "campus"))
    payer = db.scalar(select(User).where(User.email == "campus@example.com"))
    sub = Subscription(user_id=payer.id, institute_id=institute.id, plan_id=campus.id, plan=campus,
                       status=SubscriptionStatus.ACTIVE, provider="razorpay")
    db.add(sub)
    db.flush()
    payment = Payment(user_id=payer.id, subscription_id=sub.id, provider="razorpay",
                      provider_payment_id="pay_test_1", amount_cents=49900, currency="INR",
                      status="captured")
    db.add(payment)
    db.flush()
    from backend.app.services import partner_service
    assert partner_service.maybe_accrue_commission(db, payment, sub) is None

    partner.status = PartnerStatus.APPROVED
    partner.kyc_status = KycStatus.VERIFIED
    db.flush()
    row = partner_service.maybe_accrue_commission(db, payment, sub)
    db.commit()
    assert row is not None and row.status == CommissionStatus.ACCRUED
    assert row.amount_cents == 9980
    assert partner_service.maybe_accrue_commission(db, payment, sub) is None


def test_admin_impersonate_writes_audit(api, db, outbox):
    from backend.app.models import AdminAction
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    resp = admin.post(f"/api/admin/institutes/{inst_id}/login-as", headers=csrf_headers(admin))
    assert resp.status_code == 200
    assert resp.json()["data"]["user"]["workspace"] == "institute"
    actions = db.scalars(select(AdminAction).where(AdminAction.action == "institute.login_as")).all()
    assert len(actions) == 1


def test_admin_institute_dashboard(api, db):
    admin = _admin(api, db)
    created = admin.post("/api/admin/institutes", json={
        "name": "Dash College", "email": "dean@dash.edu", "password": PASSWORD,
        "contact_name": "Dean Dash", "phone": "111",
    }, headers=csrf_headers(admin))
    assert created.status_code == 200, created.text
    inst_id = created.json()["data"]["id"]
    _grant_campus(db, inst_id)
    detail = admin.get(f"/api/admin/institutes/{inst_id}")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["institute"]["name"] == "Dash College"
    assert data["login"]["email"] == "dean@dash.edu"
    assert data["seats"]["counts"]["available"] == 10
    assert data["subscription"]["plan"]["code"] == "campus"
    assert data["members"][0]["email"] == "dean@dash.edu"
    assert data["students"] == []
    assert data["payments"] == []
    assert "reports" in data and "invitations" in data


def test_admin_updates_institute(api, db):
    admin = _admin(api, db)
    created = admin.post("/api/admin/institutes", json={
        "name": "Riverside Training", "email": "dean@riverside.edu", "password": PASSWORD,
        "contact_name": "Priya Dean", "phone": "111",
    }, headers=csrf_headers(admin))
    inst_id = created.json()["data"]["id"]
    updated = admin.put(f"/api/admin/institutes/{inst_id}", json={
        "name": "Harbor Training", "contact_name": "Priya Rao", "phone": "999",
    }, headers=csrf_headers(admin))
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["name"] == "Harbor Training"
    assert data["contact_name"] == "Priya Rao"
    assert data["phone"] == "999"


def test_admin_creates_institute(api, db):
    from backend.app.models import AdminAction
    admin = _admin(api, db)
    resp = admin.post("/api/admin/institutes", json={
        "name": "Admin College", "email": "dean@admin.edu", "password": PASSWORD,
        "contact_name": "Dean Admin", "phone": "999",
    }, headers=csrf_headers(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["name"] == "Admin College" and data["status"] == "active" and data["source"] == "admin"
    assert data["email"] == "dean@admin.edu"
    taken = admin.post("/api/admin/institutes", json={
        "name": "Other", "email": "dean@admin.edu", "password": PASSWORD,
    }, headers=csrf_headers(admin))
    assert taken.status_code == 409
    actions = db.scalars(select(AdminAction).where(AdminAction.action == "institute.create")).all()
    assert len(actions) == 1
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    login = api.post("/api/auth/login", json={"email": "dean@admin.edu", "password": PASSWORD})
    assert login.status_code == 200
    user = login.json()["data"]["user"]
    assert user["workspace"] == "institute" and user["institute_status"] == "active"


def test_admin_partner_dashboard(api, db):
    admin = _admin(api, db)
    created = admin.post("/api/admin/partners", json={
        "organization": "Dash Partners", "email": "ally@dash.edu", "password": PASSWORD,
        "contact_name": "Alex Dash", "phone": "222",
    }, headers=csrf_headers(admin))
    assert created.status_code == 200, created.text
    partner_id = created.json()["data"]["id"]
    detail = admin.get(f"/api/admin/partners/{partner_id}")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["partner"]["organization"] == "Dash Partners"
    assert data["login"]["email"] == "ally@dash.edu"
    assert data["institutes"] == 0
    assert data["institute_list"] == []
    assert data["commissions"] == []
    assert data["payouts"] == []
    assert data["referral_path"].startswith("/r/")
    assert "reports" in data and "campaigns" in data


def test_admin_updates_partner(api, db):
    admin = _admin(api, db)
    created = admin.post("/api/admin/partners", json={
        "organization": "West Coast Referral", "email": "west@admin.edu", "password": PASSWORD,
        "contact_name": "Alex West", "phone": "555",
    }, headers=csrf_headers(admin))
    partner_id = created.json()["data"]["id"]
    updated = admin.put(f"/api/admin/partners/{partner_id}", json={
        "organization": "Pacific Referral", "contact_name": "Alex Pacific", "phone": "999",
    }, headers=csrf_headers(admin))
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["organization"] == "Pacific Referral"
    assert data["contact_name"] == "Alex Pacific"
    assert data["phone"] == "999"


def test_admin_creates_partner(api, db):
    from backend.app.models import AdminAction
    admin = _admin(api, db)
    resp = admin.post("/api/admin/partners", json={
        "organization": "Admin Partners", "email": "ally@admin.edu", "password": PASSWORD,
        "contact_name": "Alex Ally", "phone": "888",
    }, headers=csrf_headers(admin))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["organization"] == "Admin Partners" and data["status"] == "approved"
    assert data["kyc_status"] == "not_required" and data["referral_code"]
    taken = admin.post("/api/admin/partners", json={
        "organization": "Other", "email": "ally@admin.edu", "password": PASSWORD,
    }, headers=csrf_headers(admin))
    assert taken.status_code == 409
    actions = db.scalars(select(AdminAction).where(AdminAction.action == "partner.create")).all()
    assert len(actions) == 1
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    login = api.post("/api/auth/login", json={"email": "ally@admin.edu", "password": PASSWORD})
    assert login.status_code == 200
    user = login.json()["data"]["user"]
    assert user["workspace"] == "partner" and user["partner_status"] == "approved"
