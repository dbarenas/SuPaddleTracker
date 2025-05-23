from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum as SQLAlchemyEnum
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class EventType(enum.Enum):
    ON_SITE = "on-site"
    VIRTUAL = "virtual"

class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    location = Column(String, nullable=True) # Nullable for virtual events
    type = Column(SQLAlchemyEnum(EventType), nullable=False)
    date = Column(DateTime, nullable=False)
    # is_virtual is implicitly defined by 'type', can be a hybrid_property if needed for easier querying later
    strava_sync_enabled = Column(Boolean, default=False, nullable=False)

    # Relationships
    categories = relationship("EventCategory", back_populates="event", cascade="all, delete-orphan")
    distances = relationship("EventDistance", back_populates="event", cascade="all, delete-orphan")
    registrations = relationship("Registration", back_populates="event", cascade="all, delete-orphan")
    # For virtual events that might store general virtual results not tied to a specific registration
    virtual_results = relationship("VirtualResult", back_populates="event", cascade="all, delete-orphan")
