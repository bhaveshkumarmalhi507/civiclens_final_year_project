from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.database import get_db
from app.models.user import User
from app.models.incident import Incident
from app.routers.user import get_current_user
from app.schemas.incident import IncidentResponse
from typing import List

router = APIRouter(
    prefix="/admin",
    tags=["Admin"]
)


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "full_name": u.full_name,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active
        }
        for u in users
    ]


@router.patch("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_active = False
    db.commit()
    return {"message": f"User {user.email} deactivated"}


@router.get("/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    total_incidents = db.query(func.count(Incident.id)).scalar()
    verified_count = db.query(func.count(Incident.id)).filter(Incident.status == "Verified").scalar()
    resolved_count = db.query(func.count(Incident.id)).filter(Incident.status == "Resolved").scalar()

    category_counts = (
        db.query(Incident.category, func.count(Incident.id))
        .group_by(Incident.category)
        .all()
    )

    return {
        "total_incidents": total_incidents,
        "verified": verified_count,
        "resolved": resolved_count,
        "by_category": {cat: count for cat, count in category_counts}
    }

def require_moderator_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Moderator or admin access required")
    return current_user


@router.get("/flagged-incidents", response_model=List[IncidentResponse])
def get_flagged_incidents(
    db: Session = Depends(get_db),
    moderator: User = Depends(require_moderator_or_admin)
):
    incidents = db.query(Incident).filter(Incident.is_flagged == True).all()
    return incidents


class HeadlineUpdate(BaseModel):
    title: str


@router.patch("/incidents/{incident_id}/headline")
def edit_headline(
    incident_id: int,
    payload: HeadlineUpdate,
    db: Session = Depends(get_db),
    moderator: User = Depends(require_moderator_or_admin)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    incident.title = payload.title
    db.commit()
    return {"message": "Headline updated successfully"}