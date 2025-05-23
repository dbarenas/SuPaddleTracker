import json # Though often httpx .json() handles it, good to have if manual parsing needed
from typing import List, Optional # For type hinting scope

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status # Added status
from fastapi.responses import RedirectResponse, HTMLResponse # Added HTMLResponse
from fastapi.templating import Jinja2Templates # Added Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional # Ensure Optional is imported if not already

from app.config import Settings
from app.core.security import create_access_token, verify_token, decrypt_token # Added verify_token, decrypt_token
from app.crud.crud_strava_user import create_or_update_strava_user, get_user_by_strava_id # Added get_user_by_strava_id
from app.db.session import get_db_session
from app.dependencies import oauth2_scheme, get_current_user_strava_id_optional # Import the scheme and optional dependency
from app.models.strava_user import StravaAthleteData, StravaTokenData # Pydantic models for validation
from app.schemas.token import Token # Pydantic model for the response
# httpx is already imported
# Settings is already imported
# RedirectResponse is already imported

router = APIRouter(prefix="/auth", tags=["authentication"])
settings = Settings()

# Define the scope for Strava OAuth
# Adjust as needed: read,profile:read_all,activity:read,activity:write etc.
STRAVA_SCOPE = "read,profile:read_all,activity:read"

# Initialize Jinja2Templates for this router
# Assumes 'app/templates' directory exists relative to where the app is run
templates = Jinja2Templates(directory="app/templates")

@router.get("/display_login", response_class=HTMLResponse) # Changed path to /display_login to avoid conflict
async def login_page(request: Request):
    """
    Serves the login page.
    """
    return templates.TemplateResponse("login.html", {"request": request})

@router.get("/strava/login") # This is the actual action endpoint
async def strava_login():
    """
    Redirects the user to Strava's authorization page.
    """
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={settings.STRAVA_CLIENT_ID}"
        f"&redirect_uri={settings.STRAVA_REDIRECT_URI}"
        f"&response_type=code"
        f"&approval_prompt=auto" # 'force' to always show auth screen, 'auto' for auto-approval if already authorized
        f"&scope={STRAVA_SCOPE}"
    )
    return RedirectResponse(url=auth_url)

@router.get("/strava/callback", response_model=Token)
async def strava_callback(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    scope: Optional[str] = None, # Strava returns granted scope in the callback
    db: AsyncSession = Depends(get_db_session)
):
    """
    Handles the callback from Strava after user authorization.
    Exchanges the authorization code for an access token, fetches athlete data,
    creates or updates the user in the database, and returns a JWT.
    """
    if error:
        # Handle cases like 'access_denied'
        raise HTTPException(status_code=400, detail=f"Error from Strava: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Authorization code not provided by Strava.")

    # 1. Exchange code for token
    token_url = "https://www.strava.com/oauth/token"
    payload = {
        "client_id": settings.STRAVA_CLIENT_ID,
        "client_secret": settings.STRAVA_CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    
    strava_token_data: StravaTokenData
    athlete_summary_from_token_exchange: Optional[dict] = None # Strava includes athlete summary here

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=payload)
            response.raise_for_status() # Raises HTTPStatusError for 4xx/5xx responses
            token_response_data = response.json()
            
            # Validate with Pydantic model
            strava_token_data = StravaTokenData(**token_response_data)
            # The athlete summary is included in the token exchange response
            if 'athlete' in token_response_data:
                athlete_summary_from_token_exchange = token_response_data['athlete']

    except httpx.HTTPStatusError as e:
        # Log error details for debugging
        # print(f"HTTP error during token exchange: {e.response.text}")
        raise HTTPException(status_code=400, detail=f"Failed to exchange code for token: {e.response.text}")
    except Exception as e: # Catch other potential errors like JSONDecodeError or Pydantic validation
        # print(f"Error during token exchange: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during token exchange: {str(e)}")

    # 2. Fetch athlete data (if needed or to get more details)
    # Strava's token response includes a summary of the athlete.
    # For more detailed profile info, a separate call to /api/v3/athlete might be needed,
    # but often the summary is sufficient for initial user creation/identification.
    
    strava_athlete_data: StravaAthleteData
    if athlete_summary_from_token_exchange:
        # Validate the summary athlete data
        strava_athlete_data = StravaAthleteData(**athlete_summary_from_token_exchange)
    else:
        # Fallback to fetching athlete data if not in token response (should not happen with current Strava API)
        athlete_url = "https://www.strava.com/api/v3/athlete"
        headers = {"Authorization": f"Bearer {strava_token_data.access_token}"}
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(athlete_url, headers=headers)
                response.raise_for_status()
                athlete_api_data = response.json()
                strava_athlete_data = StravaAthleteData(**athlete_api_data)
        except httpx.HTTPStatusError as e:
            # print(f"HTTP error during athlete data fetch: {e.response.text}")
            raise HTTPException(status_code=400, detail=f"Failed to fetch athlete data: {e.response.text}")
        except Exception as e:
            # print(f"Error during athlete data fetch: {e}")
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred during athlete data fetch: {str(e)}")

    # 3. Get granted scopes
    # The 'scope' parameter from the callback URL reflects the granted scopes.
    # It can also be in token_response_data, but Strava docs say it's on callback.
    granted_scopes_list: List[str] = []
    if scope: # This is the 'scope' query parameter from Strava's redirect
        granted_scopes_list = scope.split(',')
    elif 'scope' in token_response_data: # Fallback if not in query params (less common)
         granted_scopes_list = token_response_data['scope'].split(',')
    else: # Default to what we requested if not explicitly returned
        granted_scopes_list = STRAVA_SCOPE.split(',')
        
    # 4. Create or update user in DB
    # The athlete_data from token exchange might be sufficient (e.g., `athlete_summary_from_token_exchange`)
    # We are using `strava_athlete_data` which is populated from that summary.
    db_user = await create_or_update_strava_user(
        db=db,
        athlete_data=strava_athlete_data, # This contains id, username, firstname, lastname etc.
        token_data=strava_token_data,
        scope=granted_scopes_list
    )

    if not db_user: # Should not happen if create_or_update is implemented correctly
        raise HTTPException(status_code=500, detail="Could not create or update user.")

    # 5. Create JWT access token
    # 'sub' (subject) typically holds the user's unique identifier.
    # We use strava_id as the subject for our JWT.
    jwt_payload = {"sub": str(db_user.strava_id), "strava_id": db_user.strava_id}
    jwt_access_token = create_access_token(data=jwt_payload)

    # Redirect to dashboard and set cookie
    response = RedirectResponse(url="/user/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=jwt_access_token,
        httponly=True, # Makes the cookie inaccessible to client-side JavaScript
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60, # Max age in seconds
        samesite="Lax", # Can be "Strict", "Lax", or "None"
        secure=settings.SECURE_COOKIE, # Set to True in production (requires HTTPS)
    )
    return response


@router.post("/strava/logout")
async def strava_logout(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    token: str = Depends(oauth2_scheme) # Use the dependency to get token
):
    """
    Handles user logout:
    1. Verifies the provided JWT.
    2. Fetches the user's Strava access token from the database.
    3. Calls Strava's deauthorize endpoint to revoke the token.
    4. Client is responsible for clearing the JWT.
    """
    payload = verify_token(token)
    if not payload or not payload.get("strava_id"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid or expired token"
        )
    
    user_strava_id = payload.get("strava_id")
    if not isinstance(user_strava_id, int): # Should be int from our JWT creation
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid token payload"
        )

    db_user = await get_user_by_strava_id(db, strava_id=user_strava_id)
    if not db_user:
        # This case might mean the user was deleted from DB but token is still valid.
        # Or, a valid token for a non-existent user.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        strava_access_token = decrypt_token(db_user.encrypted_access_token)
    except Exception:
        # If decryption fails, we can't deauthorize with Strava.
        # Log this, but proceed with local logout from client's perspective.
        # print(f"Error decrypting Strava access token for user {user_strava_id}. Cannot deauthorize with Strava.")
        # Depending on policy, could raise an error or just return success for local logout.
        # For now, let's assume this means we can't proceed with Strava deauth.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Could not process user credentials for Strava deauthorization.")

    deauthorize_url = "https://www.strava.com/oauth/deauthorize"
    # Strava's deauthorize endpoint expects the access_token as a POST parameter (form data).
    # The header "Authorization: Bearer <token>" is for API calls, not for this deauth call.
    form_data = {"access_token": strava_access_token} 

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(deauthorize_url, data=form_data)
            # Strava returns 200 OK on successful deauthorization.
            # It also returns 200 OK even if the token was already invalid or revoked.
            if response.status_code != 200:
                # This indicates a problem with the request itself or Strava's service
                # print(f"Error deauthorizing from Strava: {response.status_code} - {response.text}")
                # Don't fail the whole logout for this, but good to log.
                pass # Or raise an internal error if strict deauth is required
        except httpx.RequestError as e:
            # Network error or similar when trying to reach Strava
            # print(f"RequestError during Strava deauthorization: {str(e)}")
            # Don't fail the whole logout for this.
            pass

    # Client is responsible for deleting the JWT.
    # Redirecting to login page might be a good UX.
    # return RedirectResponse(url="/auth/display_login", status_code=status.HTTP_302_FOUND)
    # On logout, the client should clear the cookie. Here we can also instruct the browser to expire it.
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND) # Redirect to home
    response.delete_cookie(key="access_token", httponly=True, samesite="Lax", secure=settings.SECURE_COOKIE)
    return response
    # return {"msg": "Successfully logged out. Strava deauthorization attempted. Client should clear JWT."}


@router.get("/home", response_class=HTMLResponse)
async def home_page(
    request: Request, 
    db: AsyncSession = Depends(get_db_session), 
    strava_id: Optional[int] = Depends(get_current_user_strava_id_optional)
):
    """
    Serves the home page. Displays user information if logged in.
    """
    user_name = None
    s_id = None # Renaming to avoid conflict with strava_id from dependency
    if strava_id is not None: # Check if strava_id has a value
        user = await get_user_by_strava_id(db, strava_id=strava_id)
        if user:
            user_name = f"{user.firstname} {user.lastname}" if user.firstname and user.lastname else user.username
            s_id = user.strava_id # Assign value to s_id
    
    # current_user_name and strava_id are expected by home.html and base.html
    return templates.TemplateResponse(
        "home.html", 
        {"request": request, "current_user_name": user_name, "strava_id": s_id}
    )
