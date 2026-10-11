from automation.resume_naming import (
    build_resume_filename,
    build_resume_stem,
    next_resume_version,
)


def test_build_resume_stem():
    assert build_resume_stem(candidate="Ada Lovelace", skills=["Python", "Django"], experience="5 years") == (
        "Ada_Lovelace_Python-Django_5y"
    )


def test_build_resume_filename_version():
    name = build_resume_filename(
        candidate="Shankar DA",
        skills="Python-Kubernetes",
        experience=7,
        version=1,
        ext=".pdf",
    )
    assert name == "Shankar_DA_Python-Kubernetes_7y_v-1.pdf"


def test_next_resume_version_increments(tmp_path):
    jobs = tmp_path / "jobs" / "123"
    jobs.mkdir(parents=True)
    (jobs / "Ada_Python_5y_v-1.pdf").write_bytes(b"x")
    (jobs / "Ada_Python_5y_v-3.pdf").write_bytes(b"x")
    assert next_resume_version(cache_dir=str(tmp_path)) == 4
