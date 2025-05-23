from pydantic import BaseModel, Field
from typing import Optional

# Avoid direct import of EventRead to prevent circular dependency
# from app.schemas.event import EventReadMinimal 

class EventCategoryBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=50)
    event_id: int

class EventCategoryCreate(EventCategoryBase):
    pass

class EventCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=50)
    # event_id is usually not updatable for a category, 
    # instead, one might delete and recreate under a new event.

class EventCategoryRead(EventCategoryBase):
    id: int
    # event: Optional[EventReadMinimal] = None # Example if nesting event info
    model_config = {"from_attributes": True}

class EventCategoryReadMinimal(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}
