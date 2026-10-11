"""
Default plan catalogue. The single place limits are defined in code: billing seeds these into
an empty `plans` table (`python -m backend.app.cli seed-plans`), after which the database row is
authoritative. Prices are never referenced outside this catalogue and that table.
"""

FREE_PLAN = "free"

# "resumes" is the number of resumes a user may create per calendar month (uploads, style copies, and
# AI-tailored versions made on the website). Desktop auto-apply copies are not counted.
RESUMES_UNLIMITED = 999_999
MOCK_INTERVIEWS_UNLIMITED = 999_999

PLAN_LIMIT_KEYS = ("applications_per_month", "resumes", "mock_interviews_per_month", "seats")

# Not listed on /api/plans and not available via self-service checkout (admin grants only).
INTERNAL_PLAN_CODES: frozenset[str] = frozenset({"unlimited"})


def is_public_checkout_plan(code: str) -> bool:
    return code not in INTERNAL_PLAN_CODES


PLAN_LIMITS: dict[str, dict] = {
    "free": {
        "name": "Free",
        "kind": "personal",
        "applications_per_month": 10,
        "resumes": 3,
        "mock_interviews_per_month": 3,
        "price_cents": 0,
    },
    "starter": {
        "name": "Starter",
        "kind": "personal",
        "applications_per_month": 100,
        "resumes": 20,
        "mock_interviews_per_month": 10,
        "price_cents": 49900,
    },
    "pro": {
        "name": "Pro",
        "kind": "personal",
        "applications_per_month": 500,
        "resumes": 60,
        "mock_interviews_per_month": 30,
        "price_cents": 99900,
    },
    "premium": {
        "name": "Premium",
        "kind": "personal",
        "applications_per_month": 1500,
        "resumes": 150,
        "mock_interviews_per_month": 100,
        "price_cents": 199900,
    },
    # Internal / admin-grant only — not sold via checkout; complimentary grants use this code.
    "unlimited": {
        "name": "Unlimited",
        "kind": "personal",
        "applications_per_month": 999_999,
        "resumes": RESUMES_UNLIMITED,
        "mock_interviews_per_month": MOCK_INTERVIEWS_UNLIMITED,
        "price_cents": 0,
    },
    "campus": {
        "name": "Campus",
        "kind": "institute",
        "applications_per_month": 100,
        "resumes": 20,
        "mock_interviews_per_month": 10,
        "seats": 10,
        "price_cents": 49900,
    },
    "campus_pro": {
        "name": "Campus Pro",
        "kind": "institute",
        "applications_per_month": 500,
        "resumes": 60,
        "mock_interviews_per_month": 30,
        "seats": 50,
        "price_cents": 199900,
    },
}
