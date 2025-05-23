import pytest
import httpx
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession # For type hinting db_session

from app.services.strava_service import get_strava_access_token, _refresh_strava_token 
from app.models.strava_user import StravaUserDB
from app.core.security import encrypt_token, decrypt_token
from app.config import Settings # To access settings.STRAVA_CLIENT_ID etc.

@pytest.mark.asyncio
async def test_get_strava_access_token_valid_token_not_expired(db_session: AsyncSession, test_settings: Settings):
    # Arrange: Create a user with a valid, non-expired token
    original_access_token = "valid_access_token"
    original_refresh_token = "valid_refresh_token"
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    user = StravaUserDB(
        strava_id=123,
        username="testuser",
        firstname="Test",
        lastname="User",
        encrypted_access_token=encrypt_token(original_access_token),
        encrypted_refresh_token=encrypt_token(original_refresh_token),
        token_expires_at=expires_at,
        scope="read,activity:read" 
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    async with httpx.AsyncClient() as client:
        # Act
        retrieved_token = await get_strava_access_token(db_session, user, client)

    # Assert
    assert retrieved_token == original_access_token
    # Ensure user tokens in DB haven't changed
    await db_session.refresh(user) # Re-fetch user from db
    assert decrypt_token(user.encrypted_access_token) == original_access_token
    assert user.token_expires_at == expires_at

@pytest.mark.asyncio
async def test_get_strava_access_token_expired_token_refresh_success(
    db_session: AsyncSession, test_settings: Settings, httpx_mock: httpx.HTTPretty
):
    # Arrange: Create a user with an expired token
    original_access_token = "expired_access_token"
    original_refresh_token = "valid_refresh_token_for_success"
    new_access_token_from_strava = "new_refreshed_access_token"
    new_refresh_token_from_strava = "new_refreshed_refresh_token"
    # Token expired 1 hour ago
    expires_at_old = datetime.now(timezone.utc) - timedelta(hours=1) 
    # New token will expire in 1 hour from now (approx, based on Strava's 'expires_in')
    # Strava returns 'expires_at' as a timestamp (seconds since epoch)
    # and 'expires_in' (seconds from now). Let's simulate 'expires_at'.
    new_expires_at_timestamp = int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())


    user = StravaUserDB(
        strava_id=456,
        username="refreshtestuser",
        encrypted_access_token=encrypt_token(original_access_token),
        encrypted_refresh_token=encrypt_token(original_refresh_token),
        token_expires_at=expires_at_old,
        scope="read,activity:read"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    
    # Mock the Strava API response for token refresh
    strava_refresh_url = "https://www.strava.com/oauth/token"
    httpx_mock.add_response(
        method="POST",
        url=strava_refresh_url,
        json={
            "access_token": new_access_token_from_strava,
            "refresh_token": new_refresh_token_from_strava,
            "expires_at": new_expires_at_timestamp,
            "expires_in": 3600, # Example
            "token_type": "Bearer"
        },
        status_code=200
    )

    async with httpx.AsyncClient() as client:
        # Act
        retrieved_token = await get_strava_access_token(db_session, user, client)

    # Assert
    assert retrieved_token == new_access_token_from_strava
    
    # Verify user's tokens in DB were updated
    await db_session.refresh(user)
    assert decrypt_token(user.encrypted_access_token) == new_access_token_from_strava
    assert decrypt_token(user.encrypted_refresh_token) == new_refresh_token_from_strava
    # Compare timestamps carefully, allow for small differences if any, or compare date parts
    assert user.token_expires_at == datetime.fromtimestamp(new_expires_at_timestamp, tz=timezone.utc)
    assert len(httpx_mock.get_requests()) == 1 # Ensure the mock was called

@pytest.mark.asyncio
async def test_get_strava_access_token_expired_token_refresh_failure(
    db_session: AsyncSession, test_settings: Settings, httpx_mock: httpx.HTTPretty
):
    # Arrange: User with expired token, Strava refresh fails (e.g. 400 error)
    original_refresh_token = "invalid_refresh_token_for_failure"
    expires_at_old = datetime.now(timezone.utc) - timedelta(hours=1)

    user = StravaUserDB(
        strava_id=789,
        username="refreshfailuser",
        encrypted_access_token=encrypt_token("expired_access_token"),
        encrypted_refresh_token=encrypt_token(original_refresh_token),
        token_expires_at=expires_at_old,
        scope="read,activity:read"
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    strava_refresh_url = "https://www.strava.com/oauth/token"
    httpx_mock.add_response(
        method="POST",
        url=strava_refresh_url,
        json={"message": "Invalid refresh token"}, # Example error response
        status_code=400 
    )

    async with httpx.AsyncClient() as client:
        # Act
        retrieved_token = await get_strava_access_token(db_session, user, client)

    # Assert
    assert retrieved_token is None # Should fail to get a token
    # Ensure user tokens in DB haven't changed (or are marked invalid if that's the strategy)
    await db_session.refresh(user)
    assert decrypt_token(user.encrypted_refresh_token) == original_refresh_token # Refresh token itself shouldn't change on failed attempt
    assert len(httpx_mock.get_requests()) == 1
