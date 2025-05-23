from fastapi import APIRouter, Depends, Request, HTTPException, Form, status # Added status
from fastapi.responses import HTMLResponse, RedirectResponse # Added RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import date, datetime # date for Form, datetime for combining

from app.dependencies import get_db_session
from app.services import event_service, race_service
from app.schemas.event import EventCreate, EventRead, EventType
from app.schemas.event_category import EventCategoryCreate, EventCategoryRead
from app.schemas.event_distance import EventDistanceCreate, EventDistanceRead
from app.schemas.registration import RegistrationRead
from app.schemas.race_result import RaceResultRead
from app.services.user_service import get_event_registrations_for_admin

router = APIRouter(
    prefix="/admin/events",
    tags=["event_admin"]
    # dependencies=[Depends(get_current_admin_user)] # Add this if admin auth is implemented
)

templates = Jinja2Templates(directory="app/templates")

@router.get("/create", response_class=HTMLResponse)
async def show_create_event_form(request: Request):
    return templates.TemplateResponse("admin/create_event.html", {"request": request, "event_types": [et.value for et in EventType]})

@router.post("/", response_class=RedirectResponse) # Changed response_model to response_class
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
        # This error handling might need to be improved, e.g., flash message and redirect back to form
        raise HTTPException(status_code=400, detail="Invalid event type. Go back and correct the form.")

    # datetime is already imported from datetime import date, datetime
    full_event_datetime = datetime.combine(event_date, datetime.min.time())

    event_data = EventCreate(
        name=name,
        location=location,
        type=event_type_enum,
        date=full_event_datetime,
        strava_sync_enabled=(strava_sync_enabled == "on")
    )
    
    # The event_service.create_event returns EventRead schema, which includes the id
    new_event_details = await event_service.create_event(db=db, event_data=event_data)
    
    # Redirect to the new admin event detail page
    return RedirectResponse(
        url=router.url_path_for("admin_view_event_detail", event_id=new_event_details.id), 
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.get("/", response_class=HTMLResponse, name="list_admin_events") # Changed, added name
async def list_admin_events_view( # Renamed function for clarity
    request: Request, # Added request
    db: AsyncSession = Depends(get_db_session), 
    skip: int = 0, limit: int = 100 # Default to more for an admin list
):
    events = await event_service.get_events(db=db, skip=skip, limit=limit)
    return templates.TemplateResponse(
        "admin/list_events_admin.html", 
        {"request": request, "events": events}
    )

# This is the public detail view, not the admin one
# This route might be removed or kept depending on whether admin uses a different path for public view
@router.get("/{event_id}", response_model=EventRead) 
async def get_single_event(event_id: int, db: AsyncSession = Depends(get_db_session)):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event

# New Admin-specific detail view
@router.get("/{event_id}/view", response_class=HTMLResponse, name="admin_view_event_detail")
async def show_admin_event_detail(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    event = await event_service.get_event(db=db, event_id=event_id) # get_event returns EventRead
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return templates.TemplateResponse(
        "admin/event_detail_admin.html",
        {"request": request, "event": event}
    )

@router.get("/{event_id}/edit", response_class=HTMLResponse, name="edit_event_form")
async def show_edit_event_form(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    event = await event_service.get_event(db=db, event_id=event_id) # Returns EventRead
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return templates.TemplateResponse(
        "admin/edit_event.html",
        {"request": request, "event": event, "event_types": list(EventType)} # Pass EventType enum values
    )

@router.post("/{event_id}/edit", response_class=RedirectResponse, name="update_event_details")
async def handle_update_event_details( # Renamed function for clarity
    request: Request, # Keep for consistency, though not directly used unless for advanced form handling
    event_id: int,
    name: str = Form(...),
    location: Optional[str] = Form(None), # Assuming location can be optional or cleared
    type: str = Form(...), # This will be the string value from the form, e.g., "on-site"
    event_date: date = Form(...), # FastAPI will parse YYYY-MM-DD from form
    strava_sync_enabled: Optional[str] = Form(None), # HTML form sends 'on' if checked, or nothing if not
    db: AsyncSession = Depends(get_db_session)
):
    try:
        event_type_enum = EventType(type) # Convert string from form to EventType enum
    except ValueError:
        # Consider re-rendering edit form with error message
        raise HTTPException(status_code=400, detail="Invalid event type selected.")

    # Ensure datetime is imported (it is at the top of the file)
    full_event_datetime = datetime.combine(event_date, datetime.min.time())

    # EventUpdate schema should be imported from app.schemas.event
    from app.schemas.event import EventUpdate # Ensure this import is at the top if not already

    event_update_data = EventUpdate(
        name=name,
        location=location,
        type=event_type_enum,
        date=full_event_datetime,
        strava_sync_enabled=(strava_sync_enabled == "on") # Convert checkbox value
    )

    updated_event = await event_service.update_event(
        db=db, event_id=event_id, event_data=event_update_data
    )

    if not updated_event:
        # Consider re-rendering edit form with error message
        raise HTTPException(status_code=404, detail="Event not found or update failed.")
    
    return RedirectResponse(
        url=router.url_path_for("admin_view_event_detail", event_id=updated_event.id),
        status_code=status.HTTP_303_SEE_OTHER
    )

@router.post("/{event_id}/categories/", response_model=EventCategoryRead)
async def add_event_category(event_id: int, category_name: str = Form(...), db: AsyncSession = Depends(get_db_session)):
    category_data = EventCategoryCreate(name=category_name, event_id=event_id)
    try:
        return await event_service.add_category_to_event(db=db, category_data=category_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) 

@router.get("/{event_id}/categories/", response_model=List[EventCategoryRead])
async def list_event_categories(event_id: int, db: AsyncSession = Depends(get_db_session)):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Parent event not found.")
    return await event_service.get_event_categories(db=db, event_id=event_id)

@router.post("/{event_id}/distances/", response_model=EventDistanceRead)
async def add_event_distance(event_id: int, distance_km: float = Form(...), db: AsyncSession = Depends(get_db_session)):
    distance_data = EventDistanceCreate(distance_km=distance_km, event_id=event_id)
    try:
        return await event_service.add_distance_to_event(db=db, distance_data=distance_data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/{event_id}/distances/", response_model=List[EventDistanceRead])
async def list_event_distances(event_id: int, db: AsyncSession = Depends(get_db_session)):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Parent event not found.")
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
):
    try:
        # updated_race_result = await race_service.assign_dorsal_number(...) # Corrected variable name
        await race_service.assign_dorsal_number( # Call the service
            db=db,
            registration_id=registration_id,
            dorsal_number=dorsal_number,
            event_id=event_id
        )
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        raise e

@router.post("/{event_id}/distance/{distance_id}/start_timer", response_model=List[RaceResultRead])
async def trigger_start_timer_for_distance(
    event_id: int,
    distance_id: int,
    start_time_manual: Optional[datetime] = Form(None),
    db: AsyncSession = Depends(get_db_session)
):
    actual_start_time = start_time_manual if start_time_manual else datetime.now()
    try:
        # updated_results = await race_service.start_event_distance_timer(...) # Corrected variable name
        await race_service.start_event_distance_timer( # Call the service
            db=db, event_id=event_id, distance_id=distance_id, start_time=actual_start_time
        )
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        raise e

@router.post("/{event_id}/record_finish", response_model=RaceResultRead)
async def record_athlete_finish_time_route(
    event_id: int,
    dorsal_number: int = Form(...),
    finish_time_manual: Optional[datetime] = Form(None),
    db: AsyncSession = Depends(get_db_session)
):
    actual_finish_time = finish_time_manual if finish_time_manual else datetime.now()
    try:
        # updated_result = await race_service.record_athlete_finish(...) # Corrected variable name
        await race_service.record_athlete_finish( # Call the service
            db=db, event_id=event_id, dorsal_number=dorsal_number, finish_time=actual_finish_time
        )
        return RedirectResponse(
            url=router.url_path_for("manage_event_registrations_form", event_id=event_id),
            status_code=status.HTTP_303_SEE_OTHER
        )
    except HTTPException as e:
        raise e
