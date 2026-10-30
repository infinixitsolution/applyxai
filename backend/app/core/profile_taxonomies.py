"""Searchable taxonomy options for career preferences (maintained in-app, not scraped)."""

INDUSTRIES = [
    {"id": "it_software", "label": "IT / Software"},
    {"id": "finance", "label": "Finance & Banking"},
    {"id": "healthcare", "label": "Healthcare"},
    {"id": "manufacturing", "label": "Manufacturing"},
    {"id": "retail", "label": "Retail & E-commerce"},
    {"id": "education", "label": "Education"},
    {"id": "consulting", "label": "Consulting"},
    {"id": "telecom", "label": "Telecom"},
    {"id": "media", "label": "Media & Entertainment"},
    {"id": "other", "label": "Other"},
]

DEPARTMENTS = [
    {"id": "engineering", "label": "Engineering"},
    {"id": "product", "label": "Product"},
    {"id": "design", "label": "Design"},
    {"id": "data", "label": "Data & Analytics"},
    {"id": "sales", "label": "Sales"},
    {"id": "marketing", "label": "Marketing"},
    {"id": "operations", "label": "Operations"},
    {"id": "hr", "label": "Human Resources"},
    {"id": "finance", "label": "Finance"},
    {"id": "other", "label": "Other"},
]

JOB_ROLES = [
    {"id": "software_engineer", "label": "Software Engineer"},
    {"id": "backend_developer", "label": "Backend Developer"},
    {"id": "frontend_developer", "label": "Frontend Developer"},
    {"id": "full_stack", "label": "Full Stack Developer"},
    {"id": "data_engineer", "label": "Data Engineer"},
    {"id": "data_scientist", "label": "Data Scientist"},
    {"id": "devops", "label": "DevOps / SRE"},
    {"id": "qa", "label": "QA / Test Engineer"},
    {"id": "product_manager", "label": "Product Manager"},
    {"id": "other", "label": "Other"},
]

EDUCATION_LEVELS = [
    "Doctorate / PhD",
    "Master's / post-graduation",
    "Graduation / bachelor's degree",
    "Diploma",
    "Class XII",
    "Class X",
    "Below Class X",
    "Other",
]

EMPLOYMENT_TYPES = [
    "Full-time",
    "Part-time",
    "Contract",
    "Internship",
    "Freelance",
    "Temporary",
    "Other",
]

SKILL_CATEGORIES = [
    "Technical / IT skills",
    "Programming languages",
    "Frameworks and libraries",
    "Databases",
    "Cloud and DevOps tools",
    "Business applications",
    "Soft skills",
    "Other professional skills",
]

COMMON_ANSWER_TEMPLATES = [
    {"key": "about_yourself", "question": "Tell us about yourself.", "category": "Introduction"},
    {"key": "why_role", "question": "Why are you interested in this role?", "category": "Motivation"},
    {"key": "why_hire", "question": "Why should we hire you?", "category": "Motivation"},
    {"key": "strengths", "question": "What are your strengths?", "category": "Behavioral"},
    {"key": "weaknesses", "question": "What are your weaknesses?", "category": "Behavioral"},
    {"key": "achievement", "question": "Describe a significant achievement.", "category": "Behavioral"},
    {"key": "career_goals", "question": "What are your career goals?", "category": "Career"},
    {"key": "leaving_job", "question": "Why are you leaving your current job?", "category": "Career"},
    {"key": "expected_salary", "question": "What is your expected salary?", "category": "Compensation", "profile_field": "expected_ctc"},
    {"key": "current_salary", "question": "What is your current salary?", "category": "Compensation", "profile_field": "current_ctc"},
    {"key": "notice_period", "question": "What is your notice period?", "category": "Availability", "profile_field": "notice_period_days"},
    {"key": "when_join", "question": "When can you join?", "category": "Availability", "profile_field": "availability"},
    {"key": "relocate", "question": "Are you willing to relocate?", "category": "Preferences"},
    {"key": "work_auth", "question": "Are you legally authorized to work?", "category": "Work authorization"},
    {"key": "visa_sponsor", "question": "Do you require visa sponsorship?", "category": "Work authorization"},
]
