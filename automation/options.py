"""
The exact strings the engine accepts, copied from modules/validator.py.

The engine clicks LinkedIn filters by visible text, so these must stay literal strings
("Entry level", "Full-time", ...), never IDs. This module is side-effect free (importing
modules/validator.py would load config/*.py and user_config.json), and
backend/tests/test_engine_options.py fails if it ever drifts from the validator.
"""

EXPERIENCE_LEVELS = ["Internship", "Entry level", "Associate", "Mid-Senior level", "Director", "Executive"]
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Temporary", "Volunteer", "Internship", "Other"]
WORK_SETTINGS = ["On-site", "Remote", "Hybrid"]
DATE_POSTED = ["", "Any time", "Past month", "Past week", "Past 24 hours"]
SORT_BY = ["", "Most recent", "Most relevant"]

ETHNICITY = ["Decline", "Hispanic/Latino", "American Indian or Alaska Native", "Asian", "Black or African American",
             "Native Hawaiian or Other Pacific Islander", "White", "Other"]
GENDER = ["Male", "Female", "Other", "Decline", ""]
DISABILITY_STATUS = ["Yes", "No", "Decline"]
VETERAN_STATUS = ["Yes", "No", "Decline"]
REQUIRE_VISA = ["Yes", "No"]
US_CITIZENSHIP = ["U.S. Citizen/Permanent Resident", "Non-citizen allowed to work for any employer",
                  "Non-citizen allowed to work for current employer", "Non-citizen seeking work authorization",
                  "Canadian Citizen/Permanent Resident", "Other"]

# Engine setting name -> allowed values, for every option-restricted setting the SaaS stores.
ENGINE_OPTIONS = {
    "experience_level": EXPERIENCE_LEVELS,
    "job_type": JOB_TYPES,
    "on_site": WORK_SETTINGS,
    "date_posted": DATE_POSTED,
    "sort_by": SORT_BY,
    "ethnicity": ETHNICITY,
    "gender": GENDER,
    "disability_status": DISABILITY_STATUS,
    "veteran_status": VETERAN_STATUS,
    "require_visa": REQUIRE_VISA,
    "us_citizenship": US_CITIZENSHIP,
}

# Integer settings and the minimum the validator enforces (check_int).
ENGINE_INT_MINIMUMS = {
    "desired_salary": 0,
    "current_ctc": 0,
    "notice_period": 0,
    "switch_number": 1,
    "current_experience": -1,
    "click_gap": 0,
}
