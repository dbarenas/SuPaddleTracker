import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # Adjusted import
from datetime import date, datetime, timezone

from app.models.event import Event, EventType
from app.config import Settings # Added for test_settings type hint
from app.core.security import create_access_token # Added for non-admin token test

# from app.schemas.event import EventRead # No longer directly validating full JSON response body here

@pytest.mark.asyncio
async def test_create_new_event_api_success(client: TestClient, db_session: AsyncSession, test_settings: Settings): # Added test_settings
    # Arrange: Log in as admin first
    login_data = {"username": test_settings.ADMIN_USERNAME, "password": "testadminpass"}
    login_response = client.post("/admin/login", data=login_data, allow_redirects=True)
    assert login_response.status_code == 200, "Admin login failed"
    assert "/admin/dashboard" in str(login_response.url)

    # Arrange: Prepare form data for the event
    # Arrange: Prepare form data for the event
    event_name = "Test API Event Redirect"
    event_location = "Test Location Redirect"
    event_type_value = EventType.ON_SITE.value
    event_date_iso = date.today().isoformat()
    
    event_form_data = {
        "name": event_name,
        "location": event_location,
        "type": event_type_value,
        "event_date": event_date_iso,
        "strava_sync_enabled": "on" 
    }
    
    expected_event_datetime = datetime.combine(date.today(), datetime.min.time())
    # If timezone is involved in conversion by server, adjust expected_event_datetime.
    # Current server logic creates naive datetime from date.

    # Act: Make the POST request
    response = client.post("/admin/events/", data=event_form_data, allow_redirects=False) # Important: allow_redirects=False

    # Assert: Check the response for redirect
    assert response.status_code == 303, "Expected HTTP 303 See Other for redirect"
    assert "location" in response.headers, "Location header missing in redirect response"
    
    redirect_location = response.headers["location"]

    # Assert: Check if the event was actually created in the database
    # We need to get the ID. The ID is in the redirect_location URL.
    # e.g., /admin/events/{event_id}/view
    try:
        event_id_str = redirect_location.split("/")[-2] # Assuming URL like .../{event_id}/view
        event_id = int(event_id_str)
    except (IndexError, ValueError) as e:
        pytest.fail(f"Could not parse event_id from redirect Location header '{redirect_location}': {e}")

    db_event = await db_session.get(Event, event_id)
    
    assert db_event is not None, "Event not found in database after creation"
    assert db_event.name == event_name
    assert db_event.location == event_location
    assert db_event.type == EventType.ON_SITE
    assert db_event.date == expected_event_datetime # Compare Python datetime objects
    assert db_event.strava_sync_enabled == True

    # Optionally, test the redirect target page
    redirect_response = client.get(redirect_location, allow_redirects=False) # follow_redirects=False is default for get
    assert redirect_response.status_code == 200, f"Redirected page {redirect_location} did not return 200 OK"
    # Basic check that the event name appears on the admin detail page
    assert event_name in redirect_response.text, "Event name not found on the admin detail page after redirect"

@pytest.mark.asyncio
async def test_create_new_event_api_invalid_type(client: TestClient, db_session: AsyncSession, test_settings: Settings): # Added test_settings
    # Arrange: Log in as admin first
    login_data = {"username": test_settings.ADMIN_USERNAME, "password": "testadminpass"}
    login_response = client.post("/admin/login", data=login_data, allow_redirects=True)
    assert login_response.status_code == 200, "Admin login failed"

    # Arrange: Prepare form data with an invalid event type
    event_form_data = {
        "name": "Test Invalid Type Event",
        "location": "Test Location Invalid",
        "type": "invalid_event_type_value", # This type does not exist in Enum
        "event_date": date.today().isoformat(),
    }

    # Act
    response = client.post("/admin/events/", data=event_form_data) # Client has admin cookie

    # Assert: Check for 400 Bad Request (or 422 Unprocessable Entity if FastAPI's validation catches it first for Enum)
    # The current router code explicitly raises HTTPException 400 for invalid EventType string.
    assert response.status_code == 400, response.text
    response_data = response.json()
    assert "Invalid event type" in response_data.get("detail", "")
    
    # Assert: Ensure no event was created in the database
    # Check by name as we don't have an ID
    result = await db_session.execute(
        select(Event).where(Event.name == event_form_data["name"])
    )
    db_event = result.scalar_one_or_none()
    assert db_event is None

@pytest.mark.asyncio
async def test_admin_route_protection_no_token(client: TestClient):
    # Arrange: Try to access a protected admin route without logging in
    # Example: Admin event creation form
    
    # Act
    response = client.get("/admin/events/create", allow_redirects=False)
    
    # Assert
    assert response.status_code == 307, "Expected redirect to admin login page"
    assert "location" in response.headers
    assert response.headers["location"] == "/admin/login" # Or use url_for if client is configured for it

@pytest.mark.asyncio
async def test_admin_route_protection_with_valid_admin_token(client: TestClient, test_settings: Settings):
    # Arrange: Log in as admin first to get the cookie set on the client
    login_data = {
        "username": test_settings.ADMIN_USERNAME,
        "password": "testadminpass"
    }
    # Using allow_redirects=True ensures the TestClient follows the redirect
    # and the cookie set on the redirect response is available for subsequent requests.
    login_response = client.post("/admin/login", data=login_data, allow_redirects=True) 
    assert login_response.status_code == 200, "Admin login and redirect to dashboard failed"
    assert "/admin/dashboard" in str(login_response.url), "Redirect did not lead to admin dashboard"

    # Act: Access a protected admin route
    # The client now has the admin_access_token cookie from the login
    response = client.get("/admin/events/create") 
    
    # Assert
    assert response.status_code == 200, response.text
    assert "Create New Event" in response.text # Check for content from the protected page

@pytest.mark.asyncio
async def test_admin_route_protection_with_non_admin_token(client: TestClient, test_settings: Settings):
    # Arrange: Create a valid JWT but WITHOUT the is_admin claim
    # (This simulates a regular user token trying to access admin routes)
    user_payload = {"sub": "strava_user_123"} # Example non-admin payload
    non_admin_token_value = create_access_token(data=user_payload, is_admin=False)
    
    client.cookies.set("admin_access_token", non_admin_token_value) # Manually set the cookie

    # Act
    response = client.get("/admin/events/create", allow_redirects=False)
    
    # Assert
    assert response.status_code == 307, "Expected redirect to admin login, non-admin token"
    assert "location" in response.headers
    assert response.headers["location"] == "/admin/login"
    # Also check that the bad cookie was cleared
    assert "set-cookie" in response.headers
    assert "admin_access_token=;" in response.headers["set-cookie"]
