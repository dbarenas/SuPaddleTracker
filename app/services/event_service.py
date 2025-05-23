from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select # Added func
from sqlalchemy.orm import joinedload # For eager loading
from typing import List, Optional, Dict # Added Dict
from collections import defaultdict # Added defaultdict

# Models
from app.models.event import Event, EventType
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.registration import Registration # Added Registration
from app.models.strava_user import StravaUserDB # Added StravaUserDB

# Schemas
from app.schemas.event import EventCreate, EventRead, EventUpdate
from app.schemas.event_category import EventCategoryCreate, EventCategoryRead
from app.schemas.event_distance import EventDistanceCreate, EventDistanceRead

async def create_event(db: AsyncSession, event_data: EventCreate) -> EventRead:
    db_event = Event(**event_data.model_dump())
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event, attribute_names=['categories', 'distances']) # Refresh to get relationships
    return EventRead.model_validate(db_event)

async def get_event(db: AsyncSession, event_id: int) -> Optional[EventRead]:
    stmt = (
        select(Event)
        .options(
            joinedload(Event.categories),
            joinedload(Event.distances)
        )
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    db_event = result.unique().scalar_one_or_none()
    if db_event:
        return EventRead.model_validate(db_event)
    return None

async def get_events(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[EventRead]:
    stmt = (
        select(Event)
        .options(
            joinedload(Event.categories),
            joinedload(Event.distances)
        )
        .order_by(Event.date.desc()) # Example ordering
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    db_events = result.unique().scalars().all()
    return [EventRead.model_validate(db_event) for db_event in db_events]

async def add_category_to_event(db: AsyncSession, category_data: EventCategoryCreate) -> EventCategoryRead:
    # Ensure event exists
    event_exists = await db.get(Event, category_data.event_id)
    if not event_exists:
        raise ValueError(f"Event with id {category_data.event_id} not found.")

    db_category = EventCategory(**category_data.model_dump())
    db.add(db_category)
    await db.commit()
    await db.refresh(db_category)
    return EventCategoryRead.model_validate(db_category)

async def get_event_categories(db: AsyncSession, event_id: int) -> List[EventCategoryRead]:
    stmt = select(EventCategory).where(EventCategory.event_id == event_id)
    result = await db.execute(stmt)
    db_categories = result.scalars().all()
    return [EventCategoryRead.model_validate(cat) for cat in db_categories]

async def add_distance_to_event(db: AsyncSession, distance_data: EventDistanceCreate) -> EventDistanceRead:
    # Ensure event exists
    event_exists = await db.get(Event, distance_data.event_id)
    if not event_exists:
        raise ValueError(f"Event with id {distance_data.event_id} not found.")

    db_distance = EventDistance(**distance_data.model_dump())
    db.add(db_distance)
    await db.commit()
    await db.refresh(db_distance)
    return EventDistanceRead.model_validate(db_distance)

async def get_event_distances(db: AsyncSession, event_id: int) -> List[EventDistanceRead]:
    stmt = select(EventDistance).where(EventDistance.event_id == event_id)
    result = await db.execute(stmt)
    db_distances = result.scalars().all()
    return [EventDistanceRead.model_validate(dist) for dist in db_distances]

async def update_event(
    db: AsyncSession, event_id: int, event_data: EventUpdate
) -> Optional[EventRead]:
    db_event = await db.get(Event, event_id)
    if not db_event:
        return None

    update_data = event_data.model_dump(exclude_unset=True) # Get only fields that were set
    
    for key, value in update_data.items():
        setattr(db_event, key, value)
    
    # The EventUpdate schema has date as Optional[datetime].
    # The form sends a date string, router converts to date object, then to datetime.
    # So, event_data.date should be datetime if provided and set.

    await db.commit()
    # Refresh to ensure relationships like categories and distances are correctly loaded
    # if they were part of the EventRead schema and potentially affected by changes (though not directly here).
    await db.refresh(db_event, attribute_names=['categories', 'distances']) 
    return EventRead.model_validate(db_event)

async def get_event_participant_counts(
    db: AsyncSession, event_id: int
) -> Dict[str, Dict[str, int]]:
    """
    Calculates participant counts for an event, grouped by category and gender.
    Counts are based on all registrations for the event.
    """
    stmt = (
        select(
            EventCategory.name,
            StravaUserDB.sex,
            func.count(Registration.id).label("count")
        )
        .select_from(Registration)
        .join(EventCategory, Registration.event_category_id == EventCategory.id)
        .join(StravaUserDB, Registration.user_strava_id == StravaUserDB.strava_id)
        .where(Registration.event_id == event_id)
        .group_by(EventCategory.name, StravaUserDB.sex)
    )
    
    results = await db.execute(stmt)
    raw_counts = results.all()

    participant_counts: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in raw_counts:
        category_name = row[0] 
        sex = row[1]           
        count = row[2]         

        gender_key = "Unspecified"
        if sex == "Male":
            gender_key = "Male"
        elif sex == "Female":
            gender_key = "Female"
        
        participant_counts[category_name][gender_key] += count
            
    return dict(participant_counts)
