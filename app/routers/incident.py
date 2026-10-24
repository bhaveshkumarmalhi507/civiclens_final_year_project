from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import func, cast
from geoalchemy2 import Geography
from geoalchemy2.functions import ST_MakePoint, ST_SetSRID, ST_DWithin
from typing import List
from pydantic import BaseModel
from app.services.priority_engine import calculate_priority_score
from app.services.notification_service import notify_matching_users
from app.services.validation_service import validate_and_rank

from fastapi import Query
from app.database.database import get_db
from app.models.incident import Incident
from app.models.user import User
from app.schemas.incident import IncidentCreate, IncidentResponse, StatusUpdate, StatusHistoryResponse
from app.routers.user import get_current_user
from app.utils.geocoding import get_area_name
from app.models.status_history import StatusHistory
from app.websocket.manager import manager
from fastapi import UploadFile, File, Form
import os
import uuid
import shutil

router = APIRouter(
    prefix="/incidents",
    tags=["Incidents"]
)
# =========================
# Incident Creation & Listing
# =========================
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

# Save initial status history
    initial_history = StatusHistory(
       incident_id=new_incident.id,
       old_status=None,
       new_status="Submitted",
       changed_by=current_user.id,
       note="Incident submitted"
   )

    db.add(initial_history)
    db.commit()

    
    # ===== Community Validation Check (FR-06) =====
    validate_and_rank(db, new_incident, point)
# Send notifications to users with matching preferences
    try:
        notify_matching_users(db, new_incident)
    except Exception as e:
      print(f"[Notification Error]: {e}")

    await manager.broadcast({
        "id": new_incident.id,
        "description": new_incident.description,
        "category": new_incident.category,
        "area_name": new_incident.area_name,
        "status": new_incident.status,
        "created_at": new_incident.created_at.isoformat()
    })

    return new_incident

# =========================
# Incident Listing
# =========================

@router.get("/", response_model=List[IncidentResponse])
def list_incidents(
    category: str | None = None,
    area: str | None = None,
    priority: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    query = db.query(Incident)

    # Filter by incident category
    if category:
        query = query.filter(Incident.category == category)

    # Filter by area name
    if area:
        query = query.filter(Incident.area_name.ilike(f"%{area}%"))

    # Filter by priority tier
    if priority:
        query = query.filter(
            Incident.priority_tier.ilike(priority)
        )

    # Highest priority first, newest reports first for ties
    query = query.order_by(
        Incident.priority_score.desc().nullslast(),
        Incident.created_at.desc()
    )

    return query.offset(skip).limit(limit).all()


#=========================
#my-reports endpoint for users to see their own reports
#=========================
@router.get("/my-reports", response_model=List[IncidentResponse])
def get_my_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incidents = (
        db.query(Incident)
        .filter(Incident.user_id == current_user.id)
        .order_by(Incident.created_at.desc())
        .all()
    )
    return incidents

#=========================
# Incident Heatmap Data (FR-13)
#=========================
@router.get("/heatmap")
def get_incident_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incidents = db.query(Incident).filter(
        Incident.location.isnot(None)
    ).all()

    heatmap_data = []

    for incident in incidents:
        if incident.latitude is not None and incident.longitude is not None:
            heatmap_data.append({
                "id": incident.id,
                "latitude": incident.latitude,
                "longitude": incident.longitude,
                "category": incident.category,
                "priority": incident.priority_tier,
                "status": incident.status
            })

    return heatmap_data

#=========================
# Incident Status Update & History
#=========================
@router.get("/{incident_id}", response_model=IncidentResponse)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident

#=========================
# Incident Status History
#=========================
@router.get(
    "/{incident_id}/history",
    response_model=List[StatusHistoryResponse]
)
def get_incident_status_history(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Check whether the incident exists
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id)
        .first()
    )

    if not incident:
        raise HTTPException(
            status_code=404,
            detail="Incident not found"
        )

    # Fetch status history from oldest to newest
    history = (
        db.query(StatusHistory)
        .filter(StatusHistory.incident_id == incident_id)
        .order_by(StatusHistory.changed_at.asc())
        .all()
    )

    return history


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

#=========================
# WebSocket for Real-time Feed
#=========================
@router.websocket("/ws/feed")
async def websocket_feed(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()   # client se kuch aaye to bas sunte raho (abhi kuch use nahi karna)
    except WebSocketDisconnect:
        manager.disconnect(websocket)


#==================
# Incident Upload with Image/Video (FR-04)
#==================
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp"
}

ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/webm"
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024    # 5 MB
MAX_VIDEO_SIZE = 25 * 1024 * 1024  # 25 MB

@router.post("/upload", response_model=IncidentResponse)
async def create_incident_with_image(
    description: str = Form(...),
    category: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    image: UploadFile = File(None),
    video: UploadFile = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not image and not video:
        raise HTTPException(status_code=400, detail="At least one of image or video is required")


    # Validate image type and size
    if image:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Unsupported image type. Use JPEG, PNG, or WEBP."
            )

        image.file.seek(0, 2)
        image_size = image.file.tell()
        image.file.seek(0)

        if image_size > MAX_IMAGE_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Image size must not exceed 5 MB."
            )

    # Validate video type and size
    if video:
        if video.content_type not in ALLOWED_VIDEO_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Unsupported video type. Use MP4 or WEBM."
            )

        video.file.seek(0, 2)
        video_size = video.file.tell()
        video.file.seek(0)

        if video_size > MAX_VIDEO_SIZE:
            raise HTTPException(
                status_code=400,
                detail="Video size must not exceed 25 MB."
            )

    image_path = None
    video_path = None

    if image:
        ext = image.filename.split(".")[-1]
        image_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{ext}")
        with open(image_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)

    if video:
        ext = video.filename.split(".")[-1]
        video_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{ext}")
        with open(video_path, "wb") as buffer:
            shutil.copyfileobj(video.file, buffer)

    point = ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    area_name = get_area_name(latitude, longitude)

    new_incident = Incident(
        user_id=current_user.id,
        description=description,
        category=category,
        location=point,
        area_name=area_name,
        image_url=image_path,
        video_url=video_path,
        status="Submitted"
    )

    db.add(new_incident)
    db.commit()
    db.refresh(new_incident)

    # Save initial status history for uploaded incident
    initial_history = StatusHistory(
        incident_id=new_incident.id,
        old_status=None,
        new_status="Submitted",
        changed_by=current_user.id,
        note="Incident submitted"
    )

    db.add(initial_history)
    db.commit()

    # Community Validation + Priority Score + BREAKING notification
    validate_and_rank(db, new_incident, point)
   
    # Send notifications to users with matching preferences
    try:
        notify_matching_users(db, new_incident)
    except Exception as e:
       print(f"[Notification Error]: {e}")

    await manager.broadcast({
        "id": new_incident.id,
        "description": new_incident.description,
        "category": new_incident.category,
        "area_name": new_incident.area_name,
        "status": new_incident.status,
        "created_at": new_incident.created_at.isoformat()
    })

    return new_incident
#=========================
# Incident Deletion (FR-12)
#=========================
@router.delete("/{incident_id}")
def delete_incident(
    incident_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    incident = db.query(Incident).filter(Incident.id == incident_id).first()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    if incident.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized to delete this report")

    if incident.status != "Submitted" and current_user.role != "admin":
        raise HTTPException(status_code=400, detail="Cannot cancel a report that is already being processed")

    db.delete(incident)
    db.commit()
    return {"message": "Incident deleted successfully"}
