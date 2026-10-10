"""Mock interview feedback calibration."""

from backend.app.models.enums import MockInterviewMessageRole, MockInterviewSessionStatus
from backend.app.services.mock_interview_feedback import build_no_answer_feedback, calibrate_feedback
from backend.app.services.mock_interview_service import merge_regenerated_feedback


class _Msg:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class _Session:
    def __init__(self, messages):
        self.messages = messages
        self.status = MockInterviewSessionStatus.ACTIVE


def test_no_candidate_answers_zero_scores():
    session = _Session(
        [
            _Msg(MockInterviewMessageRole.INTERVIEWER, "Tell me about your AI experience."),
        ]
    )
    fb = build_no_answer_feedback(session)
    assert fb["overall_score"] == 0
    assert all(d["score"] == 0 for d in fb["dimensions"])
    assert fb["dimensions"][1]["key"] == "technical"
    assert fb["dimensions"][1]["score"] == 0


def test_regenerate_merge_keeps_prior_presentation():
    prior = {
        "overall_score": 70,
        "presentation": {
            "available": True,
            "presentability_summary": "Good eye contact.",
            "behavioral_parameters": [{"id": 1, "detected": False}],
        },
        "analysis_meta": {"presentation_frames_analyzed": 3, "behavior_concerns": 0},
    }
    fresh = {
        "overall_score": 55,
        "presentation": {"available": False, "reason": "no_frames"},
        "dimensions": [],
    }
    out = merge_regenerated_feedback(prior, fresh)
    assert out["presentation"]["available"] is True
    assert out["presentation"]["presentability_summary"] == "Good eye contact."
    assert out["overall_score"] == 55
    assert out["analysis_meta"]["presentation_frames_analyzed"] == 3


def test_ai_inflated_technical_capped_without_evidence():
    session = _Session(
        [
            _Msg(MockInterviewMessageRole.INTERVIEWER, "Describe your role."),
            _Msg(MockInterviewMessageRole.CANDIDATE, "Yes hello thanks."),
        ]
    )
    inflated = {
        "overall_score": 35,
        "knowledge_summary": "Limited.",
        "dimensions": [
            {"key": "communication", "label": "Communication", "score": 40, "notes": "x"},
            {"key": "technical", "label": "Technical depth", "score": 30, "notes": "x"},
            {"key": "behavioral", "label": "Behavioral / STAR", "score": 20, "notes": "x"},
            {"key": "role_fit", "label": "Role fit", "score": 30, "notes": "x"},
        ],
        "question_breakdown": [
            {"question": "Describe your role.", "answer_quality": "missing", "notes": "No real answer."}
        ],
    }
    fb = calibrate_feedback(session, inflated)
    assert fb["overall_score"] <= 10
    tech = next(d for d in fb["dimensions"] if d["key"] == "technical")
    assert tech["score"] <= 8
