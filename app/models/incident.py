from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from geoalchemy2 import Geometry
from datetime import datetime

from app.database.database import Base


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String(200), nullable=True)          # AI headline baad mein yahan aayega
    description = Column(Text, nullable=False)           # citizen ka text
    category = Column(String(50), nullable=True)         # road, fire, flood, crime etc.
    image_url = Column(String(255), nullable=True)

    area_name = Column(String(150), nullable=True)        # Nominatim se aayega (FR-05)
    location = Column(Geometry(geometry_type="POINT", srid=4326), nullable=False)  # GPS point

    severity_score = Column(String(20), nullable=True)    # Asadullah ke NLP se aayega
    priority_score = Column(Integer, nullable=True)        # tumhara ranking engine calculate karega
    priority_tier = Column(String(20), nullable=True)      # BREAKING/HIGH/MEDIUM/LOW

    status = Column(String(30), default="Submitted")       # FR-11: Submitted -> Verified -> Resolved

    created_at = Column(DateTime, default=datetime.utcnow)

    ai_confidence = Column(Integer, nullable=True)   # 0-100, AI se aayega
    is_flagged = Column(Boolean, default=False)      # low confidence par True ho jayega