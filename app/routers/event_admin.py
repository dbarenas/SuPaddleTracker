from fastapi import APIRouter, Depends, Request, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date, datetime # date for Form, datetime for combining

from app.dependencies import get_db_session # Assuming get_current_admin_user is not yet a dependency here
from app.services import event_service, race_service # Added race_service
from app.schemas.event import EventCreate, EventRead, EventType
from app.schemas.event_category import EventCategoryCreate, EventCategoryRead
from app.schemas.event_distance import EventDistanceCreate, EventDistanceRead
from app.schemas.registration import RegistrationRead # Added RegistrationRead
from app.schemas.race_result import RaceResultRead # Added RaceResultRead for response_model
from app.services.user_service import get_event_registrations_for_admin # Specific import for the new function

router = APIRouter(
    prefix="/admin/events",
    tags=["event_admin"]
    # dependencies=[Depends(get_current_admin_user)] # Add this if admin auth is implemented
)

templates = Jinja2Templates(directory="app/templates")

@router.get("/create", response_class=HTMLResponse)
async def show_create_event_form(request: Request):
    return templates.TemplateResponse("admin/create_event.html", {"request": request, "event_types": [et.value for et in EventType]})

@router.post("/", response_model=EventRead)
async def create_new_event(
    request: Request, 
    name: str = Form(...),
    location: Optional[str] = Form(None),
    type: str = Form(...), 
    event_date: date = Form(...), 
    strava_sync_enabled: Optional[str] = Form(None), 
    db: AsyncSession = Depends(get_db_session)
):
    try:
        event_type_enum = EventType(type)
    except ValueError:
        # In a real app, you might want to re-render the form with an error message.
        # For an API-like router, raising HTTPException is common.
        # Consider how to provide user feedback if this is a direct HTML form submission target.
        raise HTTPException(status_code=400, detail=f"Invalid event type: {type}. Must be one of {[et.value for et in EventType]}.")

    full_event_datetime = datetime.combine(event_date, datetime.min.time())

    event_data = EventCreate(
        name=name,
        location=location,
        type=event_type_enum,
        date=full_event_datetime,
        strava_sync_enabled=(strava_sync_enabled == "on")
    )
    
    new_event = await event_service.create_event(db=db, event_data=event_data)
    # As per prompt, returning the object.
    # For a pure HTML form POST, a redirect is often preferred:
    # from fastapi.responses import RedirectResponse
    # return RedirectResponse(url=router.url_path_for("get_single_event", event_id=new_event.id), status_code=303)
    return new_event

@router.get("/", response_model=List[EventRead])
async def list_events(db: AsyncSession = Depends(get_db_session), skip: int = 0, limit: int = 20):
    return await event_service.get_events(db=db, skip=skip, limit=limit)

@router.get("/{event_id}", response_model=EventRead)
async def get_single_event(event_id: int, db: AsyncSession = Depends(get_db_session)):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

@router.post("/{event_id}/categories/", response_model=EventCategoryRead)
async def add_event_category(event_id: int, category_name: str = Form(...), db: AsyncSession = Depends(get_db_session)):
    category_data = EventCategoryCreate(name=category_name, event_id=event_id)
    try:
        return await event_service.add_category_to_event(db=db, category_data=category_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) # Event not found for category

@router.get("/{event_id}/categories/", response_model=List[EventCategoryRead])
async def list_event_categories(event_id: int, db: AsyncSession = Depends(get_db_session)):
    # Ensure event exists before listing categories, or handle in service.
    # For now, assume service handles if event_id is for a non-existent event (returns empty list).
    event = await event_service.get_event(db=db, event_id=event_id) # Check if event exists
    if not event:
        raise HTTPException(status_code=404, detail="Parent event not found.")
    return await event_service.get_event_categories(db=db, event_id=event_id)

@router.post("/{event_id}/distances/", response_model=EventDistanceRead)
async def add_event_distance(event_id: int, distance_km: float = Form(...), db: AsyncSession = Depends(get_db_session)):
    distance_data = EventDistanceCreate(distance_km=distance_km, event_id=event_id)
    try:
        return await event_service.add_distance_to_event(db=db, distance_data=distance_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) # Event not found for distance

@router.get("/{event_id}/distances/", response_model=List[EventDistanceRead])
async def list_event_distances(event_id: int, db: AsyncSession = Depends(get_db_session)):
    # Ensure event exists before listing distances
    event = await event_service.get_event(db=db, event_id=event_id) # Check if event exists
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent event not found.")
    return await event_service.get_event_distances(db=db, event_id=event_id)

@router.get("/{event_id}/manage_registrations", response_class=HTMLResponse)
async def manage_event_registrations_form(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    registrations = await get_event_registrations_for_admin(db=db, event_id=event_id)
    
    return templates.TemplateResponse(
        "admin/manage_event_registrations.html",
        {"request": request, "event": event, "registrations": registrations}
    )

@router.post("/{event_id}/registration/{registration_id}/assign_dorsal", response_model=RaceResultRead)
async def assign_dorsal_to_registration(
    event_id: int, 
    registration_id: int,
    dorsal_number: int = Form(...),
    db: AsyncSession = Depends(get_db_session)
    # Add admin user dependency here later
):
    try:
        updated_race_result = await race_service.assign_dorsal_number(
            db=db,
            registration_id=registration_id,
            dorsal_number=dorsal_number,
            event_id=event_id
        )
        # Redirect back to the manage registrations page
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        # Log error or handle for user feedback
        # For now, re-raise to see error details. 
        # In prod, redirect with error message or use JS to display error.
        raise e
    # return updated_race_result # If not redirecting

@router.post("/{event_id}/distance/{distance_id}/start_timer", response_model=List[RaceResultRead])
async def trigger_start_timer_for_distance(
    event_id: int,
    distance_id: int,
    start_time_manual: Optional[datetime] = Form(None), # Optional: admin can input time
    db: AsyncSession = Depends(get_db_session)
    # Add admin user dependency
):
    actual_start_time = start_time_manual if start_time_manual else datetime.now() # Use current time if not provided
    # Ensure timezone awareness if your DB stores timezone info. Python's datetime.now() is naive by default.
    # If using timezone-aware datetimes in DB (e.g. DateTime(timezone=True)), ensure actual_start_time is aware.
    # from datetime import timezone
    # actual_start_time = actual_start_time.replace(tzinfo=timezone.utc) # Example: set to UTC
    # For simplicity, assuming naive datetime or DB handles conversion.

    try:
        updated_results = await race_service.start_event_distance_timer(
            db=db, event_id=event_id, distance_id=distance_id, start_time=actual_start_time
        )
        # Redirect back to manage registrations page or a dedicated timing page
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        raise e # Or handle more gracefully for UI
    # return updated_results # If not redirecting

@router.post("/{event_id}/record_finish", response_model=RaceResultRead)
async def record_athlete_finish_time_route( # Renamed for clarity
    event_id: int,
    dorsal_number: int = Form(...),
    finish_time_manual: Optional[datetime] = Form(None), # Optional: admin can input time
    db: AsyncSession = Depends(get_db_session)
    # Add admin user dependency
):
    actual_finish_time = finish_time_manual if finish_time_manual else datetime.now()
    # Similar timezone considerations as start_time

    try:
        updated_result = await race_service.record_athlete_finish(
            db=db, event_id=event_id, dorsal_number=dorsal_number, finish_time=actual_finish_time
        )
        # Redirect back to manage registrations page or a dedicated timing page
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        raise e
    # return updated_result # If not redirecting
