import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from httpx import Response, codes as http_status_codes # Renamed to avoid conflict with fastapi.status
import json

from app.config import Settings
from app.crud.crud_strava_user import get_user_by_strava_id
from app.core.security import verify_token, decrypt_token # For assertions

# Sample data (can be shared or defined per test/module)
MOCK_STRAVA_CLIENT_ID = "test_client_id"
MOCK_STRAVA_CLIENT_SECRET = "test_client_secret"
MOCK_STRAVA_REDIRECT_URI = "http://localhost:8000/auth/strava/callback"

MOCK_STRAVA_TOKEN_RESPONSE = {
    "token_type": "Bearer",
    "expires_at": 1700000000, # Example future timestamp
    "expires_in": 3600,
    "refresh_token": "mock_refresh_token",
    "access_token": "mock_access_token",
    "athlete": { # Strava includes athlete summary in token response
        "id": 12345,
        "username": "mockuser",
        "firstname": "Mock",
        "lastname": "User",
        "profile_medium": "http://example.com/mockprofile.jpg"
    }
}

MOCK_STRAVA_ATHLETE_DETAIL_RESPONSE = { # If a separate call to /api/v3/athlete was made
    "id": 12345,
    "username": "mockuser_detailed",
    "firstname": "MockDetailed",
    "lastname": "UserDetailed",
    "bio": "Mock bio",
    "city": "Mock City",
    "state": "Mock State",
    "country": "Mock Country",
    "sex": "M",
    "profile_medium": "http://example.com/mockprofile_detailed.jpg",
    "profile": "http://example.com/mockprofile_large_detailed.jpg"
}


@pytest.mark.asyncio
async def test_strava_login_redirect(client: TestClient, test_settings: Settings, monkeypatch):
    # Ensure the settings used by the app for generating the redirect URL are the test ones.
    # This is important if settings are read at module level in app.routers.auth
    monkeypatch.setattr('app.routers.auth.settings', test_settings)
    # And also patch the settings object within the auth router if it's instantiating its own
    # For this test, we assume app.config.settings is patched or auth router uses test_settings

    response = client.get("/auth/strava/login", allow_redirects=False) # Prevent following redirect
    
    assert response.status_code == http_status_codes.TEMPORARY_REDIRECT # FastAPI uses 307
    
    expected_redirect_location_start = "https://www.strava.com/oauth/authorize"
    assert response.headers["location"].startswith(expected_redirect_location_start)
    assert f"client_id={test_settings.STRAVA_CLIENT_ID}" in response.headers["location"]
    assert f"redirect_uri={test_settings.STRAVA_REDIRECT_URI}" in response.headers["location"]
    assert "scope=read,profile:read_all,activity:read" in response.headers["location"]


@pytest.mark.asyncio
async def test_strava_callback_successful_flow(
    client: TestClient, db_session: AsyncSession, httpx_mock, test_settings: Settings, monkeypatch
):
    # Patch settings used by the callback endpoint
    monkeypatch.setattr('app.routers.auth.settings', test_settings)

    # Mock Strava token exchange
    httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json=MOCK_STRAVA_TOKEN_RESPONSE,
        status_code=http_status_codes.OK
    )
    
    # Note: The current callback logic in app.routers.auth uses the athlete data
    # from the token exchange response. So, a separate mock for /api/v3/athlete
    # is not strictly needed unless that logic changes or has a fallback.
    # If it were needed:
    # httpx_mock.add_response(
    #     method="GET",
    #     url="https://www.strava.com/api/v3/athlete",
    #     json=MOCK_STRAVA_ATHLETE_DETAIL_RESPONSE, # Or use MOCK_STRAVA_TOKEN_RESPONSE['athlete']
    #     status_code=http_status_codes.OK
    # )

    callback_url = "/auth/strava/callback?code=testcode&scope=read,profile:read_all,activity:read"
    response = client.get(callback_url)
    
    assert response.status_code == http_status_codes.OK
    response_data = response.json()
    assert "access_token" in response_data
    assert "token_type" in response_data
    assert response_data["token_type"].lower() == "bearer"
    
    # Verify JWT
    jwt_payload = verify_token(response_data["access_token"]) # verify_token uses app.core.security.settings
    assert jwt_payload is not None
    assert jwt_payload["strava_id"] == MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["id"]
    
    # Verify user in DB
    db_user = await get_user_by_strava_id(db_session, strava_id=MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["id"])
    assert db_user is not None
    assert db_user.username == MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["username"]
    assert db_user.firstname == MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["firstname"]
    assert db_user.lastname == MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["lastname"]
    assert db_user.profile_picture_url == MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["profile_medium"]
    assert db_user.scope == "read,profile:read_all,activity:read" # From query param
    
    # Verify encrypted tokens stored (example check)
    decrypted_access_token = decrypt_token(db_user.encrypted_access_token)
    assert decrypted_access_token == MOCK_STRAVA_TOKEN_RESPONSE["access_token"]


@pytest.mark.asyncio
async def test_strava_callback_token_exchange_error(client: TestClient, httpx_mock, test_settings: Settings, monkeypatch):
    monkeypatch.setattr('app.routers.auth.settings', test_settings)
    
    httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json={"error": "invalid_grant"},
        status_code=http_status_codes.BAD_REQUEST # Or any 4xx/5xx
    )
    
    response = client.get("/auth/strava/callback?code=testcode_bad_exchange")
    
    assert response.status_code == http_status_codes.BAD_REQUEST # Or as per your error handling
    assert "Failed to exchange code for token" in response.json()["detail"]


@pytest.mark.asyncio
async def test_strava_callback_athlete_fetch_error(client: TestClient, httpx_mock, test_settings: Settings, monkeypatch):
    # This test is relevant if app.routers.auth.py explicitly calls /api/v3/athlete
    # and the athlete data is NOT in the token exchange response.
    # Current implementation relies on athlete data in token exchange, so this might be less critical.
    # To make it critical, we'd need to modify MOCK_STRAVA_TOKEN_RESPONSE to not include 'athlete'.
    
    monkeypatch.setattr('app.routers.auth.settings', test_settings)

    # Mock successful token exchange but without athlete data
    mock_token_response_no_athlete = MOCK_STRAVA_TOKEN_RESPONSE.copy()
    del mock_token_response_no_athlete["athlete"] # Simulate athlete not in token response

    httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json=mock_token_response_no_athlete,
        status_code=http_status_codes.OK
    )
    # Mock athlete fetch failure
    httpx_mock.add_response(
        method="GET",
        url="https://www.strava.com/api/v3/athlete",
        json={"error": "strava_api_error"},
        status_code=http_status_codes.INTERNAL_SERVER_ERROR # Or any 4xx/5xx
    )
    
    response = client.get("/auth/strava/callback?code=testcode_athlete_fetch_fail")
    
    # The current code might raise 400 or 500 based on the athlete fetch failure
    # This depends on the exact error handling in your app.routers.auth.strava_callback
    assert response.status_code == http_status_codes.BAD_REQUEST # Or 500
    assert "Failed to fetch athlete data" in response.json()["detail"]


@pytest.mark.asyncio
async def test_strava_logout(
    client: TestClient, db_session: AsyncSession, httpx_mock, test_settings: Settings, monkeypatch
):
    monkeypatch.setattr('app.routers.auth.settings', test_settings)

    # 1. Simulate login to get a JWT and create user
    httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/token",
        json=MOCK_STRAVA_TOKEN_RESPONSE,
        status_code=http_status_codes.OK
    )
    # No separate athlete fetch mock needed if athlete data is in token response.
    
    login_response = client.get("/auth/strava/callback?code=logintestcode&scope=read")
    assert login_response.status_code == http_status_codes.OK
    jwt_token = login_response.json()["access_token"]
    
    # User should be in DB now
    strava_id = MOCK_STRAVA_TOKEN_RESPONSE["athlete"]["id"]
    db_user_before_logout = await get_user_by_strava_id(db_session, strava_id=strava_id)
    assert db_user_before_logout is not None

    # 2. Mock Strava deauthorize endpoint
    deauthorize_request = httpx_mock.add_response(
        method="POST",
        url="https://www.strava.com/oauth/deauthorize",
        json={"message": "Token deauthorized"}, # Example response, Strava's actual might vary
        status_code=http_status_codes.OK
    )
    
    # 3. Call logout with JWT
    headers = {"Authorization": f"Bearer {jwt_token}"}
    logout_response = client.post("/auth/strava/logout", headers=headers)
    
    assert logout_response.status_code == http_status_codes.OK
    assert "Successfully logged out" in logout_response.json()["msg"]
    
    # 4. Assert Strava deauthorize endpoint was called
    assert deauthorize_request.called
    assert deauthorize_request.call_count == 1
    # Check form data of the call
    called_request = deauthorize_request.calls[0].request
    # httpx stores form data as bytes, need to decode and parse or compare bytes
    # For x-www-form-urlencoded, it's like "key1=value1&key2=value2"
    content_str = called_request.content.decode()
    assert f"access_token={MOCK_STRAVA_TOKEN_RESPONSE['access_token']}" in content_str

    # Optional: Verify if user's tokens are cleared or user is marked inactive in DB (not specified)
    # For now, the logout endpoint doesn't modify the DB record, only deauthorizes with Strava.
    db_user_after_logout = await get_user_by_strava_id(db_session, strava_id=strava_id)
    assert db_user_after_logout is not None # User still exists
    # We could check if encrypted_access_token is still the same or cleared, if that was a feature.
    # assert db_user_after_logout.encrypted_access_token is None # If tokens are cleared locally
    assert db_user_after_logout.encrypted_access_token == db_user_before_logout.encrypted_access_token # Not cleared by current logout impl.
