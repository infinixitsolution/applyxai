"""
Default plan catalogue. The single place limits are defined in code: billing seeds these into
an empty `plans` table (`python -m backend.app.cli seed-plans`), after which the database row is
authoritative. Prices are never referenced outside this catalogue and that table.
"""

FREE_PLAN = "free"

PLAN_LIMITS: dict[str, dict] = {
    "free":    {"name": "Free",    "kind": "personal", "applications_per_month": 10,   "resumes": 1,  "price_cents": 0},
    "starter": {"name": "Starter", "kind": "personal", "applications_per_month": 100,  "resumes": 3,  "price_cents": 49900},
    "pro":     {"name": "Pro",     "kind": "personal", "applications_per_month": 500,  "resumes": 10, "price_cents": 99900},
    "premium": {"name": "Premium", "kind": "personal", "applications_per_month": 1500, "resumes": 20, "price_cents": 199900},
    # Internal / admin-grant only — not sold via checkout; complimentary grants use this code.
    "unlimited": {"name": "Unlimited", "kind": "personal", "applications_per_month": 999_999, "resumes": 999, "price_cents": 199900},
    "campus":     {"name": "Campus",     "kind": "institute", "applications_per_month": 100,  "resumes": 3,  "seats": 10, "price_cents": 49900},
    "campus_pro": {"name": "Campus Pro", "kind": "institute", "applications_per_month": 500,  "resumes": 10, "seats": 50, "price_cents": 199900},
}
