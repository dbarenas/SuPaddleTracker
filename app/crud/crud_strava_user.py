from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import encrypt_token # decrypt_token is not used in this file yet
from app.models.strava_user import StravaUserDB, StravaAthleteData, StravaTokenData
# StravaUserCreate is not directly used for creating from API data here, but good to have for other contexts if needed.

async def get_user_by_strava_id(db: AsyncSession, *, strava_id: int) -> StravaUserDB | None:
    """
    Retrieves a user from the database by their Strava ID.
    """
    result = await db.execute(select(StravaUserDB).where(StravaUserDB.strava_id == strava_id))
    return result.scalar_one_or_none()

async def create_or_update_strava_user(
    db: AsyncSession,
    *,
    athlete_data: StravaAthleteData,
    token_data: StravaTokenData,
    scope: list[str]
) -> StravaUserDB:
    """
    Creates a new Strava user in the database or updates an existing one.
    Tokens are encrypted before storing.
    """
    existing_user = await get_user_by_strava_id(db, strava_id=athlete_data.id)

    # Calculate token expiration datetime
    # Strava's expires_at is a Unix timestamp. We can use that directly.
    # If we were to use expires_in, it would be:
    # expires_at_dt = datetime.utcnow() + timedelta(seconds=token_data.expires_in)
    # However, Strava provides expires_at which is more reliable.
    # Ensure it's timezone-aware (UTC) if it's not already.
    # For this example, we assume token_data.expires_at is a Unix timestamp (seconds since epoch)
    token_expires_at_dt = datetime.fromtimestamp(token_data.expires_at, tz=timezone.utc)
    
    encrypted_access = encrypt_token(token_data.access_token)
    encrypted_refresh = encrypt_token(token_data.refresh_token)
    
    # Join scope list into a string
    scope_str = ",".join(scope) if scope else None

    if existing_user:
        # Update existing user
        update_values = {
            "username": athlete_data.username, # Strava username can change
            "firstname": athlete_data.firstname,
            "lastname": athlete_data.lastname,
            "profile_picture_url": athlete_data.profile_medium or athlete_data.profile,
            "encrypted_access_token": encrypted_access,
            "encrypted_refresh_token": encrypted_refresh,
            "token_expires_at": token_expires_at_dt,
            "scope": scope_str,
            "last_login_at": datetime.utcnow(), # Update last login time
        }
        await db.execute(
            update(StravaUserDB)
            .where(StravaUserDB.strava_id == athlete_data.id)
            .values(**update_values)
        )
        user_to_refresh = existing_user # User instance is already here
    else:
        # Create new user
        new_user = StravaUserDB(
            strava_id=athlete_data.id,
            username=athlete_data.username,
            firstname=athlete_data.firstname,
            lastname=athlete_data.lastname,
            profile_picture_url=athlete_data.profile_medium or athlete_data.profile,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            token_expires_at=token_expires_at_dt,
            scope=scope_str,
            # created_at and last_login_at have defaults in the model
            # last_login_at will be set to current time on creation via default
        )
        db.add(new_user)
        user_to_refresh = new_user # User instance is the new_user

    await db.commit()
    await db.refresh(user_to_refresh)
    return user_to_refresh
