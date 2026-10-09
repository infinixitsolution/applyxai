"""
Admin commands. Run from the project root:

    venv\\Scripts\\python -m backend.app.cli import-history --email you@example.com
    venv\\Scripts\\python -m backend.app.cli import-history --email you@example.com --applied path\\to\\applied.csv --failed path\\to\\failed.csv

import-history copies the classic engine's CSV history into that user's ApplyXAI account.
It's safe to run more than once: a job that's already marked applied is left alone.
Imported rows don't count toward the monthly plan limit.

    venv\\Scripts\\python -m backend.app.cli seed-plans
    venv\\Scripts\\python -m backend.app.cli sync-plans

seed-plans copies the default catalogue (backend/app/core/plans.py) into an empty plans
table. sync-plans also creates each paid plan at the payment provider (PAYMENT_PROVIDER) and
stores its ID, so it can be bought online. Both are safe to repeat.

    venv\\Scripts\\python -m backend.app.cli make-admin --email you@example.com

make-admin gives an existing account admin access (it opens /admin in the web app). Register
and verify the account first. Use --revoke to take admin access away.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import select

from automation.csv_import import read_history
from backend.app.core.database import SessionLocal
from backend.app.models import User
from backend.app.services.ingest_service import ingest_events

BATCH = 500


def _default_paths() -> tuple[str, str]:
    # The engine's own settings, including the classic panel's user_config.json overrides.
    from config.settings import failed_file_name, file_name
    return file_name, failed_file_name


def import_history(email: str, applied: str | None, failed: str | None) -> int:
    default_applied, default_failed = _default_paths()
    applied, failed = applied or default_applied, failed or default_failed
    paths = {name: path for name, path in (("applied", applied), ("failed", failed)) if Path(path).is_file()}
    if not paths:
        print(f"No history found. Looked for:\n  {applied}\n  {failed}", file=sys.stderr)
        return 1
    events = read_history(paths.get("applied"), paths.get("failed"))

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"No ApplyXAI account with the email {email}.", file=sys.stderr)
            return 1
        totals = {"applied": 0, "external": 0, "failed": 0, "skipped": 0}
        for start in range(0, len(events), BATCH):
            result = ingest_events(db, user.id, events[start:start + BATCH], count_usage=False)
            db.commit()
            for key in totals:
                totals[key] += getattr(result, key)

    for name, path in paths.items():
        print(f"Read {name} history: {path}")
    print("Imported {applied} applied, {external} external, {failed} failed, {skipped} skipped rows.".format(**totals))
    return 0


def seed_plans() -> int:
    from backend.app.services.billing_service import seed_plans as seed
    with SessionLocal() as db:
        added = seed(db)
        db.commit()
    print(f"Added {added} plans." if added else "The plans table already has plans; nothing changed.")
    return 0


def sync_plans() -> int:
    from backend.app.services.billing_service import sync_provider_plans
    from backend.app.services.payments import resolve_payment_provider
    with SessionLocal() as db:
        provider = resolve_payment_provider(db)
        if provider.name == "null":
            print("Payments are in test mode. Configure Razorpay under /admin/system → Payments or set PAYMENT_PROVIDER=razorpay in .env.", file=sys.stderr)
            return 1
        created = sync_provider_plans(db, provider)
        db.commit()
    for code, provider_id in created:
        print(f"Created {code}: {provider_id}")
    print(f"Created {len(created)} plans at {provider.name}." if created else "Every paid plan already exists there.")
    return 0


def make_admin(email: str, revoke: bool) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None:
            print(f"No ApplyXAI account with the email {email}. Register it first.", file=sys.stderr)
            return 1
        user.is_admin = not revoke
        db.commit()
    print(f"{user.email} is {'no longer' if revoke else 'now'} an admin.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m backend.app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    admin = commands.add_parser("make-admin", help="Give an existing account admin access")
    admin.add_argument("--email", required=True)
    admin.add_argument("--revoke", action="store_true", help="Take admin access away instead")
    commands.add_parser("seed-plans", help="Copy the default plan catalogue into an empty plans table")
    commands.add_parser("sync-plans", help="Create paid plans at the payment provider")
    history = commands.add_parser("import-history", help="Import the engine's CSV history into an account")
    history.add_argument("--email", required=True)
    history.add_argument("--applied", help="Applied-jobs CSV (default: settings.file_name)")
    history.add_argument("--failed", help="Failed-jobs CSV (default: settings.failed_file_name)")
    args = parser.parse_args(argv)
    if args.command == "import-history":
        return import_history(args.email, args.applied, args.failed)
    if args.command == "seed-plans":
        return seed_plans()
    if args.command == "sync-plans":
        return sync_plans()
    if args.command == "make-admin":
        return make_admin(args.email, args.revoke)
    return 2


if __name__ == "__main__":
    sys.exit(main())
