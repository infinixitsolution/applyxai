"""Seed five demo students on Riverside Training with profiles and job activity.

Run from the project root:
    python scripts/seed_riverside_students.py
"""

from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select

from backend.app.core.database import SessionLocal
from backend.app.core.security import hash_password
from backend.app.models import (
    Application,
    ApplicationPreferences,
    ApplicationStatus,
    Institute,
    InstituteAssignment,
    InstituteMember,
    Job,
    MockInterviewSession,
    MockInterviewSessionStatus,
    OPEN_ASSIGNMENT_STATUSES,
    Resume,
    SearchConfig,
    SeatStatus,
    User,
    UserProfile,
)
from backend.app.services import institute_service

DEMO_PASSWORD = "StudentDemo1!"
INSTITUTE_EMAIL = "priya.riverside@example.com"
INSTITUTE_NAME = "Riverside Training"

STUDENTS = [
    {
        "name": "Aarav Mehta",
        "email": "aarav.mehta.riverside@example.com",
        "phone": "9810011001",
        "headline": "Full-stack intern targeting product engineering roles",
        "summary": "Campus intern who ships React and FastAPI features, writes tests, and wants a first full-time software role in Bengaluru.",
        "current_title": "Software intern",
        "current_company": "Riverside Labs",
        "experience_years": 1,
        "skills": ["Python", "React", "TypeScript", "SQL", "Git"],
        "preferred_roles": ["Software Engineer", "Full Stack Developer"],
        "preferred_locations": ["Bengaluru", "Remote"],
        "education": [{"school": "Riverside Institute of Technology", "degree": "B.Tech", "field": "Computer Science", "start_year": "2022", "end_year": "2026"}],
        "work_history": [{
            "title": "Software intern", "company": "Riverside Labs", "location": "Pune",
            "start": "2025-06", "end": "Present",
            "summary": "Built campus portal screens and API tests for student onboarding.",
        }],
        "search": {
            "keywords": ["software engineer", "full stack intern"],
            "location": "Bengaluru",
            "easy_apply_only": True,
            "experience_level": ["Internship", "Entry level"],
            "job_type": ["Full-time"],
            "on_site": ["Hybrid", "Remote"],
            "date_posted": "Past month",
            "salary_min": 400000,
            "salary_max": 900000,
        },
        "apps": [
            ("applied", 2), ("applied", 5), ("applied", 8), ("failed", 3),
            ("skipped", 4), ("discovered", 1), ("applied", 12),
        ],
        "mock": True,
    },
    {
        "name": "Diya Sharma",
        "email": "diya.sharma.riverside@example.com",
        "phone": "9810011002",
        "headline": "Data analyst focused on SQL, dashboards, and Python",
        "summary": "Turns campus placement data into dashboards. Looking for analyst roles that mix SQL with stakeholder reporting.",
        "current_title": "Data intern",
        "current_company": "Harbor Analytics",
        "experience_years": 1,
        "skills": ["SQL", "Python", "Excel", "Tableau", "Pandas"],
        "preferred_roles": ["Data Analyst", "Business Analyst"],
        "preferred_locations": ["Hyderabad", "Pune"],
        "education": [{"school": "Riverside Institute of Technology", "degree": "B.Sc", "field": "Statistics", "start_year": "2022", "end_year": "2026"}],
        "work_history": [{
            "title": "Data intern", "company": "Harbor Analytics", "location": "Hyderabad",
            "start": "2025-05", "end": "Present",
            "summary": "Weekly placement funnels and recruiter conversion reports.",
        }],
        "search": {
            "keywords": ["data analyst", "sql"],
            "location": "Hyderabad",
            "easy_apply_only": True,
            "experience_level": ["Entry level"],
            "job_type": ["Full-time"],
            "on_site": ["On-site", "Hybrid"],
            "date_posted": "Past week",
            "salary_min": 500000,
            "salary_max": 1000000,
        },
        "apps": [
            ("applied", 1), ("applied", 6), ("skipped", 7), ("failed", 9),
            ("discovered", 10), ("applied", 14),
        ],
        "mock": True,
    },
    {
        "name": "Kabir Iyer",
        "email": "kabir.iyer.riverside@example.com",
        "phone": "9810011003",
        "headline": "QA engineer who automates regression with Playwright",
        "summary": "Campus QA intern covering API and UI regression. Wants SDET roles that mix Python with browser automation.",
        "current_title": "QA intern",
        "current_company": "Nimbus Quality",
        "experience_years": 2,
        "skills": ["Playwright", "Python", "Postman", "CI", "Selenium"],
        "preferred_roles": ["SDET", "QA Engineer"],
        "preferred_locations": ["Chennai", "Bengaluru"],
        "education": [{"school": "Riverside Institute of Technology", "degree": "B.Tech", "field": "Information Technology", "start_year": "2021", "end_year": "2025"}],
        "work_history": [{
            "title": "QA intern", "company": "Nimbus Quality", "location": "Chennai",
            "start": "2024-07", "end": "Present",
            "summary": "Automated smoke tests for the campus jobs board.",
        }],
        "search": {
            "keywords": ["sdet", "qa engineer"],
            "location": "Chennai",
            "easy_apply_only": False,
            "experience_level": ["Entry level", "Associate"],
            "job_type": ["Full-time"],
            "on_site": ["Hybrid"],
            "date_posted": "Past month",
            "salary_min": 600000,
            "salary_max": 1200000,
        },
        "apps": [
            ("applied", 0), ("failed", 2), ("skipped", 11), ("discovered", 13),
            ("applied", 15), ("applied", 3),
        ],
        "mock": False,
    },
    {
        "name": "Ananya Reddy",
        "email": "ananya.reddy.riverside@example.com",
        "phone": "9810011004",
        "headline": "Product designer for hiring and campus workflows",
        "summary": "Designs flows that help students apply faster. Looking for product design roles in hiring tech.",
        "current_title": "Product design intern",
        "current_company": "ApplyXAI campus studio",
        "experience_years": 1,
        "skills": ["Figma", "User research", "Prototyping", "Design systems"],
        "preferred_roles": ["Product Designer", "UX Designer"],
        "preferred_locations": ["Bengaluru", "Mumbai"],
        "education": [{"school": "Riverside Institute of Technology", "degree": "B.Des", "field": "Interaction Design", "start_year": "2022", "end_year": "2026"}],
        "work_history": [{
            "title": "Product design intern", "company": "ApplyXAI campus studio", "location": "Bengaluru",
            "start": "2025-08", "end": "Present",
            "summary": "Redesigned the campus student list and candidate profile.",
        }],
        "search": {
            "keywords": ["product designer", "ux designer"],
            "location": "Bengaluru",
            "easy_apply_only": True,
            "experience_level": ["Internship", "Entry level"],
            "job_type": ["Full-time"],
            "on_site": ["Hybrid", "Remote"],
            "date_posted": "Past month",
            "salary_min": 450000,
            "salary_max": 1100000,
        },
        "apps": [
            ("applied", 4), ("applied", 16), ("skipped", 0), ("failed", 8),
            ("discovered", 17), ("applied", 18),
        ],
        "mock": False,
    },
    {
        "name": "Rohan Kapoor",
        "email": "rohan.kapoor.riverside@example.com",
        "phone": "9810011005",
        "headline": "DevOps intern learning AWS, Docker, and CI pipelines",
        "summary": "Keeps campus demo environments running. Targeting junior DevOps and platform roles.",
        "current_title": "DevOps intern",
        "current_company": "Cloudyard",
        "experience_years": 1,
        "skills": ["AWS", "Docker", "Linux", "GitHub Actions", "Nginx"],
        "preferred_roles": ["DevOps Engineer", "Platform Engineer"],
        "preferred_locations": ["Pune", "Remote"],
        "education": [{"school": "Riverside Institute of Technology", "degree": "B.Tech", "field": "Electronics", "start_year": "2021", "end_year": "2025"}],
        "work_history": [{
            "title": "DevOps intern", "company": "Cloudyard", "location": "Pune",
            "start": "2025-01", "end": "Present",
            "summary": "Containerised the campus API and added health checks.",
        }],
        "search": {
            "keywords": ["devops intern", "platform engineer"],
            "location": "Pune",
            "easy_apply_only": True,
            "experience_level": ["Internship", "Entry level"],
            "job_type": ["Full-time"],
            "on_site": ["Remote", "Hybrid"],
            "date_posted": "Past week",
            "salary_min": 500000,
            "salary_max": 1000000,
        },
        "apps": [
            ("applied", 19), ("failed", 1), ("skipped", 5), ("discovered", 6),
            ("applied", 7), ("queued", 11),
        ],
        "mock": True,
    },
]

JOBS = [
    ("demo-riv-0", "Software Engineer", "Infowave", "Bengaluru"),
    ("demo-riv-1", "Data Analyst", "Harbor Analytics", "Hyderabad"),
    ("demo-riv-2", "SDET", "Nimbus Quality", "Chennai"),
    ("demo-riv-3", "Backend Engineer", "Acme Cloud", "Bengaluru"),
    ("demo-riv-4", "Product Designer", "PixelForge", "Mumbai"),
    ("demo-riv-5", "DevOps Engineer", "Cloudyard", "Pune"),
    ("demo-riv-6", "Business Analyst", "Northstar", "Hyderabad"),
    ("demo-riv-7", "Platform Engineer", "Stackline", "Remote"),
    ("demo-riv-8", "Frontend Developer", "Brightboard", "Bengaluru"),
    ("demo-riv-9", "SQL Analyst", "Ledgerly", "Pune"),
    ("demo-riv-10", "Junior Data Scientist", "Harbor Analytics", "Hyderabad"),
    ("demo-riv-11", "QA Engineer", "Nimbus Quality", "Chennai"),
    ("demo-riv-12", "Full Stack Developer", "Infowave", "Bengaluru"),
    ("demo-riv-13", "Test Automation Engineer", "Qubit Labs", "Chennai"),
    ("demo-riv-14", "Reporting Analyst", "Northstar", "Hyderabad"),
    ("demo-riv-15", "Associate SDET", "Brightboard", "Bengaluru"),
    ("demo-riv-16", "UX Designer", "PixelForge", "Bengaluru"),
    ("demo-riv-17", "Visual Designer", "Harbor Studio", "Mumbai"),
    ("demo-riv-18", "Product Designer Intern", "ApplyXAI", "Remote"),
    ("demo-riv-19", "Cloud Intern", "Cloudyard", "Pune"),
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job(db, spec: tuple[str, str, str, str]) -> Job:
    external_id, title, company, location = spec
    row = db.scalar(select(Job).where(Job.platform == "linkedin", Job.external_id == external_id))
    if row is None:
        row = Job(
            external_id=external_id,
            platform="linkedin",
            title=title,
            company=company,
            location=location,
            job_url=f"https://www.linkedin.com/jobs/view/{external_id}",
            description=f"Demo campus posting for {title} at {company}.",
        )
        db.add(row)
        db.flush()
    return row


def _ensure_profile(db, user: User, spec: dict) -> None:
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    profile.phone = spec["phone"]
    profile.headline = spec["headline"]
    profile.summary = spec["summary"]
    profile.current_title = spec["current_title"]
    profile.current_company = spec["current_company"]
    profile.experience_years = spec["experience_years"]
    profile.skills = spec["skills"]
    profile.preferred_roles = spec["preferred_roles"]
    profile.preferred_locations = spec["preferred_locations"]
    profile.education = spec["education"]
    profile.work_history = spec["work_history"]

    search = db.scalar(select(SearchConfig).where(SearchConfig.user_id == user.id))
    if search is None:
        search = SearchConfig(user_id=user.id)
        db.add(search)
    for key, value in spec["search"].items():
        setattr(search, key, value)

    prefs = db.scalar(select(ApplicationPreferences).where(ApplicationPreferences.user_id == user.id))
    if prefs is None:
        db.add(ApplicationPreferences(user_id=user.id, answers={"years_of_experience": spec["experience_years"]}))

    resume = db.scalar(select(Resume).where(Resume.user_id == user.id, Resume.is_default.is_(True)))
    if resume is None:
        slug = hashlib.sha256(str(user.id).encode()).hexdigest()[:16]
        db.add(Resume(
            user_id=user.id,
            name=f"{spec['name']} resume",
            filename=f"{spec['name'].replace(' ', '_').lower()}.pdf",
            storage_path=f"demo/riverside/{slug}.pdf",
            file_type="pdf",
            file_size=24832,
            sha256=hashlib.sha256(slug.encode()).hexdigest(),
            is_default=True,
        ))


def _ensure_apps(db, user: User, spec: dict, jobs: list[Job]) -> None:
    existing = db.scalar(select(Application.id).where(Application.user_id == user.id))
    if existing is not None:
        return
    now = _now()
    first_applied = None
    first_job = None
    for offset, (status_name, job_index) in enumerate(spec["apps"]):
        status = ApplicationStatus(status_name)
        when = now - timedelta(days=2 + offset * 2, hours=offset)
        app = Application(
            user_id=user.id,
            job_id=jobs[job_index].id,
            status=status,
            applied_at=when if status in (ApplicationStatus.APPLIED, ApplicationStatus.FAILED) else None,
            failure_reason="Easy Apply form timed out" if status == ApplicationStatus.FAILED else "",
        )
        if status == ApplicationStatus.APPLIED and first_applied is None:
            first_applied = app
            first_job = jobs[job_index]
        db.add(app)
    db.flush()
    if spec.get("mock") and first_applied is not None and first_job is not None:
        already = db.scalar(select(MockInterviewSession.id).where(MockInterviewSession.user_id == user.id))
        if already is None:
            db.add(MockInterviewSession(
                user_id=user.id,
                application_id=first_applied.id,
                interview_types=["behavioral"],
                status=MockInterviewSessionStatus.COMPLETED,
                turn_count=6,
                feedback={"overall_score": 74},
                context_snapshot={"job_title": first_job.title, "company": first_job.company},
            ))


def main() -> int:
    from backend.app.models import InstituteSeat

    db = SessionLocal()
    try:
        institute = db.scalar(select(Institute).where(Institute.email == INSTITUTE_EMAIL))
        if institute is None:
            institute = db.scalar(select(Institute).where(Institute.name == INSTITUTE_NAME))
        if institute is None:
            print("Riverside Training was not found in this database.", file=sys.stderr)
            return 1
        member = db.scalar(
            select(InstituteMember)
            .where(InstituteMember.institute_id == institute.id, InstituteMember.status == "active")
            .order_by(InstituteMember.created_at.asc())
        )
        if member is None:
            print("Riverside Training has no active staff user to invite students.", file=sys.stderr)
            return 1
        dean = db.get(User, member.user_id)
        if dean is None:
            print("The campus admin user is missing.", file=sys.stderr)
            return 1

        needed = 0
        for spec in STUDENTS:
            open_row = db.scalar(select(InstituteAssignment).where(
                InstituteAssignment.institute_id == institute.id,
                InstituteAssignment.candidate_email == spec["email"],
                InstituteAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
            ))
            if open_row is None:
                needed += 1
        purchased_count = len(db.scalars(
            select(InstituteSeat).where(
                InstituteSeat.institute_id == institute.id, InstituteSeat.status == SeatStatus.PURCHASED
            )
        ).all())
        if needed and purchased_count < needed:
            print(f"Need {needed} open seats, only {purchased_count} available.", file=sys.stderr)
            return 1

        jobs = [_job(db, spec) for spec in JOBS]
        created = 0
        for spec in STUDENTS:
            open_row = db.scalar(select(InstituteAssignment).where(
                InstituteAssignment.institute_id == institute.id,
                InstituteAssignment.candidate_email == spec["email"],
                InstituteAssignment.status.in_(OPEN_ASSIGNMENT_STATUSES),
            ))
            if open_row is None:
                assignment, _temp = institute_service.invite_candidate(
                    db, institute, spec["email"], dean, "Demo campus student",
                    name=spec["name"], phone=spec["phone"],
                )
                created += 1
            else:
                assignment = open_row
            user = db.get(User, assignment.student_user_id) if assignment.student_user_id else None
            if user is None:
                continue
            user.password_hash = hash_password(DEMO_PASSWORD)
            user.is_verified = True
            user.is_active = True
            user.last_login_at = _now() - timedelta(hours=6)
            _ensure_profile(db, user, spec)
            _ensure_apps(db, user, spec, jobs)
            print(f"{spec['name']}  {spec['email']}  assignment={assignment.id}")
        db.commit()
        print(f"\nSeeded {created} new student(s) on {institute.name}.")
        print(f"Student login password: {DEMO_PASSWORD}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
