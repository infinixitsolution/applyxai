"""Presentation / on-camera conduct merge."""

from backend.app.services.mock_interview_presentation import merge_presentation_conduct_into_feedback


def test_smoking_issue_lowers_etiquette_and_adds_improvement():
    feedback = {
        "knowledge_summary": "Good technical depth.",
        "improvements": ["Add metrics to stories."],
        "rubric_scores": [
            {"id": 74, "key": "professional_etiquette", "label": "Professional etiquette", "score": 72, "notes": "Polite."},
        ],
        "rubric_overall": 72,
    }
    presentation = {
        "available": True,
        "overall_score": 68,
        "professional_conduct": {
            "score": 18,
            "issues": ["smoking"],
            "notes": "Cigarette visible in two snapshots.",
        },
    }
    feedback["presentation"] = presentation
    out = merge_presentation_conduct_into_feedback(feedback, presentation)
    assert out["presentation"]["overall_score"] == 18
    etiquette = next(r for r in out["rubric_scores"] if r["id"] == 74)
    assert etiquette["score"] == 18
    assert "smoking" in etiquette["notes"].lower() or "Smoking" in etiquette["notes"]
    assert any("Smoking" in imp for imp in out["improvements"])
    assert "conduct" in out["knowledge_summary"].lower()
