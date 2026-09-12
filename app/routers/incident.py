from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID, ST_DWithin
from typing import List
from pydantic import BaseModel

from app.database.database import get_db
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentResponse, StatusUpdate
from app.routers.user import get_current_user
from app.utils.geocoding import get_area_name
from app.models.status_history import StatusHistory
from app.websocket.manager import manager

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"]
)

@router.post("/", response_model=IncidentResponse)
async def create_incident(
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
        
        # ===== Real-time Broadcast (FR-08) =====
    await manager.broadcast({
        "id": new_incident.id,
        "description": new_incident.description,
        "category": new_incident.category,
        "area_name": new_incident.area_name,
        "status": new_incident.status,
        "created_at": new_incident.created_at.isoformat()
    })

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


VALID_STATUSES = ["Submitted", "Under Review", "Verified", "In Progress", "Resolved"]


@router.patch("/{incident_id}/status", response_model=IncidentResponse)
def update_status(
    incident_id: int,
    payload: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ("admin", "moderator"):
        raise HTTPException(status_code=403, detail="Only admin or moderator can update status")

    if payload.new_status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of {VALID_STATUSES}")

    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    old_status = incident.status
    incident.status = payload.new_status

    history_entry = StatusHistory(
        incident_id=incident.id,
        old_status=old_status,
        new_status=payload.new_status,
        changed_by=current_user.id,
        note=payload.note
    )

    db.add(history_entry)
    db.commit()
    db.refresh(incident)

    return incident


@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # client se kuch aaye to bas sunte raho (abhi kuch use nahi karna)
    except WebSocketDisconnect:
        manager.disconnect(websocket)