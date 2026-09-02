from sqlalchemy import Column, Integer, ForeignKey, DateTime, String
from sqlalchemy.dialects.postgresql import ARRAY
from datetime import datetime

from app.database.database import Base


class UserPreference(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    preferred_areas = Column(ARRAY(String), default=[])
    preferred_categories = Column(ARRAY(String), default=[])

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)