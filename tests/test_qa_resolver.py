from automation.qa_resolver import can_use_ai, match_human_custom, resolve_missing_answer


def test_match_human_contains():
    qs = [{"id": "1", "match": "contains", "pattern": "favorite color", "answer": "Blue"}]
    assert match_human_custom("What is your favorite color?", qs) == "Blue"
    assert match_human_custom("Other", qs) is None


def test_match_human_exact():
    qs = [{"id": "1", "match": "exact", "pattern": "Referral code", "answer": "ABC"}]
    assert match_human_custom("Referral code", qs) == "ABC"
    assert match_human_custom("referral code", qs) == "ABC"


def test_deny_blocks_ai():
    assert not can_use_ai("what is your gender", "text", {"deny_label_contains": ["gender"]})


def test_resolve_human_before_ai():
    called = []

    def fake_ai(**kwargs):
        called.append(kwargs)
        return "AI"

    from automation import qa_resolver

    qa_resolver.configure(local_answer=lambda *a, **k: fake_ai(**k))
    qs = [{"id": "1", "match": "contains", "pattern": "pet name", "answer": "Rex"}]
    ans = resolve_missing_answer(
        label_org="Pet name?",
        label_lower="pet name?",
        question_type="text",
        human_questions=qs,
        ai_policy={"deny_label_contains": []},
        use_ai=True,
    )
    assert ans == "Rex"
    assert not called
