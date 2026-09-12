from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database.database import get_db
from app.models.user import User
from app.models.incident import Incident
from app.routers.user import get_current_user

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