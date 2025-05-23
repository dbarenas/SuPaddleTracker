from fastapi import APIRouter, Depends, Request, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Optional, Any # Added Dict, Optional, Any
import datetime # Explicit import for datetime.datetime.now() if needed, though not directly here

from app.dependencies import get_db_session, get_current_user_strava_id, get_current_user_strava_id_optional
from app.services import event_service, registration_service, result_service # Added result_service
from app.services.result_service import STANDARD_DISTANCES_KM # Import for passing to template
from app.schemas.event import EventRead
from app.schemas.registration import RegistrationCreate, RegistrationRead
# from app.schemas.race_result import RaceResultRead # Not directly used as response model for HTMLResponse

router = APIRouter(
    prefix="/races", # Setting a prefix for all routes in this router
    tags=["races"]
)

# Assumes templates are in 'app/templates' relative to the app's root running directory
templates = Jinja2Templates(directory="app/templates")

# Endpoint to list all events for users to browse
@router.get("/events", response_class=HTMLResponse)
async def list_available_events(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    skip: int = 0, 
    limit: int = 20
):
    events = await event_service.get_events(db=db, skip=skip, limit=limit)
    # The current_user_strava_id_optional is not explicitly passed here,
    # but base.html might rely on it being available from root or other auth routes.
    # For templates needing it directly, it should be passed.
    # Assuming list_events.html does not strictly require current_user_strava_id for its core function.
    return templates.TemplateResponse("list_events.html", {"request": request, "events": events})

# Endpoint to show details for a single event and allow registration
@router.get("/events/{event_id}", response_class=HTMLResponse)
async def show_event_detail_and_registration_form(
    request: Request, 
    event_id: int, 
    db: AsyncSession = Depends(get_db_session),
    current_user_strava_id: Optional[int] = Depends(get_current_user_strava_id_optional) # For template
):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    participant_counts = await event_service.get_event_participant_counts(db=db, event_id=event_id)
    
    return templates.TemplateResponse(
        "event_detail.html", 
        {
            "request": request, 
            "event": event, 
            "participant_counts": participant_counts,
            "current_user_strava_id": current_user_strava_id
        }
    )

# Endpoint to handle event registration
@router.post("/events/{event_id}/register", response_model=RegistrationRead) # response_model might be overridden by RedirectResponse
async def register_for_event(
    request: Request, 
    event_id: int,
    category_id: int = Form(...),
    distance_id: int = Form(...),
    db: AsyncSession = Depends(get_db_session),
    user_strava_id: int = Depends(get_current_user_strava_id) # Ensures user is logged in
):
    registration_input = RegistrationCreate(
        user_strava_id=user_strava_id, # This field is in RegistrationBase, part of RegistrationCreate
        event_id=event_id,
        event_category_id=category_id,
        event_distance_id=distance_id,
        # payment_proof_url and status will use defaults or be None
    )
    try:
        # The service function create_registration is responsible for all validations
        # including user existence, event/category/distance validity and duplication checks.
        new_registration = await registration_service.create_registration(
            db=db,
            user_strava_id=user_strava_id, # Pass authenticated user's Strava ID
            registration_data=registration_input
        )
        # After successful registration, redirect to user's dashboard
        return RedirectResponse(url="/user/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    
    except HTTPException as e:
        # If create_registration raises an HTTPException (e.g., 400, 404, 409),
        # it's often better to display this error on the form page rather than a generic error.
        # This requires rendering the event_detail.html again with an error message.
        # For simplicity now, re-raising the exception.
        # Consider a more user-friendly error display for HTML forms.
        # For example, could fetch event details again and render template with error.
        # event = await event_service.get_event(db=db, event_id=event_id) # Re-fetch for template
        # if not event: # Should not happen if registration just failed for other reasons
        #     raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found when trying to show error.")
        # return templates.TemplateResponse(
        #     "event_detail.html",
        #     {"request": request, "event": event, "current_user_strava_id": user_strava_id, "error": e.detail},
        #     status_code=e.status_code
        # )
        raise e
    # If not redirecting, and if new_registration was to be returned:
    # return new_registration

@router.get("/events/{event_id}/results", response_class=HTMLResponse)
async def show_event_results(
    request: Request,
    event_id: int,
    db: AsyncSession = Depends(get_db_session)
):
    event = await event_service.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    classified_results = await result_service.get_event_results_classified(db=db, event_id=event_id)
    
    return templates.TemplateResponse(
        "event_results.html",
        {"request": request, "event": event, "classified_results": classified_results}
    )

@router.get("/leaderboard/{year}", response_class=HTMLResponse)
async def show_yearly_leaderboard_for_year(request: Request, year: int, db: AsyncSession = Depends(get_db_session)):
    leaderboard_data = await result_service.get_yearly_leaderboard(db=db, year=year)
    # Pass STANDARD_DISTANCES_KM to the template context
    return templates.TemplateResponse(
        "leaderboard.html",
        {"request": request, "leaderboard_data": leaderboard_data, "year": year, "standard_distances_km_list": STANDARD_DISTANCES_KM}
    )

@router.get("/leaderboard", response_class=HTMLResponse)
async def show_overall_leaderboard(request: Request, db: AsyncSession = Depends(get_db_session)):
    leaderboard_data = await result_service.get_yearly_leaderboard(db=db, year=None) # No year filter
    # Pass STANDARD_DISTANCES_KM to the template context
    return templates.TemplateResponse(
        "leaderboard.html",
        {"request": request, "leaderboard_data": leaderboard_data, "year": "Overall", "standard_distances_km_list": STANDARD_DISTANCES_KM}
    )
