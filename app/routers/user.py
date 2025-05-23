from fastapi import APIRouter, Depends, Request, HTTPException, File, UploadFile, status # Added status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any # Added Dict, Any
import shutil
from pathlib import Path

from app.dependencies import get_db_session, get_current_user_strava_id
from app.services import user_service, result_service as user_result_service, virtual_event_service # Added virtual_event_service
from app.schemas.registration import RegistrationRead
from app.schemas.race_result import RaceResultRead
from app.schemas.virtual_result import VirtualResultRead
from app.config import Settings
# from app.services.result_service import STANDARD_DISTANCES_KM # Not needed by router

settings = Settings()

router = APIRouter(
    prefix="/user",
    tags=["user"]
)

templates = Jinja2Templates(directory="app/templates")

@router.get("/dashboard", response_class=HTMLResponse)
async def view_dashboard(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    strava_id: int = Depends(get_current_user_strava_id)
):
    user_info = await user_service.get_strava_user_info(db=db, strava_id=strava_id)
    registrations = await user_service.get_user_registrations(db=db, user_strava_id=strava_id)
    
    personal_bests = await user_result_service.get_user_personal_bests(db=db, user_strava_id=strava_id)
    distinct_virtual_results = await user_service.get_user_virtual_results_summary(db=db, user_strava_id=strava_id)

    return templates.TemplateResponse(
        "dashboard.html", 
        {
            "request": request, 
            "user_info": user_info, # Full UserRead object
            "registrations": registrations,
            "virtual_results_summary": distinct_virtual_results, # Use the new summary data
            "personal_bests": personal_bests,
            # "active_page": "dashboard" # Removed as not used in new template
            # Macros are defined in the template itself
        }
    )

@router.post("/registration/{registration_id}/upload-payment-proof", response_model=RegistrationRead)
async def upload_payment_proof(
    request: Request, # request is available for url_for in template, but not explicitly needed here by default
    registration_id: int,
    payment_proof_file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db_session),
    strava_id: int = Depends(get_current_user_strava_id)
):
    # Ensure the static/uploads/payment_proofs directory exists
    # The path in the prompt app/static/... is relative to the project root.
    # If the app is run from a different CWD, this might be an issue.
    # settings.BASE_DIR or similar might be safer if available and configured.
    # For now, assume 'app/' is accessible from CWD.
    upload_dir = Path("app/static/uploads/payment_proofs") / str(strava_id) / str(registration_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename to prevent path traversal or invalid characters if necessary.
    # For simplicity, using the original filename. Consider sanitization for production.
    filename = payment_proof_file.filename
    if not filename: # Should not happen with UploadFile if a file is sent
        raise HTTPException(status_code=400, detail="No filename provided.")
        
    file_location = upload_dir / filename
    
    try:
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(payment_proof_file.file, file_object)
    except Exception as e:
        # Log the error (e.g., print(f"Error saving file: {e}"))
        raise HTTPException(status_code=500, detail=f"Could not save file: {e}")
    finally:
        payment_proof_file.file.close()

    # Construct URL path relative to static mount
    file_url_path = f"/static/uploads/payment_proofs/{strava_id}/{registration_id}/{filename}"

    updated_registration = await user_service.update_registration_payment_proof(
        db=db,
        registration_id=registration_id,
        user_strava_id=strava_id, # Pass current user's ID for verification
        payment_proof_url=file_url_path
    )
    if not updated_registration:
        # Optionally remove the uploaded file if the DB update fails
        # Path(file_location).unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Registration not found or access denied.")
    
    # Redirect back to dashboard to show the update
    # router.url_path_for("view_dashboard") should work as "view_dashboard" is the function name
    return RedirectResponse(url=router.url_path_for("view_dashboard"), status_code=status.HTTP_303_SEE_OTHER)

@router.post("/sync-strava", status_code=status.HTTP_200_OK)
async def trigger_strava_sync(
    request: Request, 
    db: AsyncSession = Depends(get_db_session),
    strava_id: int = Depends(get_current_user_strava_id) 
):
    try:
        new_count, processed_count = await virtual_event_service.sync_strava_activities_for_user(
            db=db, user_strava_id=strava_id
        )
        return {"message": f"Strava sync complete. Processed {processed_count} activities, synced {new_count} new activities."}
    except Exception as e:
        # Log the exception e
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during Strava sync: {str(e)}"
        )
