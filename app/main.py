from typing import Optional # Added Optional

from fastapi import FastAPI, Depends, Request # Added Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse # Added HTMLResponse

from app.db.session import init_db, get_db_session, AsyncSession # Import get_db_session, AsyncSession
from app.dependencies import get_current_user_strava_id_optional # Import the optional dependency
from app.crud.crud_strava_user import get_user_by_strava_id # Import crud function

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Import routers
from app.routers import registration, race
from app.routers import auth as auth_router # Import the auth router
from app.routers import user as user_router # Import the user router
from app.routers import event_admin as event_admin_router # Import the event admin router

app.include_router(registration.router)
app.include_router(race.router)
app.include_router(auth_router.router) # Include the auth router
app.include_router(user_router.router) # Include the user router
app.include_router(event_admin_router.router) # Include the event admin router


@app.get("/", response_class=HTMLResponse)
async def read_root(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    strava_id: Optional[int] = Depends(get_current_user_strava_id_optional)
):
    """
    Serves the home page from the root path.
    Displays user information if logged in.
    """
    user_name = None
    s_id = None # Renaming to avoid conflict with strava_id from dependency
    if strava_id is not None:
        user = await get_user_by_strava_id(db, strava_id=strava_id)
        if user:
            user_name = f"{user.firstname} {user.lastname}" if user.firstname and user.lastname else user.username
            s_id = user.strava_id
    
    # current_user_name and strava_id are expected by home.html and base.html
    return templates.TemplateResponse(
        "home.html", 
        {"request": request, "current_user_name": user_name, "strava_id": s_id}
    )
