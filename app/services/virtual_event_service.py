import httpx # For type hinting client, if passed through
from typing import List, Dict, Tuple, Optional # Added Optional
from datetime import datetime, timezone, timedelta # Added timedelta
from sqlalchemy import select, func # Added func for func.max

from sqlalchemy.ext.asyncio import AsyncSession # Use standard import
from app.models.virtual_result import VirtualResult
# from app.models.strava_user import StravaUserDB # Not directly used in this file's logic after prompt refinement
from app.services.strava_service import get_strava_activities, RELEVANT_STRAVA_ACTIVITY_TYPES
from app.schemas.virtual_result import VirtualResultCreate # For creating records

async def sync_strava_activities_for_user(
    db: AsyncSession,
    user_strava_id: int,
    # client: httpx.AsyncClient # Prompt indicates client is created within this service now
) -> Tuple[int, int]: # (new_activities_synced_count, total_activities_processed_count)
    """
    Fetches new Strava activities for a user and saves relevant ones as VirtualResults.
    """
    last_vr_stmt = select(func.max(VirtualResult.activity_date)).where(VirtualResult.user_strava_id == user_strava_id)
    last_activity_date_db = (await db.execute(last_vr_stmt)).scalar_one_or_none()
    
    after_timestamp = None
    if last_activity_date_db:
        # Ensure datetime is timezone-aware (UTC) before converting to timestamp
        if last_activity_date_db.tzinfo is None:
            last_activity_date_utc = last_activity_date_db.replace(tzinfo=timezone.utc)
        else:
            last_activity_date_utc = last_activity_date_db.astimezone(timezone.utc)
        after_timestamp = int(last_activity_date_utc.timestamp())
    else:
        # If no virtual results, fetch activities from e.g., last 30 days
        after_timestamp = int((datetime.now(timezone.utc) - timedelta(days=30)).timestamp())

    # get_strava_activities expects an httpx.AsyncClient to be passed.
    # The prompt for this service function implies it can create its own, or it can be passed.
    # The prompt for the router calling this service says "The current implementation of virtual_event_service creates its own client."
    # This means get_strava_activities needs to be callable without an explicit client from here,
    # or this service needs to create one and pass it.
    # The implementation of get_strava_activities in strava_service.py *requires* a client.
    # So, this function must create it.
    async with httpx.AsyncClient() as client:
        strava_activities = await get_strava_activities(
            db=db, user_strava_id=user_strava_id, client=client, after=after_timestamp, per_page=50 # Fetch up to 50 recent
        )

    if not strava_activities:
        return 0, 0

    newly_synced_count = 0
    processed_count = len(strava_activities)

    for activity_data in strava_activities:
        activity_id_str = str(activity_data["id"]) # Strava activity IDs are integers but can be large

        # Check if activity already synced
        existing_vr_stmt = select(VirtualResult.id).where(VirtualResult.strava_activity_id == activity_id_str)
        existing_vr = (await db.execute(existing_vr_stmt)).scalar_one_or_none()
        if existing_vr:
            continue

        # Filter by type
        activity_type = activity_data.get("type")
        if activity_type not in RELEVANT_STRAVA_ACTIVITY_TYPES:
            continue
        
        try:
            activity_datetime_str = activity_data["start_date"]
            # Ensure it's timezone-aware, Strava typically provides UTC.
            # Handle Z (Zulu time) if present, which means UTC.
            if activity_datetime_str.endswith("Z"):
                activity_datetime = datetime.fromisoformat(activity_datetime_str.replace("Z", "+00:00"))
            else:
                # If no timezone info, assume UTC as per Strava's general practice or parse as needed
                # For robustness, one might need to check format more carefully or make timezone explicit
                temp_dt = datetime.fromisoformat(activity_datetime_str)
                if temp_dt.tzinfo is None:
                    activity_datetime = temp_dt.replace(tzinfo=timezone.utc)
                else:
                    activity_datetime = temp_dt
        except (ValueError, TypeError) as e:
            # print(f"Could not parse activity date: {activity_data.get('start_date', 'N/A')}. Error: {e}")
            continue # Skip if date is invalid

        vr_create_data = VirtualResultCreate(
            user_strava_id=user_strava_id,
            strava_activity_id=activity_id_str,
            name=activity_data.get("name", "Strava Activity"),
            distance_km=activity_data.get("distance", 0) / 1000.0, # Distance from Strava is in meters
            elapsed_time_seconds=activity_data.get("elapsed_time", 0), # Elapsed time in seconds
            activity_date=activity_datetime,
            # event_id can be null if not tied to a specific virtual event in our system yet
        )
        
        if vr_create_data.distance_km <= 0 or vr_create_data.elapsed_time_seconds <= 0:
            continue

        db_virtual_result = VirtualResult(**vr_create_data.model_dump())
        db.add(db_virtual_result)
        newly_synced_count += 1
    
    if newly_synced_count > 0:
        await db.commit()
        
    return newly_synced_count, processed_count
