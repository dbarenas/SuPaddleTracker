from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class EventDistance(Base):
    __tablename__ = "event_distances"

    id = Column(Integer, primary_key=True, index=True)
    distance_km = Column(Float, nullable=False)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)

    # Relationships
    event = relationship("Event", back_populates="distances")
    registrations = relationship("Registration", back_populates="distance", cascade="all, delete-orphan")
