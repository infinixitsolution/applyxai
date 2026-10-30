"""Offline checks against labeled outreach_eval fixtures (no network)."""

import json
from pathlib import Path

from backend.app.services.outreach.contact_extract import extract_contacts_from_content
from backend.app.services.outreach.evidence import apply_evidence_gate
from backend.app.services.outreach.identity import discovery_dedupe_key

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "outreach_eval" / "labeled_institutes.json"


def _samples():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return data["samples"]


def test_eval_directory_samples_have_distinct_dedupe_keys():
    samples = {s["id"]: s for s in _samples()}
    a = samples["distinct-directory-a"]
    b = samples["distinct-directory-b"]
    assert discovery_dedupe_key(a["discovery_url"], a["expected_name"]) != discovery_dedupe_key(
        b["discovery_url"], b["expected_name"]
    )


def test_eval_contact_extraction_precision_on_labeled_text():
    samples = _samples()
    checked = 0
    correct = 0
    for sample in samples:
        text = sample.get("source_text") or ""
        if "expected_emails" not in sample and "expected_name" not in sample:
            continue
        url = sample.get("discovery_url") or "https://fixture.local/page"
        candidates = extract_contacts_from_content(text, source_url=url)
        emails = [c.value for c in candidates if c.field == "emails" and c.status == "syntax_valid"]
        expected = sample.get("expected_emails")
        if expected is not None:
            checked += 1
            if emails == expected:
                correct += 1
    assert checked >= 2
    assert correct / checked >= 0.5

def test_eval_ai_fabrication_blocked():
    sample = next(s for s in _samples() if s["id"] == "no-contacts")
    gated = apply_evidence_gate(
        {"name": "Fake", "emails": ["invented@fake.com"], "phones": ["+919999999999"], "website": ""},
        source_blob=sample["source_text"],
        deterministic=extract_contacts_from_content(sample["source_text"], source_url="https://delta.example"),
        fallback_name="Delta",
        discovery_url="https://delta.example",
    )
    assert gated["emails"] == []
    assert gated["phones"] == []
