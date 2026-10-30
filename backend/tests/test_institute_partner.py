"""Institute and partner workspaces: register, approve, seats, referrals, commissions."""

from sqlalchemy import select

from backend.app.core.security import hash_password
from backend.app.models import (
    AssignmentStatus, CommissionStatus, Institute, InstituteAssignment, InstituteSeat, InstituteStatus,
    KycStatus, Partner, PartnerCommission, PartnerCommissionMode, PartnerStatus, Payment, Plan, PlanKind, SeatStatus,
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
    blocked = api.post(
        f"/api/admin/partners/{partner_id}/status",
        json={"status": "approved"},
        headers=csrf_headers(api),
    )
    assert blocked.status_code == 409 and blocked.json()["error"]["code"] == "KYC_REQUIRED"
    assert api.post(f"/api/admin/partners/{partner_id}/kyc", json={"status": "verified"},
                    headers=csrf_headers(api)).json()["data"]["kyc_status"] == "verified"
    assert api.post(f"/api/admin/partners/{partner_id}/status", json={"status": "approved"},
                    headers=csrf_headers(api)).json()["data"]["status"] == "approved"


def test_partner_kyc_file_upload_and_admin_download(api, db, outbox):
    _register(api, "kycdocs@example.com", "partner", organization="KYC Files", agreed=True)
    _verify_login(api, outbox, "kycdocs@example.com")
    uploaded = api.post(
        "/api/partner/kyc",
        files={"file": ("pan.pdf", b"%PDF-1.4 kyc", "application/pdf")},
        data={"note": "PAN card"},
        headers=csrf_headers(api),
    )
    assert uploaded.status_code == 200, uploaded.text
    docs = uploaded.json()["data"]["kyc_documents"]
    assert len(docs) == 1
    assert docs[0]["filename"] == "pan.pdf"
    assert docs[0]["note"] == "PAN card"
    assert docs[0]["id"]
    assert "storage_path" not in docs[0]
    doc_id = docs[0]["id"]
    own = api.get(f"/api/partner/kyc/{doc_id}/file")
    assert own.status_code == 200
    assert own.content.startswith(b"%PDF-1.4")
    reject = api.post(
        "/api/partner/kyc",
        files={"file": ("notes.exe", b"MZ not a document", "application/octet-stream")},
        headers=csrf_headers(api),
    )
    assert reject.status_code == 422

    partner_id = api.get("/api/partner/me").json()["data"]["id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin_file = admin.get(f"/api/admin/partners/{partner_id}/kyc/{doc_id}/file")
    assert admin_file.status_code == 200
    assert admin_file.content.startswith(b"%PDF-1.4")


def test_invite_requires_active_institute_and_free_seat(api, db, outbox):
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    student = {"name": "Sam Student", "phone": "9876543210", "email": "student@example.com"}
    resp = api.post("/api/institute/students/invite", json=student, headers=csrf_headers(api))
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "INSTITUTE_NOT_ACTIVE"

    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    resp = api.post("/api/institute/students/invite", json=student, headers=csrf_headers(api))
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "NO_SEATS"

    _grant_campus(db, inst_id)
    api.post("/api/auth/logout", headers=csrf_headers(api))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    seats = api.get("/api/institute/seats").json()["data"]["counts"]
    assert seats["available"] == 10
    invited = api.post("/api/institute/students/invite", json=student, headers=csrf_headers(api))
    assert invited.status_code == 200, invited.text
    assert invited.json()["data"]["assignment"]["status"] == "active"
    assert any(e.to == "student@example.com" and "Password:" in e.body for e in outbox.sent)
    listed = api.get("/api/institute/seats").json()["data"]["items"]
    assert sum(1 for s in listed if s["status"] == "assigned") == 1
    assert any(s.get("assignment") and s["assignment"]["candidate_email"] == "student@example.com" for s in listed)


def test_dashboard_sums_jobs_across_active_students(api, db, outbox):
    import uuid as uuid_lib
    from backend.app.models import Application, ApplicationStatus, Job

    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    _grant_campus(db, inst_id)
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    first = api.post("/api/institute/students/invite", json={
        "name": "Sam Student", "phone": "9876543210", "email": "sam@example.com",
    }, headers=csrf_headers(api))
    second = api.post("/api/institute/students/invite", json={
        "name": "Riley Student", "phone": "9876543211", "email": "riley@example.com",
    }, headers=csrf_headers(api))
    assert first.status_code == 200 and second.status_code == 200, first.text + second.text
    sam = uuid_lib.UUID(first.json()["data"]["assignment"]["student_user_id"])
    riley = uuid_lib.UUID(second.json()["data"]["assignment"]["student_user_id"])
    outsider = User(email="outsider@example.com", password_hash=hash_password(PASSWORD), is_verified=True)
    db.add(outsider)
    jobs = [Job(external_id=str(i), title=f"Role {i}", company="Acme") for i in range(6)]
    db.add_all(jobs)
    db.commit()
    db.add_all([
        Application(user_id=sam, job_id=jobs[0].id, status=ApplicationStatus.APPLIED),
        Application(user_id=sam, job_id=jobs[1].id, status=ApplicationStatus.SKIPPED),
        Application(user_id=riley, job_id=jobs[2].id, status=ApplicationStatus.APPLIED),
        Application(user_id=riley, job_id=jobs[3].id, status=ApplicationStatus.FAILED),
        Application(user_id=riley, job_id=jobs[4].id, status=ApplicationStatus.DISCOVERED),
        Application(user_id=outsider.id, job_id=jobs[5].id, status=ApplicationStatus.APPLIED),
    ])
    db.commit()
    dash = api.get("/api/institute/dashboard").json()["data"]["activity"]
    assert dash["searched"] == 5
    assert dash["applied"] == 2
    assert dash["skipped"] == 1
    assert dash["failed"] == 1
    assert dash["success_rate"] == 0.6667
    listed = {row["candidate_email"]: row for row in api.get("/api/institute/students").json()["data"]["items"]}
    assert listed["sam@example.com"]["activity"]["applied"] == 1
    assert listed["sam@example.com"]["activity"]["skipped"] == 1
    assert listed["riley@example.com"]["activity"]["applied"] == 1
    assert listed["riley@example.com"]["activity"]["failed"] == 1
    assert listed["riley@example.com"]["activity"]["searched"] == 3


def test_student_detail_returns_profile_and_activity(api, db, outbox):
    import uuid as uuid_lib
    from backend.app.models import Application, ApplicationStatus, Job, UserProfile

    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    _grant_campus(db, inst_id)
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    added = api.post("/api/institute/students/invite", json={
        "name": "Sam Student", "phone": "9876543210", "email": "sam@example.com",
    }, headers=csrf_headers(api))
    assert added.status_code == 200, added.text
    assignment = added.json()["data"]["assignment"]
    user_id = uuid_lib.UUID(assignment["student_user_id"])
    job = Job(external_id="detail-1", title="Backend Engineer", company="Acme", location="Bengaluru")
    db.add(job)
    db.commit()
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
    profile.headline = "Python developer"
    profile.current_title = "Trainee Engineer"
    profile.current_company = "Acme Labs"
    profile.skills = ["Python", "SQL"]
    db.add(Application(user_id=user_id, job_id=job.id, status=ApplicationStatus.APPLIED))
    db.commit()

    missing = api.get("/api/institute/students/00000000-0000-0000-0000-000000000001")
    assert missing.status_code == 404

    detail = api.get(f"/api/institute/students/{assignment['id']}")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert data["assignment"]["id"] == assignment["id"]
    assert data["user"]["email"] == "sam@example.com"
    assert data["activity"]["searched"] == 1
    assert data["activity"]["applied"] == 1
    assert data["candidate"]["profile"]["headline"] == "Python developer"
    assert data["candidate"]["profile"]["skills"] == ["Python", "SQL"]
    assert data["candidate"]["recent_applications"][0]["title"] == "Backend Engineer"


def test_add_student_activates_seat_and_release_frees_it(api, db, outbox):
    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    _grant_campus(db, inst_id)
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    added = api.post("/api/institute/students/invite", json={
        "name": "Sam Student", "phone": "9876543210", "email": "student@example.com",
    }, headers=csrf_headers(api))
    assert added.status_code == 200, added.text
    assignment = added.json()["data"]["assignment"]
    assert assignment["status"] == "active"
    assert assignment["candidate_name"] == "Sam Student"
    assert assignment["candidate_phone"] == "9876543210"
    assignment_id = assignment["id"]
    cred_mail = next(e for e in outbox.sent if e.to == "student@example.com" and "Password:" in e.body)
    import re
    password = re.search(r"Password:\s*(\S+)", cred_mail.body).group(1)
    api.post("/api/auth/logout", headers=csrf_headers(api))

    login = api.post("/api/auth/login", json={"email": "student@example.com", "password": password})
    assert login.status_code == 200, login.text
    me = api.get("/api/auth/me").json()["data"]["user"]
    assert me["institute_managed"] is True
    assert me["institute_name"] == "Acme College"

    usage = api.get("/api/usage").json()["data"]
    assert usage["plan"] == "campus"
    assert usage["applications"]["limit"] == 100

    billing = api.get("/api/billing").json()["data"]
    assert billing["managed_by_institute"] is True
    assert billing["checkout_available"] is False
    blocked = api.post("/api/billing/checkout", json={"plan": "starter"}, headers=csrf_headers(api))
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "BILLING_MANAGED_BY_INSTITUTE"

    # Release via service (same client is rate-limited on login) while student session stays open.
    import uuid
    from backend.app.services import institute_service
    from backend.app.services.email_service import institute_student_released_email
    institute = db.get(Institute, uuid.UUID(str(inst_id)))
    row, notify_email = institute_service.release_assignment(db, institute, uuid.UUID(assignment_id))
    db.commit()
    assert row.status == AssignmentStatus.RELEASED and notify_email == "student@example.com"
    outbox.send(institute_student_released_email(notify_email, institute.name, db))
    assert any(e.to == "student@example.com" and "campus package ended" in e.subject.lower() for e in outbox.sent)

    me2 = api.get("/api/auth/me").json()["data"]["user"]
    assert me2["institute_managed"] is False
    billing2 = api.get("/api/billing").json()["data"]
    assert billing2["managed_by_institute"] is False
    usage2 = api.get("/api/usage").json()["data"]
    assert usage2["plan"] != "campus"
    seats = institute_service.seat_counts(db, institute.id)
    assert seats["available"] == 10 and seats["assigned"] == 0


def test_add_existing_candidate_keeps_password(api, db, outbox):
    _register(api, "student@example.com")
    _verify_login(api, outbox, "student@example.com")
    api.post("/api/auth/logout", headers=csrf_headers(api))

    _register(api, "campus@example.com", "institute", institute_name="Acme College", agreed=True)
    _verify_login(api, outbox, "campus@example.com")
    inst_id = api.get("/api/auth/me").json()["data"]["user"]["institute_id"]
    api.post("/api/auth/logout", headers=csrf_headers(api))
    admin = _admin(api, db)
    admin.post(f"/api/admin/institutes/{inst_id}/status", json={"status": "active"}, headers=csrf_headers(admin))
    _grant_campus(db, inst_id)
    admin.post("/api/auth/logout", headers=csrf_headers(admin))
    api.post("/api/auth/login", json={"email": "campus@example.com", "password": PASSWORD})
    before = len(outbox.sent)
    added = api.post("/api/institute/students/invite", json={
        "name": "Sam Student", "phone": "9876543210", "email": "student@example.com",
    }, headers=csrf_headers(api))
    assert added.status_code == 200
    assert added.json()["data"]["assignment"]["status"] == "active"
    new_mail = [e for e in outbox.sent[before:] if e.to == "student@example.com"]
    assert new_mail and "Password:" not in new_mail[-1].body
    assert "enrolled" in new_mail[-1].subject.lower() or "campus" in new_mail[-1].body.lower()
    api.post("/api/auth/logout", headers=csrf_headers(api))
    assert api.post("/api/auth/login", json={"email": "student@example.com", "password": PASSWORD}).status_code == 200


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
    admin.post(f"/api/admin/partners/{partner_id}/kyc", json={"status": "verified"}, headers=csrf_headers(admin))
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


def test_commission_flat_per_payment(api, db):
    from backend.app.services import partner_service

    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    partner = db.scalars(select(Partner)).one()
    partner.status = PartnerStatus.APPROVED
    partner.kyc_status = KycStatus.VERIFIED
    partner.commission_mode = PartnerCommissionMode.FLAT_PAYMENT
    partner.commission_flat_cents = 50000
    db.flush()

    institute = Institute(name="Flat Pay U", email="flat@example.com", status=InstituteStatus.ACTIVE, partner_id=partner.id, source="referral")
    db.add(institute)
    db.flush()
    campus = db.scalar(select(Plan).where(Plan.code == "campus"))
    if campus is None:
        from backend.app.services import billing_service
        billing_service.seed_plans(db)
        db.commit()
        campus = db.scalar(select(Plan).where(Plan.code == "campus"))
    payer = db.scalar(select(User).where(User.email == "ally@example.com"))
    sub = Subscription(user_id=payer.id, institute_id=institute.id, plan_id=campus.id, plan=campus,
                       status=SubscriptionStatus.ACTIVE, provider="razorpay")
    db.add(sub)
    db.flush()
    payment = Payment(user_id=payer.id, subscription_id=sub.id, provider="razorpay",
                      provider_payment_id="pay_flat_1", amount_cents=49900, currency="INR", status="captured")
    db.add(payment)
    db.flush()
    row = partner_service.maybe_accrue_commission(db, payment, sub)
    assert row is not None and row.amount_cents == 50000


def test_commission_flat_per_candidate(api, db):
    from backend.app.services import partner_service

    _register(api, "ally@example.com", "partner", organization="Ally", agreed=True)
    partner = db.scalars(select(Partner)).one()
    partner.status = PartnerStatus.APPROVED
    partner.kyc_status = KycStatus.VERIFIED
    partner.commission_mode = PartnerCommissionMode.FLAT_CANDIDATE
    partner.commission_flat_cents = 25000
    db.flush()

    institute = Institute(name="Flat Cand U", email="cand@example.com", status=InstituteStatus.ACTIVE, partner_id=partner.id, source="referral")
    db.add(institute)
    db.flush()
    assignment = InstituteAssignment(
        institute_id=institute.id,
        candidate_email="student@example.com",
        status=AssignmentStatus.ACTIVE,
    )
    db.add(assignment)
    db.flush()
    row = partner_service.maybe_accrue_candidate_commission(db, assignment)
    assert row is not None and row.amount_cents == 25000
    assert partner_service.maybe_accrue_candidate_commission(db, assignment) is None


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
        "organization": "Pacific Referral",
        "contact_name": "Alex Pacific",
        "phone": "999",
        "commission_mode": "percent_payment",
        "commission_bps": 2000,
        "commission_flat_cents": 0,
        "status": "approved",
        "kyc_status": "not_required",
        "gstin": "29ABCDE1234F1Z5",
        "pan_number": "ABCDE1234F",
        "payout_account": "1234567890",
        "payout_ifsc": "HDFC0001234",
        "email": "pacific@admin.edu",
    }, headers=csrf_headers(admin))
    assert updated.status_code == 200, updated.text
    data = updated.json()["data"]
    assert data["organization"] == "Pacific Referral"
    assert data["contact_name"] == "Alex Pacific"
    assert data["phone"] == "999"
    assert data["gstin"] == "29ABCDE1234F1Z5"
    assert data["pan_number"] == "ABCDE1234F"
    assert data["payout_account"] == "1234567890"
    assert data["payout_ifsc"] == "HDFC0001234"
    detail = admin.get(f"/api/admin/partners/{partner_id}")
    assert detail.json()["data"]["login"]["email"] == "pacific@admin.edu"


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


def test_admin_cannot_approve_payout_without_kyc(api, db):
    import uuid

    from backend.app.models import PartnerPayout, PayoutStatus

    admin = _admin(api, db)
    created = admin.post("/api/admin/partners", json={
        "organization": "Payout KYC Test", "email": "payoutkyc@admin.edu", "password": PASSWORD,
    }, headers=csrf_headers(admin))
    partner_id = created.json()["data"]["id"]
    admin.put(f"/api/admin/partners/{partner_id}", json={
        "organization": "Payout KYC Test",
        "commission_mode": "percent_payment",
        "commission_bps": 1000,
        "commission_flat_cents": 0,
        "status": "approved",
        "kyc_status": "pending",
    }, headers=csrf_headers(admin))
    partner = db.get(Partner, uuid.UUID(str(partner_id)))
    row = PartnerPayout(partner_id=partner.id, amount_cents=5000, currency="INR", status=PayoutStatus.REQUESTED)
    db.add(row)
    db.commit()
    blocked = admin.post(
        f"/api/admin/payouts/{row.id}/status",
        json={"status": "approved"},
        headers=csrf_headers(admin),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "KYC_REQUIRED"
