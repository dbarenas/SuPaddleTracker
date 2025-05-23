from datetime import datetime
from typing import Optional

from pydantic import BaseModel # Field removed as it's not used in the current models
from sqlalchemy import Column, Integer, String, DateTime # func removed
from sqlalchemy.orm import relationship # Added for relationships
# from sqlalchemy.sql import func # For default/onupdate server-side timestamps if preferred - kept commented for reference

from app.db.base import Base # Import Base from the previously created file

# Pydantic Models

class StravaTokenData(BaseModel):
    access_token: str
    expires_at: int  # Timestamp
    expires_in: int  # Seconds
    refresh_token: str
    token_type: str  # e.g., "Bearer"

class StravaAthleteData(BaseModel):
    id: int
    username: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    bio: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    sex: Optional[str] = None
    profile_medium: Optional[str] = None  # profile picture
    profile: Optional[str] = None  # larger profile picture

class StravaUserBase(BaseModel):
    strava_id: int
    username: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    profile_picture_url: Optional[str] = None

class StravaUserCreate(StravaUserBase):
    # No additional fields needed for creation beyond what's in StravaUserBase
    pass

class StravaUser(StravaUserBase):
    id: int  # Local DB id
    created_at: datetime
    last_login_at: datetime

    model_config = {"from_attributes": True}


# SQLAlchemy Model

class StravaUserDB(Base):
    __tablename__ = "strava_users"

    # Using SQLAlchemy 2.0 style type hints
    id: int = Column(Integer, primary_key=True, index=True)
    strava_id: int = Column(Integer, unique=True, index=True, nullable=False)
    username: Optional[str] = Column(String, index=True, nullable=True)
    firstname: Optional[str] = Column(String, nullable=True)
    lastname: Optional[str] = Column(String, nullable=True)
    profile_picture_url: Optional[str] = Column(String, nullable=True)
    
    encrypted_access_token: str = Column(String, nullable=False)
    encrypted_refresh_token: str = Column(String, nullable=False)
    token_expires_at: datetime = Column(DateTime, nullable=False)
    scope: Optional[str] = Column(String, nullable=True)

    created_at: datetime = Column(DateTime, default=datetime.utcnow)
    # onupdate=datetime.utcnow for SQLAlchemy often requires more setup or is handled at app level.
    # It's kept here as per instruction but might need adjustment later.
    last_login_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    registrations = relationship("Registration", back_populates="user", cascade="all, delete-orphan")
    virtual_results = relationship("VirtualResult", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<StravaUserDB(id={self.id}, strava_id={self.strava_id}, username='{self.username}')>"
