from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

# Import RegistrationReadMinimal for nesting
from app.schemas.registration import RegistrationReadMinimal 

class RaceResultBase(BaseModel):
    registration_id: int
    dorsal_number: Optional[int] = Field(None, ge=1)
    start_time: Optional[datetime] = None
    finish_time: Optional[datetime] = None
    net_time_seconds: Optional[int] = Field(None, ge=0) # Duration

class RaceResultCreate(RaceResultBase):
    # For creation, we might only need registration_id, other fields set later
    pass

class RaceResultUpdate(BaseModel):
    dorsal_number: Optional[int] = Field(None, ge=1)
    start_time: Optional[datetime] = None
    finish_time: Optional[datetime] = None
    net_time_seconds: Optional[int] = Field(None, ge=0)

class RaceResultRead(RaceResultBase):
    id: int
    registration: Optional[RegistrationReadMinimal] = None # Embed RegistrationReadMinimal
    model_config = {"from_attributes": True}

# This schema is defined here as per the content for race_result.py and for __init__.py to import.
# The registration.py file defines its own internal one for forward referencing.
class RaceResultReadMinimal(BaseModel):
    id: int
    dorsal_number: Optional[int] = None
    net_time_seconds: Optional[int] = None
    model_config = {"from_attributes": True}
