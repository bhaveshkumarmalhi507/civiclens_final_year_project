from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID, ST_DWithin
from typing import List

from app.database.database import get_db
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentResponse
from app.routers.user import get_current_user
from app.utils.geocoding import get_area_name
router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"]
)


@router.post("/", response_model=IncidentResponse)
def create_incident(
    incident: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    point = ST_SetSRID(ST_MakePoint(incident.longitude, incident.latitude), 4326)
    area_name = get_area_name(incident.latitude, incident.longitude)
    new_incident = Incident(
        user_id=current_user.id,
        description=incident.description,
        category=incident.category,
        location=point,
        area_name=area_name,
        status="Submitted"
    )

    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)

    # ===== Community Validation Check (FR-06) =====
    distinct_users_count = (
        db.query(func.count(func.distinct(Incident.user_id)))
        .filter(
            Incident.category == new_incident.category,
            ST_DWithin(
                cast(Incident.location, Geography),
                cast(point, Geography),
                500
            )
        )
        .scalar()
    )

    if distinct_users_count >= 3:
        matching_incidents = (
            db.query(Incident)
            .filter(
                Incident.category == new_incident.category,
                ST_DWithin(
                    cast(Incident.location, Geography),
                    cast(point, Geography),
                    500
                )
            )
            .all()
        )

        for inc in matching_incidents:
            inc.status = "Verified"

        db.commit()
        db.refresh(new_incident)

    return new_incident


@router.get("/", response_model=List[IncidentResponse])
def list_incidents(db: Session = Depends(get_db)):
    incidents = db.query(Incident).order_by(Incident.created_at.desc()).all()
    return incidents


@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident