# This file can remain relatively simple, just importing models to make them accessible.
# Or it can be used by Alembic if it's configured to look here.
# For now, ensure that when Base.metadata.create_all() is called, these models are known.

from .strava_user import StravaUserDB # Existing model
from .event import Event, EventType
from .event_category import EventCategory
from .event_distance import EventDistance
from .registration import Registration, RegistrationStatus
from .race_result import RaceResult
from .virtual_result import VirtualResult

# It's also good practice to ensure that related models have their relationships defined correctly.
# For example, StravaUserDB might need a 'registrations' and 'virtual_results' relationship.

# Add to app/models/strava_user.py, within the StravaUserDB class:
# registrations = relationship("Registration", back_populates="user")
# virtual_results = relationship("VirtualResult", back_populates="user")
