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
