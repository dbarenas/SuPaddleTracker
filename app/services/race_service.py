from sqlalchemy.ext.asyncio import AsyncSession # Standard import
from sqlalchemy import select
from sqlalchemy.orm import joinedload # selectinload is not used in the provided code, keeping joinedload
from fastapi import HTTPException, status
from datetime import datetime # Python's datetime
from typing import List, Optional

from app.models.race_result import RaceResult
from app.models.registration import Registration
from app.models.event import Event # Event model for context if needed later
from app.models.event_distance import EventDistance # EventDistance model for context if needed later

from app.schemas.race_result import RaceResultRead
# from app.schemas.registration import RegistrationRead # Not directly used in return types here

async def assign_dorsal_number(
    db: AsyncSession,
    registration_id: int,
    dorsal_number: int,
    event_id: int # To ensure dorsal is unique per event
) -> Optional[RaceResultRead]:
    # Check if dorsal number is already assigned for this event
    existing_dorsal_stmt = (
        select(RaceResult)
        .join(RaceResult.registration) # Assuming 'registration' is the relationship attribute in RaceResult model
        .where(
            Registration.event_id == event_id,
            RaceResult.dorsal_number == dorsal_number
        )
    )
    existing_dorsal_result = await db.execute(existing_dorsal_stmt)
    if existing_dorsal_result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Dorsal number {dorsal_number} is already assigned for this event."
        )

    # Find the RaceResult by registration_id
    race_result_stmt = (
        select(RaceResult)
        .options(joinedload(RaceResult.registration).joinedload(Registration.event)) # Load event for validation
        .where(RaceResult.registration_id == registration_id)
    )
    race_result_obj = (await db.execute(race_result_stmt)).scalar_one_or_none()

    if not race_result_obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Race result for registration not found.")
    
    if race_result_obj.registration.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration does not belong to the specified event.")

    race_result_obj.dorsal_number = dorsal_number
    await db.commit()
    # Refresh to get relationship attributes properly loaded for the schema, if they were changed or are lazy
    # The specific attribute 'registration' is useful here if RaceResultRead needs details from it
    # that might not be loaded by default after commit.
    await db.refresh(race_result_obj, attribute_names=['registration']) 

    return RaceResultRead.model_validate(race_result_obj)

async def start_event_distance_timer(
    db: AsyncSession, 
    event_id: int, 
    distance_id: int, 
    start_time: datetime
) -> List[RaceResultRead]:
    # Verify event and distance exist
    event = await db.get(Event, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")
    
    event_distance = await db.get(EventDistance, distance_id)
    if not event_distance or event_distance.event_id != event_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event distance not found or not related to this event.")

    # Find registrations for this event and distance
    registrations_stmt = (
        select(Registration.id)
        .where(Registration.event_id == event_id)
        .where(Registration.event_distance_id == distance_id)
        # Add any other conditions, e.g., registration.status == 'CONFIRMED'
    )
    registration_ids = (await db.execute(registrations_stmt)).scalars().all()

    if not registration_ids:
        # No registrations for this event/distance combination.
        # Or, handle as non-error, just return empty list.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No confirmed registrations found for this event/distance to start timer.")


    # Update RaceResult entries for these registrations
    # Set start_time only if not already set, or if policy allows overriding
    update_stmt = (
        RaceResult.__table__.update()
        .where(RaceResult.registration_id.in_(registration_ids))
        .where(RaceResult.start_time.is_(None)) # Only update if start_time is not already set
        .values(start_time=start_time)
    )
    await db.execute(update_stmt)
    await db.commit()

    # Fetch and return the updated RaceResult objects
    results_stmt = (
        select(RaceResult)
        .options(joinedload(RaceResult.registration).joinedload(Registration.user)) # Load user for context
        .where(RaceResult.registration_id.in_(registration_ids))
        # .where(RaceResult.start_time == start_time) # To ensure we get ones that were updated
    )
    updated_race_results = (await db.execute(results_stmt)).scalars().all()
    return [RaceResultRead.model_validate(rr) for rr in updated_race_results]

async def record_athlete_finish(
    db: AsyncSession, 
    event_id: int, 
    dorsal_number: int, 
    finish_time: datetime
) -> Optional[RaceResultRead]:
    # Find RaceResult by dorsal_number and event_id
    race_result_stmt = (
        select(RaceResult)
        .join(RaceResult.registration)
        .where(Registration.event_id == event_id)
        .where(RaceResult.dorsal_number == dorsal_number)
        .options(joinedload(RaceResult.registration).joinedload(Registration.user)) # For context in response
    )
    race_result = (await db.execute(race_result_stmt)).scalar_one_or_none()

    if not race_result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Race result for dorsal {dorsal_number} in this event not found.")

    if race_result.finish_time is not None:
        # Or allow update? For now, raise error if already set.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Finish time for dorsal {dorsal_number} already recorded.")

    race_result.finish_time = finish_time

    if race_result.start_time:
        net_time = finish_time - race_result.start_time
        race_result.net_time_seconds = int(net_time.total_seconds())
    else:
        # Cannot calculate net_time if start_time is not set
        # Log this or raise an error, depending on desired behavior
        # For now, net_time_seconds will remain None
        pass 
        # Or: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time not recorded for this athlete. Cannot calculate net time.")


    await db.commit()
    await db.refresh(race_result, attribute_names=['registration'])
    return RaceResultRead.model_validate(race_result)

async def update_event_distance_start_time(db: AsyncSession, event_id: int, distance_id: int, new_start_time: datetime) -> List[RaceResultRead]:
    # Implementation in next sub-task
    pass
