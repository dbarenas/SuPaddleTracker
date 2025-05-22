import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from app.crud.crud_strava_user import create_or_update_strava_user, get_user_by_strava_id
from app.models.strava_user import StravaAthleteData, StravaTokenData, StravaUserDB
# encrypt_token will be needed if we directly prepare encrypted tokens for DB setup.
# However, create_or_update_strava_user handles encryption internally.
# from app.core.security import encrypt_token 
# We need to ensure that the `encrypt_token` used by the CRUD function uses the test SECRET_KEY.
# The autouse fixture in test_security.py should handle this if tests are run together.
# If not, a specific fixture here might be needed to patch settings for app.core.security.

# Sample data for tests
sample_athlete_data_1 = StravaAthleteData(
    id=12345,
    username="testuser1",
    firstname="Test",
    lastname="UserOne",
    profile_medium="http://example.com/profile1.jpg"
    # Other fields can be None or default
)

sample_token_data_1 = StravaTokenData(
    access_token="access_token_1",
    refresh_token="refresh_token_1",
    expires_at=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()), # Expires in 1 hour
    expires_in=3600, # seconds
    token_type="Bearer"
)

sample_scope_1 = ["read", "profile:read_all"]

sample_athlete_data_2 = StravaAthleteData(
    id=67890,
    username="testuser2",
    firstname="Another",
    lastname="UserTwo",
    profile_medium="http://example.com/profile2.jpg"
)

sample_token_data_2 = StravaTokenData(
    access_token="access_token_2",
    refresh_token="refresh_token_2",
    expires_at=int((datetime.now(timezone.utc) + timedelta(hours=2)).timestamp()),
    expires_in=7200,
    token_type="Bearer"
)
sample_scope_2 = ["read", "activity:read"]


@pytest.mark.asyncio
async def test_create_new_strava_user(db_session: AsyncSession):
    # Ensure that the security settings are patched for encrypt_token if it's used by CRUD
    # This relies on the autouse fixture in test_security.py or a similar setup.
    
    user = await create_or_update_strava_user(
        db=db_session,
        athlete_data=sample_athlete_data_1,
        token_data=sample_token_data_1,
        scope=sample_scope_1
    )
    
    assert user is not None
    assert user.strava_id == sample_athlete_data_1.id
    assert user.username == sample_athlete_data_1.username
    assert user.firstname == sample_athlete_data_1.firstname
    assert user.lastname == sample_athlete_data_1.lastname
    assert user.profile_picture_url == sample_athlete_data_1.profile_medium
    assert user.scope == ",".join(sample_scope_1)
    
    # Check if tokens are encrypted (i.e., not the raw token)
    assert user.encrypted_access_token != sample_token_data_1.access_token
    assert user.encrypted_refresh_token != sample_token_data_1.refresh_token
    
    # Verify token expiration (datetime object in DB)
    expected_expires_at_dt = datetime.fromtimestamp(sample_token_data_1.expires_at, tz=timezone.utc)
    assert user.token_expires_at.replace(tzinfo=timezone.utc) == expected_expires_at_dt.replace(microsecond=0) # DB might truncate microseconds

    # Verify created_at and last_login_at are recent
    assert (datetime.utcnow() - user.created_at).total_seconds() < 10
    assert (datetime.utcnow() - user.last_login_at).total_seconds() < 10


@pytest.mark.asyncio
async def test_get_user_by_strava_id_existing(db_session: AsyncSession):
    # Create a user first
    await create_or_update_strava_user(
        db=db_session,
        athlete_data=sample_athlete_data_1,
        token_data=sample_token_data_1,
        scope=sample_scope_1
    )
    
    fetched_user = await get_user_by_strava_id(db=db_session, strava_id=sample_athlete_data_1.id)
    
    assert fetched_user is not None
    assert fetched_user.strava_id == sample_athlete_data_1.id
    assert fetched_user.username == sample_athlete_data_1.username

@pytest.mark.asyncio
async def test_get_user_by_strava_id_non_existing(db_session: AsyncSession):
    fetched_user = await get_user_by_strava_id(db=db_session, strava_id=999999) # Non-existent ID
    assert fetched_user is None

@pytest.mark.asyncio
async def test_update_existing_strava_user(db_session: AsyncSession):
    # 1. Create initial user
    initial_user = await create_or_update_strava_user(
        db=db_session,
        athlete_data=sample_athlete_data_1,
        token_data=sample_token_data_1,
        scope=sample_scope_1
    )
    initial_db_id = initial_user.id
    initial_created_at = initial_user.created_at
    
    # Make sure some time passes for last_login_at to be different
    await asyncio.sleep(0.1)

    # 2. Prepare updated data
    updated_athlete_data = StravaAthleteData(
        id=sample_athlete_data_1.id, # Same Strava ID
        username="updated_testuser1",
        firstname="TestUpdated",
        lastname="UserOneUpdated",
        profile_medium="http://example.com/profile1_updated.jpg"
    )
    updated_token_data = StravaTokenData(
        access_token="new_access_token_1",
        refresh_token="new_refresh_token_1",
        expires_at=int((datetime.now(timezone.utc) + timedelta(hours=3)).timestamp()),
        expires_in=10800,
        token_type="Bearer"
    )
    updated_scope = ["read", "activity:write"] # New scope

    # 3. Call create_or_update_strava_user again with updated data
    updated_user = await create_or_update_strava_user(
        db=db_session,
        athlete_data=updated_athlete_data,
        token_data=updated_token_data,
        scope=updated_scope
    )
    
    assert updated_user is not None
    assert updated_user.id == initial_db_id # Local DB ID should remain the same
    assert updated_user.strava_id == sample_athlete_data_1.id
    
    # Verify updated fields
    assert updated_user.username == updated_athlete_data.username
    assert updated_user.firstname == updated_athlete_data.firstname
    assert updated_user.lastname == updated_athlete_data.lastname
    assert updated_user.profile_picture_url == updated_athlete_data.profile_medium
    assert updated_user.scope == ",".join(updated_scope)
    
    # Check encrypted tokens are different
    assert updated_user.encrypted_access_token != initial_user.encrypted_access_token
    assert updated_user.encrypted_refresh_token != initial_user.encrypted_refresh_token
    
    # Verify new token expiration
    expected_updated_expires_at_dt = datetime.fromtimestamp(updated_token_data.expires_at, tz=timezone.utc)
    assert updated_user.token_expires_at.replace(tzinfo=timezone.utc) == expected_updated_expires_at_dt.replace(microsecond=0)

    # Verify timestamps
    assert updated_user.created_at == initial_created_at # created_at should not change
    assert updated_user.last_login_at > initial_user.last_login_at # last_login_at should update


@pytest.mark.asyncio
async def test_create_or_update_multiple_users(db_session: AsyncSession):
    # Create user 1
    user1 = await create_or_update_strava_user(
        db=db_session,
        athlete_data=sample_athlete_data_1,
        token_data=sample_token_data_1,
        scope=sample_scope_1
    )
    # Create user 2
    user2 = await create_or_update_strava_user(
        db=db_session,
        athlete_data=sample_athlete_data_2,
        token_data=sample_token_data_2,
        scope=sample_scope_2
    )
    
    assert user1 is not None
    assert user1.strava_id == sample_athlete_data_1.id
    
    assert user2 is not None
    assert user2.strava_id == sample_athlete_data_2.id
    
    # Verify they are distinct records
    assert user1.id != user2.id
    
    fetched_user1 = await get_user_by_strava_id(db=db_session, strava_id=sample_athlete_data_1.id)
    fetched_user2 = await get_user_by_strava_id(db=db_session, strava_id=sample_athlete_data_2.id)
    
    assert fetched_user1.username == sample_athlete_data_1.username
    assert fetched_user2.username == sample_athlete_data_2.username
