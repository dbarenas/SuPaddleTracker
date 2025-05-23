from pydantic import BaseModel, Field
from typing import Optional

# from app.schemas.event import EventReadMinimal # For nesting event info

class EventDistanceBase(BaseModel):
    distance_km: float = Field(..., gt=0)
    event_id: int

class EventDistanceCreate(EventDistanceBase):
    pass

class EventDistanceUpdate(BaseModel):
    distance_km: Optional[float] = Field(None, gt=0)
    # event_id is usually not updatable

class EventDistanceRead(EventDistanceBase):
    id: int
    # event: Optional[EventReadMinimal] = None # Example if nesting event info
    model_config = {"from_attributes": True}

class EventDistanceReadMinimal(BaseModel):
    id: int
    distance_km: float
    model_config = {"from_attributes": True}
