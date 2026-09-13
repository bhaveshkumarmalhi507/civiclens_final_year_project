from pydantic import BaseModel
from datetime import datetime
from enum import Enum


class IncidentCategory(str, Enum):
    roads = "Roads"
    fire = "Fire"
    flooding = "Flooding"
    crime = "Crime"
    water_supply = "Water Supply"


class IncidentCreate(BaseModel):
    description: str
    category: IncidentCategory
    latitude: float
    longitude: float


class IncidentResponse(BaseModel):
    id: int
    user_id: int
    title: str | None
    description: str
    category: str | None
    area_name: str | None
    image_url: str | None
    video_url: str | None
    status: str
    priority_score: int | None
    priority_tier: str | None
    created_at: datetime

    class Config:
        from_attributes = True

class StatusUpdate(BaseModel):
    new_status: str
    note: str | None = None
