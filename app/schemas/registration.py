from pydantic import BaseModel, Field
from typing import Optional, List # List was missing for RegistrationRead's potential list fields if any
from datetime import datetime
from app.models.registration import RegistrationStatus # Import the enum

# Import minimal schemas to break circular dependencies
from app.schemas.event import EventReadMinimal
from app.schemas.event_category import EventCategoryReadMinimal
from app.schemas.event_distance import EventDistanceReadMinimal
from app.schemas.strava_user import UserRead 

# Forward reference for RaceResultReadMinimal defined locally
class RaceResultReadMinimal(BaseModel):
    id: int
    dorsal_number: Optional[int] = None
    net_time_seconds: Optional[int] = None
    model_config = {"from_attributes": True}


class RegistrationBase(BaseModel):
    user_strava_id: int
    event_id: int
    event_category_id: int
    event_distance_id: int
    payment_proof_url: Optional[str] = Field(None, max_length=255)
    status: RegistrationStatus = RegistrationStatus.PENDING

class RegistrationCreate(RegistrationBase):
    pass

class RegistrationUpdate(BaseModel):
    payment_proof_url: Optional[str] = Field(None, max_length=255)
    status: Optional[RegistrationStatus] = None

class RegistrationRead(RegistrationBase):
    id: int
    registered_at: datetime
    user: Optional[UserRead] = None # Nested user info
    event: Optional[EventReadMinimal] = None # Nested event info
    category: Optional[EventCategoryReadMinimal] = None # Nested category info
    distance: Optional[EventDistanceReadMinimal] = None # Nested distance info
    race_result: Optional[RaceResultReadMinimal] = None # Nested race result
    model_config = {"from_attributes": True}

# This is the key schema for results display via RaceResultRead
class RegistrationReadMinimal(BaseModel):
    id: int
    # user_strava_id: int # Can be omitted if UserRead contains strava_id
    user: Optional[UserRead] = None # Embed UserRead here
    # status: RegistrationStatus # Status might not be needed for public result display
    model_config = {"from_attributes": True}
