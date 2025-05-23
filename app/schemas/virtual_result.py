from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

from app.schemas.strava_user import UserRead # For nesting user info
from app.schemas.event import EventReadMinimal # For nesting event info, if linked

class VirtualResultBase(BaseModel):
    user_strava_id: int
    event_id: Optional[int] = None # If linked to a specific virtual event
    strava_activity_id: str = Field(..., max_length=50)
    name: Optional[str] = Field(None, max_length=150)
    distance_km: float = Field(..., gt=0)
    elapsed_time_seconds: int = Field(..., ge=0)
    activity_date: datetime

class VirtualResultCreate(VirtualResultBase):
    pass

class VirtualResultUpdate(BaseModel):
    # Usually, virtual results are immutable once created from Strava,
    # but some fields might be updatable if necessary (e.g., linking to an event post-creation)
    event_id: Optional[int] = None
    name: Optional[str] = Field(None, max_length=150)


class VirtualResultRead(VirtualResultBase):
    id: int
    user: Optional[UserRead] = None # Nested user information
    event: Optional[EventReadMinimal] = None # Nested event information, if linked
    model_config = {"from_attributes": True}
