from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # For SQLAlchemy 2.0 style queries
from sqlalchemy.orm import joinedload
from typing import List, Optional

# Models
from app.models.registration import Registration
from app.models.race_result import RaceResult
from app.models.virtual_result import VirtualResult
from app.models.event import Event
from app.models.event_category import EventCategory
from app.models.event_distance import EventDistance
from app.models.strava_user import StravaUserDB

# Schemas
from app.schemas.registration import RegistrationRead
from app.schemas.race_result import RaceResultRead
from app.schemas.virtual_result import VirtualResultRead
from app.schemas.strava_user import UserRead # Import UserRead schema
from app.models.registration import RegistrationStatus # Import enum

async def get_strava_user_info(db: AsyncSession, strava_id: int) -> Optional[UserRead]:
    user_db_stmt = select(StravaUserDB).where(StravaUserDB.strava_id == strava_id)
    user = (await db.execute(user_db_stmt)).scalar_one_or_none()
    if user:
        return UserRead.model_validate(user)
    return None

async def get_user_registrations(db: AsyncSession, user_strava_id: int) -> List[RegistrationRead]:
    stmt = (
        select(Registration)
        .where(Registration.user_strava_id == user_strava_id)
        .options(
            joinedload(Registration.user), # Eagerly load StravaUserDB
            joinedload(Registration.event).joinedload(Event.categories), # Eagerly load Event and its categories
            joinedload(Registration.event).joinedload(Event.distances), # Eagerly load Event and its distances
            joinedload(Registration.category), # Eagerly load EventCategory
            joinedload(Registration.distance), # Eagerly load EventDistance
            joinedload(Registration.race_result) # Eagerly load RaceResult
        )
        .order_by(Registration.registered_at.desc())
    )
    result = await db.execute(stmt)
    registrations = result.scalars().all()
    return [RegistrationRead.model_validate(reg) for reg in registrations]

async def get_user_race_results(db: AsyncSession, user_strava_id: int) -> List[RaceResultRead]:
    # Assuming RaceResult is linked to Registration, and Registration is linked to user_strava_id
    stmt = (
        select(RaceResult)
        .join(Registration, RaceResult.registration_id == Registration.id)
        .where(Registration.user_strava_id == user_strava_id)
        .options(
            joinedload(RaceResult.registration).joinedload(Registration.event), # Eager load event details
            joinedload(RaceResult.registration).joinedload(Registration.category),
            joinedload(RaceResult.registration).joinedload(Registration.distance)
        )
        .order_by(RaceResult.id.desc()) # Or some other relevant field like finish_time
    )
    result = await db.execute(stmt)
    race_results = result.scalars().all()
    return [RaceResultRead.model_validate(rr) for rr in race_results]

async def get_user_virtual_results(db: AsyncSession, user_strava_id: int) -> List[VirtualResultRead]:
    stmt = (
        select(VirtualResult)
        .where(VirtualResult.user_strava_id == user_strava_id)
        .options(
            joinedload(VirtualResult.user), # Eager load user
            joinedload(VirtualResult.event)  # Eager load event if linked
        )
        .order_by(VirtualResult.activity_date.desc())
    )
    result = await db.execute(stmt)
    virtual_results = result.scalars().all()
    return [VirtualResultRead.model_validate(vr) for vr in virtual_results]

async def update_registration_payment_proof(
    db: AsyncSession,
    registration_id: int,
    user_strava_id: int, # For authorization check
    payment_proof_url: str
) -> Optional[RegistrationRead]:
    # First, get the registration and verify ownership
    stmt = (
        select(Registration)
        .where(Registration.id == registration_id)
        .where(Registration.user_strava_id == user_strava_id)
    )
    result = await db.execute(stmt)
    registration = result.scalar_one_or_none()

    if not registration:
        return None # Not found or doesn't belong to user

    # Add logic here if certain statuses should not allow updates
    # For example, only allow updates if status is PENDING
    if registration.status != RegistrationStatus.PENDING.value:
        # Optionally raise an error, or simply return None or the existing registration
        # For this example, we'll prevent update if not PENDING
        # You might want to return the object without changes or raise HTTPException from router
        return None 

    registration.payment_proof_url = payment_proof_url
    # Optionally change status, e.g., to "AWAITING_CONFIRMATION"
    # registration.status = RegistrationStatus.AWAITING_CONFIRMATION.value # Or some other status like 'SUBMITTED'

    await db.commit()
    await db.refresh(registration)
    
    # Re-fetch with relationships for the response model to be correctly populated
    # This ensures that all fields expected by RegistrationRead are loaded.
    stmt_loaded = (
        select(Registration)
        .options(
            joinedload(Registration.user),
            joinedload(Registration.event).joinedload(Event.categories), # Also load sub-relationships if needed by schema
            joinedload(Registration.event).joinedload(Event.distances),
            joinedload(Registration.category),
            joinedload(Registration.distance),
            joinedload(Registration.race_result),
        )
        .where(Registration.id == registration_id)
    )
    result_loaded = await db.execute(stmt_loaded)
    registration_loaded = result_loaded.scalar_one_or_none()

    if not registration_loaded:
        # This should ideally not happen if the commit and refresh were successful
        return None

    return RegistrationRead.model_validate(registration_loaded)

async def get_event_registrations_for_admin(db: AsyncSession, event_id: int) -> List[RegistrationRead]:
    stmt = (
        select(Registration)
        .options(
            joinedload(Registration.user),
            joinedload(Registration.event), 
            joinedload(Registration.category),
            joinedload(Registration.distance),
            joinedload(Registration.race_result) # Crucial for dorsal number display
        )
        .where(Registration.event_id == event_id)
        .order_by(Registration.registered_at) # Example ordering
    )
    results = await db.execute(stmt)
    registrations = results.scalars().all()
    # print(f"Found {len(registrations)} registrations for event {event_id}") # Debugging
    # for reg in registrations: # Debugging
    #     print(f"Reg ID: {reg.id}, User: {reg.user.username if reg.user else 'N/A'}, RaceResult: {reg.race_result}")
    return [RegistrationRead.model_validate(reg) for reg in registrations]

async def get_user_virtual_results_summary(db: AsyncSession, user_strava_id: int) -> List[VirtualResultRead]:
    stmt = (
        select(VirtualResult)
        .where(VirtualResult.user_strava_id == user_strava_id)
        .order_by(VirtualResult.activity_date.desc())
        # .options(joinedload(VirtualResult.user)) # User is known, not strictly needed here
    )
    results = await db.execute(stmt)
    virtual_results_models = results.scalars().all()
    return [VirtualResultRead.model_validate(vr) for vr in virtual_results_models]
