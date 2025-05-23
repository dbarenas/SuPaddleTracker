from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class RaceResult(Base):
    __tablename__ = "race_results"

    id = Column(Integer, primary_key=True, index=True)
    registration_id = Column(Integer, ForeignKey("registrations.id"), unique=True, nullable=False)
    dorsal_number = Column(Integer, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=True)
    finish_time = Column(DateTime(timezone=True), nullable=True)
    net_time_seconds = Column(Integer, nullable=True) # Store duration in seconds for easy calculation

    # Relationship
    registration = relationship("Registration", back_populates="race_result")
