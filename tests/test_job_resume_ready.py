"""The apply loop waits until a resume file is fully written before Easy Apply starts."""

from automation.job_resume import wait_until_file_ready


def test_wait_until_file_ready_accepts_a_finished_file(tmp_path):
    path = tmp_path / "resume.docx"
    path.write_bytes(b"PK\x03\x04hello")
    assert wait_until_file_ready(str(path), timeout=2, poll=0.05) is True


def test_wait_until_file_ready_rejects_a_missing_file(tmp_path):
    missing = tmp_path / "missing.docx"
    assert wait_until_file_ready(str(missing), timeout=0.3, poll=0.05) is False


def test_wait_until_file_ready_rejects_an_empty_file(tmp_path):
    path = tmp_path / "empty.docx"
    path.write_bytes(b"")
    assert wait_until_file_ready(str(path), timeout=0.3, poll=0.05) is False


def test_choose_resume_card_uses_the_file_just_prepared():
    from automation.job_resume import choose_resume_card

    prepared = "Ada Lovelace_Backend Engineer_Acme_5 years.docx"
    older = [
        "Ada Lovelace_Django_5 years.docx",
        "Ada Lovelace_Data Analyst_Northwind_4 years.pdf",
    ]
    shown = older + ["Ada Lovelace_Backend Engineer_Acme_5 years.docx"]
    assert choose_resume_card(shown, prepared, before=older) == 2


def test_choose_resume_card_ignores_other_versions_of_the_same_person():
    from automation.job_resume import choose_resume_card

    prepared = "Ada Lovelace_Backend Engineer_Acme_5 years.docx"
    older = [
        "Ada Lovelace_Django_5 years.docx",
        "Ada Lovelace_Data Analyst_Northwind_4 years.pdf",
    ]
    assert choose_resume_card(older, prepared, before=older) is None


def test_local_resume_filename_uses_the_job_version_name():
    from automation.job_resume import local_resume_filename

    header = 'attachment; filename="Ada Lovelace_Backend Engineer_Acme_5 years.docx"'
    assert local_resume_filename(header, "12345") == "Ada Lovelace_Backend Engineer_Acme_5 years.docx"


def test_choose_resume_card_matches_a_truncated_linkedin_title():
    from automation.job_resume import choose_resume_card

    prepared = "Ada Lovelace_Backend Engineer_Acme_5 years.docx"
    shown = [
        "Ada Lovelace_Django_5 years",
        "Ada Lovelace_Backend Engi…",
    ]
    assert choose_resume_card(shown, prepared, before=[]) == 1
