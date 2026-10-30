"""Source rotation: switch after N submissions, ignore skips, leave a blocked source."""

from automation.sources.history import paths_for, read_job_ids
from automation.sources.naukri_links import (
    actionable_question, chat_step, classify_apply, education_course_answer, education_level_answer,
    education_specialization_answer, education_year_answer, fresher_or_experienced, job_page_url,
    keep_leaf_chat_options, pick_education_option, pick_option, preferred_chat_answer, search_url,
)
from automation.sources.rotation import Rotation


def test_switch_after_n_successful_applications_and_skips_do_not_count():
    rotation = Rotation(["linkedin", "naukri"], 2)
    assert rotation.current() == "linkedin"
    assert rotation.record("skipped") == []
    assert rotation.record("failed") == []
    assert rotation.submitted_on_source == 0
    assert rotation.current() == "linkedin"
    assert rotation.record("submitted") == []
    switched = rotation.record("submitted")
    assert switched[0]["event"] == "source_switched"
    assert switched[0]["source"] == "naukri"
    assert switched[0]["submitted_on_previous"] == 2
    assert rotation.current() == "naukri"
    assert rotation.submitted_on_source == 0


def test_a_blocked_source_is_skipped_when_another_remains():
    rotation = Rotation(["linkedin", "naukri"], 10)
    events = rotation.record("blocked", reason="captcha")
    assert events[0] == {"event": "source_blocked", "source": "linkedin", "reason": "captcha"}
    assert events[1]["event"] == "source_switched"
    assert events[1]["source"] == "naukri"
    assert rotation.current() == "naukri"


def test_the_only_source_stops_when_it_is_blocked():
    rotation = Rotation(["naukri"], None)
    events = rotation.record("blocked", reason="Sign in to Naukri to continue.")
    assert events == [{
        "event": "source_blocked",
        "source": "naukri",
        "reason": "Sign in to Naukri to continue.",
    }]
    assert rotation.current() is None


def test_history_files_are_split_by_source(tmp_path):
    applied = tmp_path / "applied.csv"
    applied.write_text("Job ID\n100\n", encoding="utf-8")
    linkedin_applied, linkedin_failed = paths_for(str(applied), "linkedin")
    naukri_applied, _failed = paths_for(str(applied), "naukri")
    assert linkedin_applied.endswith("/linkedin/applied.csv")
    assert linkedin_failed.endswith("/linkedin/failed.csv")
    assert naukri_applied.endswith("/naukri/applied.csv")
    assert read_job_ids(str(applied)) == {"100"}


def test_naukri_apply_classification_and_search_url():
    assert classify_apply("Apply", left_naukri=False) == "onsite"
    assert classify_apply("Apply on company site", left_naukri=False) == "external"
    assert classify_apply("Apply", left_naukri=True) == "external"
    assert "k=Python+Developer" in search_url("Python Developer", "Bengaluru")
    assert search_url("Python Developer", "Bengaluru").endswith("&l=Bengaluru")
    assert job_page_url("123456") == "https://www.naukri.com/job-listings-123456"


def test_naukri_chat_follows_the_question_and_does_not_treat_a_choice_as_text():
    question = "Sorry I couldn’t understand. Are you a fresher or are you experienced?"
    assert actionable_question(question) == "Are you a fresher or are you experienced?"
    assert chat_step(question) == "choice"
    assert chat_step("What is your highest education level?") == "choice"
    assert chat_step("Select your qualification") == "choice"
    assert chat_step("Which course did you study?") == "choice"
    assert chat_step("What was your specialization in B.Tech / B.E.?") == "choice"
    assert chat_step("What was the course type?") == "choice"
    assert chat_step("In which institute did you study B.Tech / B.E.?") == "text"
    assert chat_step("Please upload your resume") == "resume"
    assert fresher_or_experienced("0") == "Fresher"
    assert fresher_or_experienced(5) == "Experienced"
    assert preferred_chat_answer(question, "0") == "Fresher"
    options = ["Fresher", "Experienced"]
    assert pick_option(preferred_chat_answer(question, "0"), options) == "Fresher"
    assert pick_option("Graduate or Diploma", ["Graduate or Diploma", "Doctorate"]) == "Graduate or Diploma"
    assert pick_option("Applied Electronics", ["B.Tech / B.E.", "MBA"]) is None


def test_naukri_education_answers_from_master_profile_rows():
    education = [
        {"school": "IIT Delhi", "degree": "B.Tech", "field": "Computer Science", "end_year": "2020"},
    ]
    assert education_level_answer(education) == "Graduation"
    assert education_course_answer(education) == "B.Tech / B.E."
    assert education_specialization_answer(education) == "Computer Science"
    assert education_year_answer(education) == "2020"
    options = ["Graduate or Diploma", "Doctorate"]
    assert pick_option(preferred_chat_answer("What is your highest education level?", education=education), options) == "Graduate or Diploma"
    naukri_chips = ["10th", "12th", "Diploma", "Graduation", "Post Graduation", "Doctorate"]
    assert pick_option(preferred_chat_answer("Select your qualification", education=education), naukri_chips) == "Graduation"
    assert pick_education_option(naukri_chips, education) == "Graduation"
    assert pick_option("B.Tech", ["B.Tech/B.E.", "MBA", "B.Sc"]) == "B.Tech/B.E."
    assert pick_option("Computer Science", ["Mechanical", "Computer Science & Engineering"]) == "Computer Science & Engineering"
    assert keep_leaf_chat_options(["Graduation", "Post Graduation", "Graduation Post Graduation"]) == ["Graduation", "Post Graduation"]
    mba = [{"degree": "MBA", "field": "Finance", "school": "ISB", "end_year": "2018"}]
    assert education_level_answer(mba) == "Post Graduation"
    assert pick_education_option(naukri_chips, mba) == "Post Graduation"
