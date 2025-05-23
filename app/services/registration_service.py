from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import Optional

from fastapi import HTTPException, status

# Models
from app.models.registration import Registration, RegistrationStatus
from app.models.event import Event
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.strava_user import StravaUserDB
from app.models.race_result import RaceResult # Import RaceResult

# Schemas
from app.schemas.registration import RegistrationCreate, RegistrationRead

async def create_registration(
    db: AsyncSession,
    user_strava_id: int,
    registration_data: RegistrationCreate
) -> RegistrationRead:
    # Verify user exists
    user_query = await db.execute(select(StravaUserDB).where(StravaUserDB.strava_id == user_strava_id))
    user = user_query.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    # Verify event, category, and distance exist and are linked
    event = await db.get(Event, registration_data.event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found.")

    category = await db.get(EventCategory, registration_data.event_category_id)
    if not category or category.event_id != event.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid category for this event.")

    distance = await db.get(EventDistance, registration_data.event_distance_id)
    if not distance or distance.event_id != event.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid distance for this event.")

    # Check for duplicate registration
    existing_reg_stmt = select(Registration).where(
        Registration.user_strava_id == user_strava_id,
        Registration.event_id == registration_data.event_id,
        Registration.event_category_id == registration_data.event_category_id,
        Registration.event_distance_id == registration_data.event_distance_id
    )
    existing_reg_result = await db.execute(existing_reg_stmt)
    if existing_reg_result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already registered for this event/category/distance.")

    # Create registration
    # user_strava_id is passed directly, not from registration_data to ensure it's the authenticated user.
    # payment_proof_url and status from registration_data are ignored here, model defaults will apply.
    db_registration = Registration(
        user_strava_id=user_strava_id, 
        event_id=registration_data.event_id,
        event_category_id=registration_data.event_category_id,
        event_distance_id=registration_data.event_distance_id
        # status will use the default from the model (PENDING)
        # payment_proof_url will be None by default
    )

    db.add(db_registration)
    await db.commit()
    # await db.refresh(db_registration) # Refresh to get ID if needed for RaceResult, but commit does this.

    # Create a corresponding RaceResult entry
    new_race_result = RaceResult(registration_id=db_registration.id)
    db.add(new_race_result)
    await db.commit()
    
    # Refresh db_registration to get all fields like id, registered_at, status, and potentially the race_result relationship
    # The race_result relationship might not be immediately populated on db_registration object by refreshing it,
    # especially if the ORM hasn't been configured to see it bi-directionally immediately or if it's a new object.
    # The explicit loading below will ensure it's part of the final object.
    await db.refresh(db_registration)


    # Eagerly load related data for the response, including the new race_result
    loaded_reg_stmt = (
        select(Registration)
        .options(
            joinedload(Registration.user),
            joinedload(Registration.event).joinedload(Event.categories),
            joinedload(Registration.event).joinedload(Event.distances),
            joinedload(Registration.category),
            joinedload(Registration.distance),
            joinedload(Registration.race_result),
        )
        .where(Registration.id == db_registration.id)
    )
    loaded_reg_result = await db.execute(loaded_reg_stmt)
    final_registration = loaded_reg_result.scalar_one_or_none()
    
    if not final_registration: # Should not happen
       raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve registration details after creation.")

    return RegistrationRead.model_validate(final_registration)
