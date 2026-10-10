from automation.company_contacts import extract_published_contacts, merge_contacts


def test_posting_email_and_phone_are_captured_without_the_applicant():
    rows = extract_published_contacts(
        "Write to hiring@acme.com or WhatsApp +91 98450 11223. Ignore jobs@linkedin.com.",
        name="Priya Shah \u00b7 Recruiter",
        link="https://www.linkedin.com/in/priya",
    )
    assert rows == [{
        "name": "Priya Shah",
        "email": "hiring@acme.com",
        "phone": "+91 98450 11223",
        "role": "Recruiter",
        "link": "https://www.linkedin.com/in/priya",
    }]


def test_hiring_team_name_is_kept_when_no_email_is_published():
    rows = extract_published_contacts("", name="Unknown")
    assert rows == []
    rows = extract_published_contacts("No contact line.", name="Amit Rao")
    assert rows[0]["name"] == "Amit Rao" and rows[0]["email"] == "" and rows[0]["phone"] == ""


def test_merge_fills_a_blank_phone_on_the_same_email():
    merged = merge_contacts(
        [{"name": "", "email": "hr@acme.com", "phone": "", "role": "", "link": ""}],
        [{"name": "Priya", "email": "hr@acme.com", "phone": "9845011223", "role": "", "link": ""}],
    )
    assert len(merged) == 1
    assert merged[0]["name"] == "Priya" and merged[0]["phone"] == "9845011223"
