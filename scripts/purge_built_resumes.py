#!/usr/bin/env python3
"""Remove built resume rows (AI / automation / styled) for one user; keep master uploads.

Run from project root:
  python scripts/purge_built_resumes.py --email user@example.com
  python scripts/purge_built_resumes.py --email user@example.com --keep-single-master
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models import User
from backend.app.models.resume import Resume
from backend.app.services import resume_service

BUILT_GENERATORS = frozenset({"ai", "automation", "style"})


def is_built(resume: Resume) -> bool:
    by = str((resume.ai_metadata or {}).get("generated_by") or "").lower()
    return by in BUILT_GENERATORS


def pick_master(uploads: list[Resume]) -> Resume | None:
    if not uploads:
        return None
    default = [r for r in uploads if r.is_default]
    if len(default) == 1:
        return default[0]
    if default:
        return default[0]
    with_skills = [r for r in uploads if r.master_skills]
    if with_skills:
        return max(with_skills, key=lambda r: len(r.master_skills or []))
    return min(uploads, key=lambda r: r.created_at)


def main() -> None:
    parser = argparse.ArgumentParser(description="Purge built resumes for a user account.")
    parser.add_argument("--email", required=True, help="User login email")
    parser.add_argument(
        "--keep-single-master",
        action="store_true",
        help="After removing built copies, delete extra uploaded resumes and keep one master.",
    )
    parser.add_argument("--dry-run", action="store_true", help="List actions without deleting")
    args = parser.parse_args()

    email = args.email.strip().lower()
    engine = create_engine(str(settings.DATABASE_URL))

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"No user with email {email!r}")
            sys.exit(1)

        rows = list(db.scalars(select(Resume).where(Resume.user_id == user.id)).all())
        built = [r for r in rows if is_built(r)]
        uploads = [r for r in rows if not is_built(r)]

        print(f"User {user.email} ({user.id}): {len(rows)} total, {len(built)} built, {len(uploads)} uploads")

        to_delete: list[Resume] = list(built)
        master: Resume | None = None

        if args.keep_single_master and uploads:
            master = pick_master(uploads)
            to_delete.extend(r for r in uploads if r.id != master.id)
            if master and not master.is_default:
                print(f"Will set default master: {master.name!r} ({master.id})")

        for r in sorted(to_delete, key=lambda x: x.created_at):
            gb = (r.ai_metadata or {}).get("generated_by")
            print(f"  delete: {r.name!r} gen={gb!r} id={r.id}")

        if args.dry_run:
            print("Dry run — no changes.")
            return

        for r in to_delete:
            resume_service.delete_resume(db, user, r.id)

        if args.keep_single_master and master is not None and not master.is_default:
            resume_service.set_default(db, user, master.id)

        remaining = db.scalars(select(Resume).where(Resume.user_id == user.id)).all()
        print(f"Done. Deleted {len(to_delete)}. {len(remaining)} resume(s) left.")
        for r in remaining:
            print(f"  kept: {r.name!r} default={r.is_default} id={r.id}")


if __name__ == "__main__":
    main()
