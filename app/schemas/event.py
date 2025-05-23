from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.models.event import EventType # Import the enum

# Forward references for relationships
class EventCategoryRead(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}

class EventDistanceRead(BaseModel):
    id: int
    distance_km: float
    model_config = {"from_attributes": True}

class EventBase(BaseModel):
    name: str = Field(..., min_length=3, max_length=100)
    location: Optional[str] = Field(None, max_length=150)
    type: EventType
    date: datetime
    strava_sync_enabled: bool = False

class EventCreate(EventBase):
    pass

class EventUpdate(EventBase):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    location: Optional[str] = Field(None, max_length=150) # Added location to update
    type: Optional[EventType] = None
    date: Optional[datetime] = None
    strava_sync_enabled: Optional[bool] = None

class EventRead(EventBase):
    id: int
    categories: List[EventCategoryRead] = []
    distances: List[EventDistanceRead] = []
    model_config = {"from_attributes": True}

# Minimal schema for use in other schemas to avoid circular deps
class EventReadMinimal(BaseModel):
    id: int
    name: str
    date: datetime
    type: EventType
    model_config = {"from_attributes": True}
