from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# This is for reading user info in other schemas, not the full StravaUser model from models/strava_user.py
class UserRead(BaseModel):
    strava_id: int
    username: Optional[str] = None
    firstname: Optional[str] = None
    lastname: Optional[str] = None
    profile_picture_url: Optional[str] = None
    model_config = {"from_attributes": True}
