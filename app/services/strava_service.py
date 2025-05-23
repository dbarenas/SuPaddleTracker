import httpx
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, timezone
from sqlalchemy import select # Use select from sqlalchemy

from sqlalchemy.ext.asyncio import AsyncSession # Use standard import
from app.models.strava_user import StravaUserDB, StravaTokenData # StravaTokenData for refresh response
from app.core.security import decrypt_token, encrypt_token # Assuming these exist and work
from app.config import Settings

settings = Settings()

STRAVA_API_BASE_URL = "https://www.strava.com/api/v3"
STRAVA_OAUTH_URL = "https://www.strava.com/oauth/token"

# Define relevant activity types for virtual events
# Based on Strava's documentation: https://developers.strava.com/docs/reference/#api-models-ActivityType
RELEVANT_STRAVA_ACTIVITY_TYPES = [
    "Run", "Ride", "Swim", "Walk", "Hike", "AlpineSki", "BackcountrySki", 
    "Canoeing", "Crossfit", "EBikeRide", "Elliptical", "Golf", "Handcycle", 
    "IceSkate", "InlineSkate", "Kayaking", "Kitesurf", "NordicSki", 
    "RockClimbing", "RollerSki", "Rowing", "Sail", "Skateboard", "Snowboard", 
    "Snowshoe", "Soccer", "StairStepper", "StandUpPaddling", "Surfing", 
    "Velomobile", "VirtualRide", "VirtualRun", "WeightTraining", "Wheelchair", 
    "Windsurf", "Workout", "Yoga"
]


async def _refresh_strava_token(db: AsyncSession, user: StravaUserDB, client: httpx.AsyncClient) -> Optional[str]:
    """Helper function to refresh Strava access token."""
    payload = {
        "client_id": settings.STRAVA_CLIENT_ID,
        "client_secret": settings.STRAVA_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": decrypt_token(user.encrypted_refresh_token),
    }
    try:
        response = await client.post(STRAVA_OAUTH_URL, data=payload)
        response.raise_for_status() # Raise an exception for bad status codes
        token_data_dict = response.json()
        
        # Strava's refresh response: access_token, expires_at, expires_in, refresh_token
        
        user.encrypted_access_token = encrypt_token(token_data_dict["access_token"])
        user.encrypted_refresh_token = encrypt_token(token_data_dict["refresh_token"]) # Strava may return a new refresh token
        user.token_expires_at = datetime.fromtimestamp(token_data_dict["expires_at"], tz=timezone.utc)
        
        await db.commit()
        await db.refresh(user)
        return token_data_dict["access_token"]
    except httpx.HTTPStatusError as e:
        # print(f"Error refreshing Strava token for user {user.strava_id}: {e.response.text}")
        if e.response.status_code == 400:
            # This often means the refresh token is no longer valid.
            # Decide on re-auth strategy (e.g., clear tokens, set a flag on user model)
            pass 
        return None
    except Exception as e:
        # print(f"Unexpected error refreshing token: {e}")
        return None

async def get_strava_access_token(db: AsyncSession, user: StravaUserDB, client: httpx.AsyncClient) -> Optional[str]:
    """Gets a valid Strava access token, refreshing if necessary."""
    if user.token_expires_at <= datetime.now(timezone.utc) + timedelta(minutes=5):
        access_token = await _refresh_strava_token(db, user, client)
        if not access_token:
            return None 
        return access_token
    return decrypt_token(user.encrypted_access_token)

async def get_strava_activities(
    db: AsyncSession,
    user_strava_id: int,
    client: httpx.AsyncClient, # Pass httpx client for reuse
    page: int = 1,
    per_page: int = 30, 
    after: Optional[int] = None, 
    before: Optional[int] = None 
) -> List[Dict[str, Any]]:
    """Fetches activities for a user from Strava API."""
    user_stmt = select(StravaUserDB).where(StravaUserDB.strava_id == user_strava_id)
    user = (await db.execute(user_stmt)).scalar_one_or_none()

    if not user:
        # print(f"User {user_strava_id} not found in DB for Strava sync.")
        return []

    access_token = await get_strava_access_token(db, user, client)
    if not access_token:
        # print(f"Could not obtain valid access token for user {user_strava_id}.")
        return [] 

    headers = {"Authorization": f"Bearer {access_token}"}
    params = {"page": page, "per_page": per_page}
    if after:
        params["after"] = after
    if before:
        params["before"] = before
    
    try:
        response = await client.get(f"{STRAVA_API_BASE_URL}/athlete/activities", headers=headers, params=params)
        response.raise_for_status()
        activities = response.json()
        return activities 
    except httpx.HTTPStatusError as e:
        # print(f"Error fetching Strava activities for user {user.strava_id}: {e.response.text}")
        if e.response.status_code == 401: 
            refreshed_token = await _refresh_strava_token(db, user, client)
            if refreshed_token:
                headers = {"Authorization": f"Bearer {refreshed_token}"}
                try:
                    response = await client.get(f"{STRAVA_API_BASE_URL}/athlete/activities", headers=headers, params=params)
                    response.raise_for_status()
                    return response.json()
                except Exception: 
                    pass
        return []
    except Exception as e:
        # print(f"Unexpected error fetching activities: {e}")
        return []
