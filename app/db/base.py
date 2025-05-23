# app/db/base.py
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models here so that Base has them registered:
# This is crucial for Base.metadata.create_all(engine) to work correctly.
# It also helps tools like Alembic to detect the models.

from app.models.strava_user import StravaUserDB
from app.models.event import Event
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.registration import Registration
from app.models.race_result import RaceResult
from app.models.virtual_result import VirtualResult
