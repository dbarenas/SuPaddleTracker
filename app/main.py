from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.db.session import init_db # Import init_db

app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await init_db()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Import routers
from app.routers import registration, race
from app.routers import auth as auth_router # Import the auth router

app.include_router(registration.router)
app.include_router(race.router)
app.include_router(auth_router.router) # Include the auth router
