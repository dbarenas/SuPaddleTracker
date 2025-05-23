from .event import EventBase, EventCreate, EventUpdate, EventRead, EventReadMinimal, EventType
from .event_category import EventCategoryBase, EventCategoryCreate, EventCategoryUpdate, EventCategoryRead, EventCategoryReadMinimal
from .event_distance import EventDistanceBase, EventDistanceCreate, EventDistanceUpdate, EventDistanceRead, EventDistanceReadMinimal
from .strava_user import UserRead
from .race_result import RaceResultBase, RaceResultCreate, RaceResultUpdate, RaceResultRead, RaceResultReadMinimal
from .registration import RegistrationBase, RegistrationCreate, RegistrationUpdate, RegistrationRead, RegistrationReadMinimal, RegistrationStatus
from .virtual_result import VirtualResultBase, VirtualResultCreate, VirtualResultUpdate, VirtualResultRead
from .token import Token # Existing schema

# Update forward references now that all schemas are defined
# This is a common pattern to resolve circular dependencies with Pydantic v2
# Import all schema modules that are involved in relationships or might be referenced
from app.schemas import event, event_category, event_distance, registration, race_result, virtual_result, strava_user

# The EventCategoryRead and EventDistanceRead in event.py are fully defined classes, not string forward refs.
# So, model_rebuild is not strictly needed for them in event.py context if they don't use forward refs themselves.
# However, the prompt asks for these, so they are included.
event.EventCategoryRead.model_rebuild()
event.EventDistanceRead.model_rebuild()

# registration.RegistrationRead uses a locally defined RaceResultReadMinimal which acts like a forward reference.
# This call resolves it after all schemas (including the canonical RaceResultReadMinimal in race_result.py) are loaded.
registration.RegistrationRead.model_rebuild()

# The following are commented out as per the prompt's specification:
# event.EventRead.model_rebuild() # If EventRead had forward refs to Registration etc.
# race_result.RaceResultRead.model_rebuild() # If it had forward refs
# event_category.EventCategoryRead.model_rebuild() # If EventCategoryRead had a forward ref to EventReadMinimal etc.
# event_distance.EventDistanceRead.model_rebuild() # If EventDistanceRead had a forward ref to EventReadMinimal etc.
