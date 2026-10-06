"""
Default plan catalogue. The single place limits are defined in code: Phase 9 seeds these into
the `plans` table, after which the database row (admin-editable) is authoritative. Prices are
placeholders and are never referenced outside this catalogue.
"""

FREE_PLAN = "free"

PLAN_LIMITS: dict[str, dict] = {
    "free":    {"name": "Free",    "applications_per_month": 10,   "resumes": 1,  "price_cents": 0},
    "starter": {"name": "Starter", "applications_per_month": 100,  "resumes": 3,  "price_cents": 49900},
    "pro":     {"name": "Pro",     "applications_per_month": 500,  "resumes": 10, "price_cents": 99900},
    "premium": {"name": "Premium", "applications_per_month": 1500, "resumes": 20, "price_cents": 199900},
}
