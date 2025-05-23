import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # Adjusted import
from datetime import date, datetime, timezone

from app.models.event import Event, EventType
# from app.schemas.event import EventRead # No longer directly validating full JSON response body here

@pytest.mark.asyncio
async def test_create_new_event_api_success(client: TestClient, db_session: AsyncSession):
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
async def test_create_new_event_api_invalid_type(client: TestClient, db_session: AsyncSession):
    # Arrange: Prepare form data with an invalid event type
    event_form_data = {
        "name": "Test Invalid Type Event",
        "location": "Test Location Invalid",
        "type": "invalid_event_type_value", # This type does not exist in Enum
        "event_date": date.today().isoformat(),
    }

    # Act
    response = client.post("/admin/events/", data=event_form_data)

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
