import os # For os.makedirs

from fastapi import APIRouter, Form, UploadFile, File, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user_strava_id
from app.crud.crud_strava_user import get_user_by_strava_id
from app.db.session import get_db_session

router = APIRouter()

# Instantiate Jinja2Templates. Assumes 'app/templates' exists.
# This is created in an earlier step (Part 3, Step 2).
templates = Jinja2Templates(directory="app/templates")

@router.get("/register", response_class=HTMLResponse)
async def show_registration_form(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    strava_id: int = Depends(get_current_user_strava_id)
):
    """
    Shows the registration form, pre-filled with user details if available.
    Requires user to be logged in via Strava.
    """
    user = await get_user_by_strava_id(db, strava_id=strava_id)
    user_name = "Strava User" # Default
    if user:
        if user.firstname and user.lastname:
            user_name = f"{user.firstname} {user.lastname}"
        elif user.username:
            user_name = user.username
    
    return templates.TemplateResponse(
        "register.html", 
        {"request": request, "user_name": user_name, "strava_id": strava_id}
    )

@router.post("/register")
async def register(
    request: Request, # Added request for potential future use, not strictly needed now
    nombre: str = Form(...), 
    edad: int = Form(...), 
    categoria: str = Form(...), 
    pago: UploadFile = File(...),
    strava_id: int = Depends(get_current_user_strava_id), # Inject Strava ID
    db: AsyncSession = Depends(get_db_session) # Added db session for potential future use
):
    """
    Handles the registration form submission.
    Associates the registration with the logged-in Strava user.
    """
    # Ensure the directory for payment proofs exists
    payments_dir = "static/payments/"
    os.makedirs(payments_dir, exist_ok=True)

    # Sanitize filename (basic example, consider more robust sanitization)
    safe_filename = pago.filename.replace("..", "").replace("/", "").replace("\\", "")
    payment_filename = f"payment_{strava_id}_{safe_filename}"
    payment_filepath = os.path.join(payments_dir, payment_filename)

    try:
        content = await pago.read()
        with open(payment_filepath, "wb") as f:
            f.write(content)
    except Exception as e:
        # Log error, return appropriate response
        # print(f"Error saving payment file: {e}")
        # For now, let's assume if this fails, registration is problematic.
        # Consider raising HTTPException or returning an error template.
        return {"msg": f"Error processing payment file: {str(e)}"}

    # Here you would typically save the registration details (nombre, edad, categoria, strava_id, payment_filepath)
    # to a new database table, e.g., 'registrations'. This part is not detailed in the task.
    # For now, just return a success message.
    
    return {
        "msg": f"Registrado con éxito para Strava ID {strava_id}", 
        "nombre": nombre, 
        "categoria": categoria, 
        "strava_id": strava_id,
        "payment_proof_filename": payment_filename
    }
