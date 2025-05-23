from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload # For eager loading
from typing import List, Optional

# Models
from app.models.event import Event, EventType # EventType needed for EventCreate, but not directly used in service functions here
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance

# Schemas
from app.schemas.event import EventCreate, EventRead
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
        .options(joinedload(Event.categories), joinedload(Event.distances))
        .where(Event.id == event_id)
    )
    result = await db.execute(stmt)
    db_event = result.scalar_one_or_none()
    if db_event:
        return EventRead.model_validate(db_event)
    return None

async def get_events(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[EventRead]:
    stmt = (
        select(Event)
        .options(joinedload(Event.categories), joinedload(Event.distances))
        .offset(skip)
        .limit(limit)
        .order_by(Event.date.desc()) # Example ordering
    )
    result = await db.execute(stmt)
    db_events = result.scalars().all()
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
