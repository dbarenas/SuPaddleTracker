from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class VirtualResult(Base):
    __tablename__ = "virtual_results"

    id = Column(Integer, primary_key=True, index=True)
    user_strava_id = Column(Integer, ForeignKey("strava_users.strava_id"), nullable=False)
    # Link to an event if this virtual activity is part of a specific virtual event
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True) 
    strava_activity_id = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True) # Name of the activity from Strava
    distance_km = Column(Float, nullable=False)
    elapsed_time_seconds = Column(Integer, nullable=False) # Duration in seconds
    activity_date = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    user = relationship("StravaUserDB", back_populates="virtual_results")
    event = relationship("Event", back_populates="virtual_results") # If linked to a specific event
