"""Unit tests: password hashing, access tokens, opaque tokens, rate limiting."""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from backend.app.core import security
from backend.app.core.errors import AppError
from backend.app.core.rate_limit import RateLimiter


def test_passwords_are_hashed_with_argon2id_and_salted():
    first, second = security.hash_password("s3cret-pass"), security.hash_password("s3cret-pass")
    assert first.startswith("$argon2id$")
    assert first != second
    assert "s3cret-pass" not in first


def test_verify_password():
    hashed = security.hash_password("s3cret-pass")
    assert security.verify_password("s3cret-pass", hashed)
    assert not security.verify_password("wrong-pass", hashed)
    assert not security.verify_password("s3cret-pass", "not-a-hash")


def test_opaque_tokens_are_random_and_only_hashes_are_comparable():
    a, b = security.generate_token(), security.generate_token()
    assert a != b and len(a) >= 40
    assert security.hash_token(a) == security.hash_token(a)
    assert security.hash_token(a) != a and len(security.hash_token(a)) == 64


def test_access_token_roundtrip():
    uid = uuid.uuid4()
    claims = security.decode_access_token(security.create_access_token(uid, 3))
    assert claims["sub"] == str(uid) and claims["ver"] == 3 and claims["type"] == "access"


def test_tampered_or_garbage_access_tokens_are_rejected():
    token = security.create_access_token(uuid.uuid4(), 0)
    head, body, sig = token.split(".")
    assert security.decode_access_token(f"{head}.{body}.{sig[::-1]}") is None
    assert security.decode_access_token("garbage") is None
    assert security.decode_access_token("") is None


def _forge(payload, secret=None):
    return jwt.encode(payload, secret or security._jwt_secret(), algorithm="HS256")


def test_expired_access_token_is_rejected():
    now = datetime.now(timezone.utc)
    token = _forge({"sub": str(uuid.uuid4()), "ver": 0, "type": "access", "aud": "applyxai-api",
                    "iat": now - timedelta(hours=1), "exp": now - timedelta(minutes=1)})
    assert security.decode_access_token(token) is None


def test_token_signed_with_another_secret_is_rejected():
    now = datetime.now(timezone.utc)
    token = _forge({"sub": str(uuid.uuid4()), "ver": 0, "type": "access", "aud": "applyxai-api",
                    "iat": now, "exp": now + timedelta(minutes=5)}, secret="attacker-secret-" * 4)
    assert security.decode_access_token(token) is None


def test_alg_none_is_rejected():
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": str(uuid.uuid4()), "ver": 0, "type": "access", "aud": "applyxai-api",
                        "iat": now, "exp": now + timedelta(minutes=5)}, key=None, algorithm="none")
    assert security.decode_access_token(token) is None


def test_rate_limiter_blocks_after_limit_and_is_per_key():
    limiter = RateLimiter("memory://")
    for _ in range(3):
        limiter.hit("3/minute", "login", "1.2.3.4")
    with pytest.raises(AppError) as err:
        limiter.hit("3/minute", "login", "1.2.3.4")
    assert err.value.status_code == 429 and int(err.value.headers["Retry-After"]) >= 1
    limiter.hit("3/minute", "login", "5.6.7.8")
