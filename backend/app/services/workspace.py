"""Resolve the signed-in user's workspace from membership, not a users.role column."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Institute, InstituteMember, InstituteStatus, Partner, PartnerStatus, User


def workspace_for(db: Session, user: User) -> dict:
    if user.is_admin:
        return {
            "workspace": "admin",
            "institute_id": None,
            "partner_id": None,
            "institute_status": None,
            "partner_status": None,
        }

    member = db.execute(
        select(InstituteMember, Institute)
        .join(Institute, Institute.id == InstituteMember.institute_id)
        .where(
            InstituteMember.user_id == user.id,
            InstituteMember.status == "active",
            Institute.status != InstituteStatus.CLOSED,
        )
        .order_by(Institute.created_at.desc())
        .limit(1)
    ).first()
    if member is not None:
        _membership, institute = member
        return {
            "workspace": "institute",
            "institute_id": institute.id,
            "partner_id": None,
            "institute_status": institute.status.value,
            "partner_status": None,
        }

    partner = db.scalar(select(Partner).where(Partner.user_id == user.id))
    if partner is not None and partner.status != PartnerStatus.CLOSED:
        return {
            "workspace": "partner",
            "institute_id": None,
            "partner_id": partner.id,
            "institute_status": None,
            "partner_status": partner.status.value,
        }

    return {
        "workspace": "app",
        "institute_id": None,
        "partner_id": None,
        "institute_status": None,
        "partner_status": None,
    }


def user_payload(db: Session, user: User) -> dict:
    from backend.app.schemas.auth import UserOut

    base = UserOut.model_validate(user).model_dump(mode="json")
    ws = workspace_for(db, user)
    if ws["institute_id"] is not None:
        ws["institute_id"] = str(ws["institute_id"])
    if ws["partner_id"] is not None:
        ws["partner_id"] = str(ws["partner_id"])
    base.update(ws)
    return base
