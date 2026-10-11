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


def test_prepare_resume_for_job_uses_jd_folder(tmp_path):
    from automation.job_resume import job_resume_dir, prepare_resume_for_job

    src = tmp_path / "ShankarDA.pdf"
    src.write_bytes(b"%PDF-1.4")
    out = prepare_resume_for_job(
        str(src),
        job_id="4478061191",
        job_title="Software Engineer",
        company="Jobtogether",
        cache_dir=str(tmp_path / "cache"),
        candidate="Shankar DA",
        skills=["Python", "Django"],
        experience=5,
    )
    assert job_resume_dir(str(tmp_path / "cache"), "4478061191") in __import__("pathlib").Path(out).parents
    assert "_v-1" in out
    assert "Shankar" in out or "Software_Engineer" in out.replace(" ", "_")


def test_choose_resume_after_upload_when_linkedin_keeps_old_filename():
    from automation.job_resume import choose_resume_after_upload

    before = ["ShankarDA.pdf"] * 5
    labels = before + ["ShankarDA.pdf"]
    fulls = [f"ShankarDA.pdf\nLast used on 10/8/2026"] * 5 + ["ShankarDA.pdf\nUploaded on 10/11/2026"]
    staged = "ShankarDA_Python_5y_v-2.pdf"
    assert choose_resume_after_upload(labels, staged, before, full_texts=fulls) == 5


def test_choose_resume_card_prefers_fresh_upload_when_titles_match(tmp_path):
    from automation.job_resume import choose_resume_card, prepare_resume_for_job

    prepared = prepare_resume_for_job(
        str(tmp_path / "ShankarDA.pdf"),
        job_id="4478061191",
        job_title="Python Engineer",
        company="HARISAN",
        cache_dir=str(tmp_path),
    )
    name = prepared.split("\\")[-1].split("/")[-1]
    before = ["ShankarDA.pdf", "ShankarDA.pdf"]
    fulls = [
        "ShankarDA.pdf\nLast used on 10/9/2026",
        "ShankarDA.pdf\nLast used on 10/8/2026",
        f"{name}\nUploaded on 10/11/2026",
    ]
    labels = ["ShankarDA.pdf", "ShankarDA.pdf", name]
    assert choose_resume_card(labels, name, before=before, full_texts=fulls) == 2


def test_choose_resume_card_picks_newest_uploaded_duplicate_name():
    from automation.job_resume import choose_resume_card

    prepared = "ShankarDA.pdf"
    before = ["ShankarDA.pdf"] * 4
    fulls = [
        "ShankarDA.pdf\nUploaded on 10/11/2026",
        "ShankarDA.pdf\nLast used on 10/9/2026",
        "ShankarDA.pdf\nLast used on 10/9/2026",
        "ShankarDA.pdf\nLast used on 10/8/2026",
        "ShankarDA.pdf\nUploaded on 10/10/2026",
    ]
    labels = ["ShankarDA.pdf"] * 5
    assert choose_resume_card(labels, prepared, before=before, full_texts=fulls) == 0


def test_choose_resume_card_matches_a_truncated_linkedin_title():
    from automation.job_resume import choose_resume_card

    prepared = "Ada Lovelace_Backend Engineer_Acme_5 years.docx"
    shown = [
        "Ada Lovelace_Django_5 years",
        "Ada Lovelace_Backend Engi…",
    ]
    assert choose_resume_card(shown, prepared, before=[]) == 1
