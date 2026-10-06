import io
import zipfile

import pytest

from backend.app.core.config import get_settings
from backend.app.models import Plan, Subscription, SubscriptionStatus, User
from backend.app.services.resume_service import DOCX_MIME, safe_display_name
from backend.tests.conftest import csrf_headers

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def make_docx(macro: bool = False) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", "<w:document/>")
        if macro:
            zf.writestr("word/vbaProject.bin", b"\x00")
    return buf.getvalue()


@pytest.fixture
def alice(make_user):
    return make_user()


def upload(client, filename="cv.pdf", data=PDF, mime="application/pdf", name=None):
    form = {"name": name} if name else None
    return client.post("/api/resumes", files={"file": (filename, data, mime)}, data=form,
                       headers=csrf_headers(client))


def give_plan(db, email, code, resumes):
    user = db.query(User).filter_by(email=email).one()
    plan = Plan(code=code, name=code.title(), limits={"resumes": resumes})
    db.add(plan)
    db.flush()
    db.add(Subscription(user_id=user.id, plan_id=plan.id, status=SubscriptionStatus.ACTIVE))
    db.commit()


def test_upload_pdf_stores_under_generated_name(alice, storage_dir):
    resp = upload(alice, filename="../../etc/My CV.pdf")
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["filename"] == "My CV.pdf" and data["name"] == "My CV"
    assert data["is_default"] is True and data["file_type"] == "pdf" and data["file_size"] == len(PDF)

    files = list(storage_dir.rglob("*.pdf"))
    assert len(files) == 1 and files[0].read_bytes() == PDF
    assert files[0].parent.parent == storage_dir / "resumes"          # resumes/<user_id>/<uuid>.pdf
    assert "My CV" not in files[0].name and "storage_path" not in data


def test_upload_docx_and_custom_name(alice):
    resp = upload(alice, filename="cv.docx", data=make_docx(), mime=DOCX_MIME, name="Backend roles")
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["name"] == "Backend roles"


def test_generic_mime_is_accepted_when_content_matches(alice):
    assert upload(alice, mime="application/octet-stream").status_code == 201


@pytest.mark.parametrize("filename,data,mime", [
    ("cv.exe", PDF, "application/pdf"),                         # wrong extension
    ("cv", PDF, "application/pdf"),                             # no extension
    ("cv.doc", PDF, "application/msword"),                      # legacy Word is not supported
    ("cv.pdf", b"MZ\x90\x00 not a pdf", "application/pdf"),     # spoofed extension
    ("cv.docx", PDF, DOCX_MIME),                                # PDF bytes renamed to .docx
    ("cv.docx", b"PK\x03\x04garbage", DOCX_MIME),               # broken zip
    ("cv.docx", make_docx(macro=True), DOCX_MIME),              # macro-enabled document
    ("cv.pdf", PDF, "text/html"),                               # declared type contradicts extension
    ("cv.pdf", b"", "application/pdf"),                         # empty
])
def test_rejects_invalid_files(alice, storage_dir, filename, data, mime):
    resp = upload(alice, filename=filename, data=data, mime=mime)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"]["code"] == "INVALID_FILE"
    assert not list(storage_dir.rglob("*.*"))


def test_rejects_oversized_file(alice, storage_dir, monkeypatch):
    monkeypatch.setattr(get_settings(), "MAX_RESUME_BYTES", 1024)
    resp = upload(alice, data=PDF + b"0" * 2048)
    assert resp.status_code == 413
    assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"
    assert not list(storage_dir.rglob("*.*"))


def test_free_plan_resume_limit_is_enforced_server_side(alice, db):
    assert upload(alice).status_code == 201
    resp = upload(alice)
    assert resp.status_code == 403 and resp.json()["error"]["code"] == "PLAN_LIMIT_REACHED"

    give_plan(db, "alice@example.com", "starter", resumes=3)
    assert upload(alice).status_code == 201
    assert alice.get("/api/resumes").json()["data"]["limit"] == 3


def test_upload_requires_csrf(alice):
    resp = alice.post("/api/resumes", files={"file": ("cv.pdf", PDF, "application/pdf")})
    assert resp.status_code == 403


def test_rename_default_delete_and_download(alice, db, storage_dir):
    give_plan(db, "alice@example.com", "pro", resumes=10)
    h = csrf_headers(alice)
    first = upload(alice, name="One").json()["data"]
    second = upload(alice, filename="two.docx", data=make_docx(), mime=DOCX_MIME).json()["data"]
    third = upload(alice, name="Three").json()["data"]
    assert [first["is_default"], second["is_default"], third["is_default"]] == [True, False, False]

    assert alice.patch(f"/api/resumes/{second['id']}", json={"name": "  Two  "}, headers=h).json()["data"]["name"] == "Two"
    assert alice.patch(f"/api/resumes/{second['id']}", json={"name": "   "}, headers=h).status_code == 422

    assert alice.post(f"/api/resumes/{second['id']}/default", headers=h).json()["data"]["is_default"] is True
    listed = alice.get("/api/resumes").json()["data"]["resumes"]
    assert [r["id"] for r in listed if r["is_default"]] == [second["id"]]
    assert listed[0]["id"] == second["id"]

    resp = alice.get(f"/api/resumes/{second['id']}/download")
    assert resp.status_code == 200 and resp.content == make_docx()
    assert resp.headers["content-type"] == DOCX_MIME
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["content-disposition"].startswith("attachment;")

    # Deleting the default promotes the newest remaining resume and removes the file.
    assert alice.delete(f"/api/resumes/{second['id']}", headers=h).status_code == 200
    listed = alice.get("/api/resumes").json()["data"]["resumes"]
    assert {r["id"]: r["is_default"] for r in listed} == {third["id"]: True, first["id"]: False}
    assert len(list(storage_dir.rglob("*.*"))) == 2
    assert alice.get(f"/api/resumes/{second['id']}/download").status_code == 404


def test_unknown_or_malformed_ids_are_404_or_422(alice):
    assert alice.get("/api/resumes/00000000-0000-0000-0000-000000000000/download").status_code == 404
    assert alice.get("/api/resumes/not-a-uuid/download").status_code == 422


@pytest.mark.parametrize("raw,expected", [
    ("C:\\Users\\bob\\cv.pdf", "cv.pdf"),
    ("../../secret.pdf", "secret.pdf"),
    ("cv\x00\r\n.pdf", "cv.pdf"),
    ("", "resume"),
    ("...", "resume"),
])
def test_safe_display_name(raw, expected):
    assert safe_display_name(raw) == expected
