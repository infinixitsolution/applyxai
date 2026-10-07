"""API tests for registration, login sessions, CSRF, verification, and password reset."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from backend.app.core.cookies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from backend.app.models import AuthToken, TokenPurpose, User
from backend.tests.conftest import PASSWORD, csrf_headers


def _register(api, email="alice@example.com", password=PASSWORD, **extra):
    return api.post("/api/auth/register", json={"email": email, "password": password, **extra})


def _login(api, email="alice@example.com", password=PASSWORD):
    return api.post("/api/auth/login", json={"email": email, "password": password})


def test_accounts_on_internal_domains_can_log_in_but_not_register(api, db):
    from backend.app.core.security import hash_password
    db.add(User(email="admin@applyxai.local", password_hash=hash_password(PASSWORD), is_verified=True, is_admin=True))
    db.commit()
    assert _register(api, email="someone@applyxai.local").status_code == 422
    assert _login(api, email="Admin@ApplyXAI.local").status_code == 200
    assert _login(api, email="not-an-email").status_code == 422


# ------------------------------------------------------------------ registration
def test_register_stores_hash_not_password_and_sends_verification(api, db, outbox):
    resp = _register(api, email="Alice@Example.com", first_name=" Alice ")
    assert resp.status_code == 202 and resp.json()["success"] is True
    user = db.scalars(select(User)).one()
    assert user.email == "alice@example.com" and user.first_name == "Alice"
    assert user.password_hash.startswith("$argon2id$") and PASSWORD not in user.password_hash
    assert not user.is_verified
    assert outbox.sent[-1].to == "alice@example.com" and "verify-email?token=" in outbox.sent[-1].body
    stored = db.scalars(select(AuthToken)).one()
    assert stored.token_hash != outbox.last_token()      # only the hash is stored


def test_register_existing_email_gives_identical_response(api, outbox):
    first = _register(api)
    second = _register(api, email="ALICE@example.com", password="another password 1")
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    assert "already have one" in outbox.sent[-1].body and "token=" not in outbox.sent[-1].body


def test_register_validation(api):
    assert _register(api, email="not-an-email").json()["error"]["code"] == "VALIDATION_ERROR"
    assert _register(api, password="short").status_code == 422
    assert _register(api, password="aaaaaaaaaaaa").status_code == 422
    assert _register(api, password="x" * 129).status_code == 422
    resp = _register(api, email="bob@example.com", password="bob@example.com")
    assert resp.status_code == 422 and resp.json()["error"]["code"] == "WEAK_PASSWORD"


# ------------------------------------------------------------------ verification + login
def test_cannot_log_in_before_verifying(api):
    _register(api)
    resp = _login(api)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "EMAIL_NOT_VERIFIED"


def test_verify_then_login_sets_secure_cookie_flags(api, outbox):
    _register(api)
    verify = api.post("/api/auth/verify-email", json={"token": outbox.last_token()})
    assert verify.status_code == 200 and verify.json()["data"]["user"]["is_verified"] is True

    resp = _login(api)
    assert resp.status_code == 200
    user = resp.json()["data"]["user"]
    assert user["email"] == "alice@example.com" and "password_hash" not in user
    set_cookie = "\n".join(resp.headers.get_list("set-cookie"))
    for name in (ACCESS_COOKIE, REFRESH_COOKIE):
        line = next(c for c in resp.headers.get_list("set-cookie") if c.startswith(name + "="))
        assert "HttpOnly" in line and "SameSite=lax" in line
    csrf_line = next(c for c in resp.headers.get_list("set-cookie") if c.startswith(CSRF_COOKIE + "="))
    assert "HttpOnly" not in csrf_line
    assert "Path=/api/auth" in next(c for c in set_cookie.splitlines() if c.startswith(REFRESH_COOKIE))


def test_verification_token_is_single_use(api, outbox):
    _register(api)
    token = outbox.last_token()
    assert api.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    resp = api.post("/api/auth/verify-email", json={"token": token})
    assert resp.status_code == 400 and resp.json()["error"]["code"] == "INVALID_TOKEN"


def test_expired_verification_token_is_rejected(api, db, outbox):
    _register(api)
    db.execute(update(AuthToken).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)))
    db.commit()
    assert api.post("/api/auth/verify-email", json={"token": outbox.last_token()}).status_code == 400


def test_resend_verification_replaces_old_token(api, outbox):
    _register(api)
    old = outbox.last_token()
    assert api.post("/api/auth/resend-verification", json={"email": "alice@example.com"}).status_code == 202
    new = outbox.last_token()
    assert new != old
    assert api.post("/api/auth/verify-email", json={"token": old}).status_code == 400
    assert api.post("/api/auth/verify-email", json={"token": new}).status_code == 200


def test_wrong_password_and_unknown_email_look_the_same(api, make_user):
    make_user()
    api.post("/api/auth/logout", headers=csrf_headers(api))
    wrong = _login(api, password="wrong password 1")
    unknown = _login(api, email="nobody@example.com")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_disabled_account_cannot_log_in(api, db, make_user):
    make_user()
    db.execute(update(User).values(is_active=False))
    db.commit()
    assert api.get("/api/auth/me").status_code == 401
    resp = _login(api)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "ACCOUNT_DISABLED"


# ------------------------------------------------------------------ session
def test_me_requires_login(api):
    resp = api.get("/api/auth/me")
    assert resp.status_code == 401 and resp.json()["error"]["code"] == "UNAUTHORIZED"


def test_me_returns_current_user(make_user):
    api = make_user()
    resp = api.get("/api/auth/me")
    assert resp.status_code == 200 and resp.json()["data"]["user"]["email"] == "alice@example.com"


def test_logout_requires_csrf_header(make_user):
    api = make_user()
    resp = api.post("/api/auth/logout")
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "CSRF_FAILED"
    resp = api.post("/api/auth/logout", headers={"X-CSRF-Token": "forged"})
    assert resp.status_code == 403
    assert api.get("/api/auth/me").status_code == 200          # still logged in


def test_logout_ends_session(make_user):
    api = make_user()
    refresh_cookie = api.cookies.get(REFRESH_COOKIE)
    assert api.post("/api/auth/logout", headers=csrf_headers(api)).status_code == 200
    assert api.get("/api/auth/me").status_code == 401
    api.cookies.set(REFRESH_COOKIE, refresh_cookie, path="/api/auth")
    api.cookies.set(CSRF_COOKIE, "x")
    assert api.post("/api/auth/refresh", headers={"X-CSRF-Token": "x"}).status_code == 401


def test_refresh_rotates_tokens(make_user):
    api = make_user()
    old_refresh = api.cookies.get(REFRESH_COOKIE)
    resp = api.post("/api/auth/refresh", headers=csrf_headers(api))
    assert resp.status_code == 200
    assert api.cookies.get(REFRESH_COOKIE) != old_refresh
    assert api.get("/api/auth/me").status_code == 200


def test_reused_refresh_token_revokes_every_session(api, db, make_user):
    make_user()
    stolen = api.cookies.get(REFRESH_COOKIE)
    assert api.post("/api/auth/refresh", headers=csrf_headers(api)).status_code == 200
    # Age the rotation past the two-tabs grace window, then replay the old token.
    db.execute(update(AuthToken).where(AuthToken.used_at.is_not(None))
               .values(used_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    db.commit()
    legit_access = api.cookies.get(ACCESS_COOKIE)

    api.cookies.set(REFRESH_COOKIE, stolen, path="/api/auth")
    assert api.post("/api/auth/refresh", headers=csrf_headers(api)).status_code == 401

    api.cookies.set(ACCESS_COOKIE, legit_access, path="/api")
    assert api.get("/api/auth/me").status_code == 401           # token_version bumped
    live = db.scalars(select(AuthToken).where(AuthToken.purpose == TokenPurpose.REFRESH,
                                              AuthToken.used_at.is_(None))).all()
    assert live == []


def test_logout_all_invalidates_existing_access_tokens(make_user):
    api = make_user()
    access = api.cookies.get(ACCESS_COOKIE)
    assert api.post("/api/auth/logout-all", headers=csrf_headers(api)).status_code == 200
    api.cookies.set(ACCESS_COOKIE, access, path="/api")
    assert api.get("/api/auth/me").status_code == 401


# ------------------------------------------------------------------ password reset
def test_forgot_password_unknown_email_gives_identical_response(api, make_user, outbox):
    make_user()
    sent_before = len(outbox.sent)
    known = api.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    unknown = api.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert known.status_code == unknown.status_code == 202 and known.json() == unknown.json()
    assert len(outbox.sent) == sent_before + 1


def test_password_reset_flow_ends_sessions_and_changes_password(api, make_user, outbox):
    make_user()
    old_access = api.cookies.get(ACCESS_COOKIE)
    api.post("/api/auth/forgot-password", json={"email": "alice@example.com"})
    token = outbox.last_token()
    resp = api.post("/api/auth/reset-password", json={"token": token, "new_password": "brand new passphrase"})
    assert resp.status_code == 200

    api.cookies.set(ACCESS_COOKIE, old_access, path="/api")
    assert api.get("/api/auth/me").status_code == 401           # old sessions are dead
    assert _login(api).status_code == 401                        # old password is dead
    assert _login(api, password="brand new passphrase").status_code == 200
    again = api.post("/api/auth/reset-password", json={"token": token, "new_password": "another passphrase"})
    assert again.status_code == 400                              # single use


# ------------------------------------------------------------------ rate limiting
def test_login_is_rate_limited_per_ip(api):
    codes = [_login(api, email=f"user{i}@example.com").status_code for i in range(6)]
    assert codes[:5] == [401] * 5
    assert codes[5] == 429
    blocked = _login(api)
    assert blocked.json()["error"]["code"] == "RATE_LIMITED" and "retry-after" in blocked.headers


def test_login_is_rate_limited_per_account(api, limiter):
    for _ in range(10):
        limiter.hit("10/hour", "login-email", "alice@example.com")
    assert _login(api).status_code == 429


def test_forgot_password_is_rate_limited(api):
    codes = [api.post("/api/auth/forgot-password", json={"email": "alice@example.com"}).status_code
             for _ in range(4)]
    assert codes == [202, 202, 202, 429]


def test_without_email_verification_new_accounts_log_in_straight_away(api, outbox, monkeypatch):
    from backend.app.core.config import settings
    monkeypatch.setattr(settings, "REQUIRE_EMAIL_VERIFICATION", False)
    resp = api.post("/api/auth/register", json={"email": "quick@example.com", "password": PASSWORD})
    assert resp.status_code == 202 and resp.json()["data"]["verification_required"] is False
    assert not any(e.to == "quick@example.com" and "token=" in e.body for e in outbox.sent)
    login = api.post("/api/auth/login", json={"email": "quick@example.com", "password": PASSWORD})
    assert login.status_code == 200 and login.json()["data"]["user"]["is_verified"] is True
