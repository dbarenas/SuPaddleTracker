import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select # Adjusted import
from datetime import date, datetime, timezone

from app.models.event import Event, EventType
from app.schemas.event import EventRead # For response validation

@pytest.mark.asyncio
async def test_create_new_event_api_success(client: TestClient, db_session: AsyncSession):
    # Arrange: Prepare form data for the event
    event_form_data = {
        "name": "Test API Event",
        "location": "Test Location",
        "type": EventType.ON_SITE.value, # Use enum value
        "event_date": date.today().isoformat(), # e.g., "2023-10-27"
        "strava_sync_enabled": "on" # HTML form checkbox value
    }
    
    # Expected datetime for comparison (assuming time defaults to midnight)
    expected_event_datetime = datetime.combine(date.today(), datetime.min.time())
    # If your app assumes a specific timezone for date -> datetime conversion, apply it
    # For example, if it converts to UTC:
    # expected_event_datetime = datetime.combine(date.today(), datetime.min.time(), tzinfo=timezone.utc)
    # The current implementation of create_new_event in router combines with datetime.min.time() (naive)

    # Act: Make the POST request to the endpoint
    # The TestClient handles data serialization based on parameter types (Form in this case)
    response = client.post("/admin/events/", data=event_form_data)

    # Assert: Check the response
    assert response.status_code == 200, response.text
    response_data = response.json()
    
    assert response_data["name"] == event_form_data["name"]
    assert response_data["location"] == event_form_data["location"]
    assert response_data["type"] == event_form_data["type"]
    # Compare datetime part by part or by converting response string to datetime
    assert response_data["date"].startswith(expected_event_datetime.isoformat().split('T')[0]) # Check date part
    # Example: if response_data["date"] is "2023-10-27T00:00:00"
    # parsed_response_date = datetime.fromisoformat(response_data["date"])
    # assert parsed_response_date == expected_event_datetime # This would compare naive datetimes
    assert response_data["strava_sync_enabled"] == True # "on" should be converted to True

    # Assert: Check if the event was actually created in the database
    event_id = response_data["id"]
    db_event = await db_session.get(Event, event_id)
    
    assert db_event is not None
    assert db_event.name == event_form_data["name"]
    assert db_event.location == event_form_data["location"]
    assert db_event.type == EventType.ON_SITE # Compare with Enum member
    # Compare datetime object from DB with expected_event_datetime
    # Ensure db_event.date is also naive or both are timezone-aware for comparison
    assert db_event.date == expected_event_datetime 
    assert db_event.strava_sync_enabled == True

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
