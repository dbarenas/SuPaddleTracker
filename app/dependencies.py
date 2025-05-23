from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse # Ensure RedirectResponse is imported
from fastapi.security import OAuth2PasswordBearer

from app.core.security import verify_token # Assuming this exists
from app.config import Settings
# from app.schemas.token import TokenData # Not currently used by these functions

settings = Settings() # Needs to be instantiated to be used by functions if they access settings directly

# This oauth2_scheme can be kept for other parts of the application or API docs,
# but the functions below will primarily rely on cookies for token extraction.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/strava/login") 
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/strava/login", auto_error=False)


async def get_current_user_strava_id_optional(request: Request) -> Optional[int]:
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = verify_token(token) # verify_token should handle JWTError, ExpiredSignatureError
        if payload is None: # Explicitly check if verify_token returned None (e.g. on error)
            return None
        strava_id: Optional[int] = payload.get("strava_id")
        if strava_id is None or not isinstance(strava_id, int): # Check type as well
            return None
        return strava_id
    except Exception: # Catch any other unexpected errors during token processing
        # Optionally log the exception here
        return None

async def get_current_user_strava_id(strava_id_from_optional: Optional[int] = Depends(get_current_user_strava_id_optional)) -> int:
    # Renamed parameter to avoid conflict with the strava_id variable from the outer scope if this was nested
    if strava_id_from_optional is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"}, # "Bearer" might be for header tokens, adjust if only cookies
        )
    return strava_id_from_optional

# Database session dependency - ensure this is consistent with existing usage
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import AsyncSessionFactory # Assuming AsyncSessionFactory is defined in session.py

async def get_db_session() -> AsyncSession: # Make sure this return type matches usage
    async with AsyncSessionFactory() as session:
        yield session

# Example usage (not part of this file, just for context):
# from fastapi import APIRouter
# router = APIRouter()
# @router.get("/users/me")
# async def read_users_me(current_user_id: int = Depends(get_current_user_strava_id)):
# return {"strava_id": current_user_id}
#
# @router.get("/users/me_optional")
# async def read_users_me_optional(current_user_id: Optional[int] = Depends(get_current_user_strava_id_optional)):
# if current_user_id is None:
# return {"msg": "Hello, guest!"}
# return {"strava_id": current_user_id, "msg": "Hello, authenticated user!"}
