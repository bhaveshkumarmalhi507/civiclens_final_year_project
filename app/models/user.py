from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.database.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(100), nullable=False)

    email = Column(String(150), unique=True, nullable=False, index=True)

    password = Column(String(255), nullable=False)

    phone = Column(String(20), nullable=True)

    city = Column(String(100), nullable=True)

    role = Column(String(20), default="citizen")

    profile_image = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)