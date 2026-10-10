"""Behavior parameter catalog."""

from backend.app.services.mock_interview_behavior_parameters import (
    BEHAVIOR_PARAMETERS,
    conduct_issues_from_behavior,
    normalize_behavior_scores,
)


def test_catalog_has_55_parameters():
    assert len(BEHAVIOR_PARAMETERS) == 55
    assert {p.id for p in BEHAVIOR_PARAMETERS} == set(range(1, 56))


def test_normalize_fills_missing_and_detects_smoking():
    raw = [{"id": 26, "status": "concern", "detected": True, "score": 12, "notes": "Cigarette in frame 3."}]
    scores = normalize_behavior_scores(raw)
    assert len(scores) == 55
    smoking = next(r for r in scores if r["id"] == 26)
    assert smoking["detected"] is True
    assert smoking["score"] == 12
    assert "smoking" in conduct_issues_from_behavior(scores)
