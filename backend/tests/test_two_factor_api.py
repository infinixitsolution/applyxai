"""TOTP two-factor authentication API."""

import pyotp

from backend.tests.conftest import PASSWORD, csrf_headers


def _register_verify_login(api, outbox, email="enable2fa@example.com"):
    api.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    api.post("/api/auth/verify-email", json={"token": outbox.last_token()})
    resp = api.post("/api/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 200 and resp.json()["data"].get("user")


def test_totp_login_challenge_and_complete(api, outbox):
    _register_verify_login(api, outbox)
    begin = api.post("/api/auth/2fa/setup", headers=csrf_headers(api))
    assert begin.status_code == 200
    secret = begin.json()["data"]["secret"]
    en = api.post("/api/auth/2fa/enable", json={"code": pyotp.TOTP(secret).now()}, headers=csrf_headers(api))
    assert en.status_code == 200
    api.post("/api/auth/logout", headers=csrf_headers(api))
    second = api.post("/api/auth/login", json={"email": "enable2fa@example.com", "password": PASSWORD})
    assert second.json()["data"]["requires_2fa"] is True
    challenge = second.json()["data"]["challenge_token"]
    bad = api.post("/api/auth/login/2fa", json={"challenge_token": challenge, "code": "000000"})
    assert bad.status_code == 401
    good = api.post("/api/auth/login/2fa", json={"challenge_token": challenge, "code": pyotp.TOTP(secret).now()})
    assert good.status_code == 200
    assert good.json()["data"]["user"]["totp_enabled"] is True
