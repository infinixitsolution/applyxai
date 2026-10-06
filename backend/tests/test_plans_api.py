from backend.app.core.plans import PLAN_LIMITS
from backend.app.models import Plan


def test_plans_are_public_and_default_to_the_catalogue(api):
    resp = api.get("/api/plans")
    assert resp.status_code == 200
    plans = resp.json()["data"]["plans"]
    assert [p["code"] for p in plans] == list(PLAN_LIMITS)
    free = plans[0]
    assert free["price_cents"] == 0 and free["limits"] == {"applications_per_month": 10, "resumes": 1}


def test_plans_table_overrides_defaults(api, db):
    db.add_all([
        Plan(code="pro", name="Pro", price_cents=79900, limits={"applications_per_month": 600}, sort_order=2),
        Plan(code="free", name="Free", price_cents=0, sort_order=1),
        Plan(code="legacy", name="Legacy", price_cents=1, is_active=False),
    ])
    db.commit()
    plans = api.get("/api/plans").json()["data"]["plans"]
    assert [p["code"] for p in plans] == ["free", "pro"]
    assert plans[1]["price_cents"] == 79900
    assert plans[1]["limits"] == {"applications_per_month": 600, "resumes": 10}
