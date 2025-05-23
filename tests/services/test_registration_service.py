import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # For checking DB state
from datetime import datetime, timezone, timedelta # Added timedelta

from app.services.registration_service import create_registration
from app.schemas.registration import RegistrationCreate, RegistrationRead
from app.models.strava_user import StravaUserDB
from app.models.event import Event, EventType
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.registration import Registration
from app.models.race_result import RaceResult

@pytest.fixture
async def setup_event_data(db_session: AsyncSession):
    # Create a user
    user = StravaUserDB(
        strava_id=111222, username="reg_tester", firstname="Reg", lastname="Tester",
        encrypted_access_token="dummy_token", encrypted_refresh_token="dummy_refresh",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=1)
    )
    db_session.add(user)
    
    # Create an event
    event = Event(
        name="Test Registration Event", type=EventType.ON_SITE, 
        date=datetime.now(timezone.utc), strava_sync_enabled=False
    )
    db_session.add(event)
    await db_session.flush() # Flush to get IDs for event

    # Create category and distance for the event
    category = EventCategory(name="Elite", event_id=event.id)
    distance = EventDistance(distance_km=10.0, event_id=event.id)
    db_session.add_all([category, distance])
    
    await db_session.commit()
    # It's good practice to refresh objects if their state might change due to DB triggers
    # or if relationships need to be immediately accessible after commit via the same instance.
    # For these tests, direct re-fetching or using returned schema data is often sufficient.
    # However, refreshing here aligns with the prompt's structure.
    await db_session.refresh(user)
    await db_session.refresh(event)
    await db_session.refresh(category)
    await db_session.refresh(distance)
    
    return user, event, category, distance

@pytest.mark.asyncio
async def test_create_registration_success(db_session: AsyncSession, setup_event_data):
    # Arrange
    user, event, category, distance = setup_event_data
    
    registration_data = RegistrationCreate(
        user_strava_id=user.strava_id, # This field is in schema
        event_id=event.id,
        event_category_id=category.id,
        event_distance_id=distance.id
    )

    # Act
    # The service function create_registration takes user_strava_id as a separate parameter
    created_reg_schema = await create_registration(
        db=db_session, 
        user_strava_id=user.strava_id, 
        registration_data=registration_data
    )

    # Assert - Schema
    assert isinstance(created_reg_schema, RegistrationRead)
    assert created_reg_schema.user_strava_id == user.strava_id
    assert created_reg_schema.event.id == event.id # EventReadMinimal is nested
    assert created_reg_schema.category.id == category.id # EventCategoryReadMinimal
    assert created_reg_schema.distance.id == distance.id # EventDistanceReadMinimal
    assert created_reg_schema.status.value == "pending" # Default status
    assert created_reg_schema.race_result is not None # RaceResultReadMinimal
    assert created_reg_schema.race_result.id is not None # Check if RR was created

    # Assert - Database Registration
    db_reg = await db_session.get(Registration, created_reg_schema.id)
    assert db_reg is not None
    assert db_reg.user_strava_id == user.strava_id
    assert db_reg.event_id == event.id
    assert db_reg.status == "pending" # Compare with string value of enum

    # Assert - Database RaceResult
    db_race_result_exec = await db_session.execute(
        select(RaceResult).where(RaceResult.registration_id == db_reg.id)
    )
    race_result_entry = db_race_result_exec.scalar_one_or_none()
    assert race_result_entry is not None
    assert race_result_entry.dorsal_number is None # Initially None
    assert race_result_entry.net_time_seconds is None # Initially None
    assert created_reg_schema.race_result.id == race_result_entry.id


@pytest.mark.asyncio
async def test_create_registration_duplicate(db_session: AsyncSession, setup_event_data):
    # Arrange: Create an initial registration
    user, event, category, distance = setup_event_data
    initial_reg_data = RegistrationCreate(
        user_strava_id=user.strava_id, event_id=event.id,
        event_category_id=category.id, event_distance_id=distance.id
    )
    await create_registration(db_session, user.strava_id, initial_reg_data) # First registration

    # Act & Assert: Try to register again with the same details
    duplicate_reg_data = RegistrationCreate(
        user_strava_id=user.strava_id, event_id=event.id,
        event_category_id=category.id, event_distance_id=distance.id
    )
    with pytest.raises(HTTPException) as exc_info:
        await create_registration(db_session, user.strava_id, duplicate_reg_data)
    
    assert exc_info.value.status_code == 409 # Conflict
    assert "Already registered" in exc_info.value.detail

@pytest.mark.asyncio
async def test_create_registration_non_existent_event(db_session: AsyncSession, setup_event_data):
    user, _, category, distance = setup_event_data # Event not used directly
    
    registration_data = RegistrationCreate(
        user_strava_id=user.strava_id, event_id=99999, # Non-existent event ID
        event_category_id=category.id, event_distance_id=distance.id
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await create_registration(db_session, user.strava_id, registration_data)
    
    assert exc_info.value.status_code == 404
    assert "Event not found" in exc_info.value.detail

@pytest.mark.asyncio
async def test_create_registration_invalid_category_for_event(db_session: AsyncSession, setup_event_data):
    user, event, _, distance = setup_event_data # Category not used directly

    # Create a category not linked to this event
    other_event = Event(name="Other Event", type=EventType.VIRTUAL, date=datetime.now(timezone.utc))
    db_session.add(other_event)
    await db_session.flush() # Get ID for other_event
    other_category = EventCategory(name="Wrong Cat", event_id=other_event.id)
    db_session.add(other_category)
    await db_session.commit() # Commit to save other_event and other_category
    await db_session.refresh(other_category) # Ensure other_category is loaded

    registration_data = RegistrationCreate(
        user_strava_id=user.strava_id, event_id=event.id,
        event_category_id=other_category.id, # Category from a different event
        event_distance_id=distance.id
    )
    
    with pytest.raises(HTTPException) as exc_info:
        await create_registration(db_session, user.strava_id, registration_data)
    
    assert exc_info.value.status_code == 400
    assert "Invalid category for this event" in exc_info.value.detail
