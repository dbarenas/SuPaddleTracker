from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func # For default timestamp
from app.db.base import Base
import enum # Required for RegistrationStatus

class RegistrationStatus(enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed" # e.g. payment received
    CANCELLED = "cancelled"

class Registration(Base):
    __tablename__ = "registrations"

    id = Column(Integer, primary_key=True, index=True)
    user_strava_id = Column(Integer, ForeignKey("strava_users.strava_id"), nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    event_category_id = Column(Integer, ForeignKey("event_categories.id"), nullable=False)
    event_distance_id = Column(Integer, ForeignKey("event_distances.id"), nullable=False)
    
    payment_proof_url = Column(String, nullable=True)
    # Using string for status as per the updated requirement
    status = Column(String, default=RegistrationStatus.PENDING.value, nullable=False) 
    registered_at = Column(DateTime(timezone=True), server_default=func.now())


    # Relationships
    user = relationship("StravaUserDB", back_populates="registrations")
    event = relationship("Event", back_populates="registrations")
    category = relationship("EventCategory", back_populates="registrations")
    distance = relationship("EventDistance", back_populates="registrations")
    race_result = relationship("RaceResult", back_populates="registration", uselist=False, cascade="all, delete-orphan")
