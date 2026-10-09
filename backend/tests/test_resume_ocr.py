from pathlib import Path

from backend.app.services import resume_ocr, resume_text_service


def test_text_usable_requires_enough_alnum():
    assert not resume_ocr.text_usable("   ")
    assert resume_ocr.text_usable("Jane Doe\n" + "Python developer " * 10)


def test_merge_prefers_ocr_when_native_weak():
    native = "x"
    ocr = "Jane Doe\nSenior Engineer at Acme with Python and Django experience for many years."
    merged = resume_ocr.merge_pdf_text(native, ocr)
    assert "Jane Doe" in merged


def test_extract_pdf_falls_back_to_ocr(tmp_path, monkeypatch):
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"%PDF-1.4\nminimal\n")

    def fake_ocr(path: Path, **kwargs):
        assert path == pdf
        return "Alice Rao\n9876543210\nSummary\nBackend engineer with 5 years experience."

    monkeypatch.setattr(resume_ocr, "ocr_pdf", fake_ocr)
    monkeypatch.setattr(resume_text_service, "_pdf_native_text", lambda _p: "")

    text, source = resume_text_service.extract_text_with_source(pdf, "pdf")
    assert source == "ocr"
    assert "Alice Rao" in text
