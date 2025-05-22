from typing import Optional # Added Optional

from fastapi import Depends, HTTPException, status, Request # Added Request
from fastapi.security import OAuth2PasswordBearer

from app.core.security import verify_token
# TokenData schema might be useful if we want to return more than just strava_id
# from app.schemas.token import TokenData 

# The tokenUrl is a bit nominal here as login is via redirect and token is obtained from callback.
# However, FastAPI uses it for documentation and some internal wiring.
# It should point to an endpoint that *could* theoretically issue a token via password flow,
# or in our case, the start of the OAuth flow.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/strava/login") # auto_error=True by default
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/strava/login", auto_error=False)


async def get_current_user_strava_id(token: str = Depends(oauth2_scheme)) -> int:
    """
    Dependency to get the Strava ID from the current user's JWT.
    Raises HTTPException 401 if the token is invalid, expired, or doesn't contain the Strava ID.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception
    
    strava_id_from_payload = payload.get("strava_id")
    if strava_id_from_payload is None:
        # This could happen if 'strava_id' key is missing, or if its value is None.
        # We expect an int.
        raise credentials_exception
    
    # Ensure strava_id is an int, as stored in the token payload.
    # verify_token should return the payload as decoded, so strava_id should already be int.
    # If there's a chance it's a string (e.g. from 'sub'), convert or validate type.
    # Based on create_access_token, 'strava_id' is stored as int.
    if not isinstance(strava_id_from_payload, int):
        # Log this unexpected type for debugging
        # print(f"Unexpected type for strava_id in token: {type(strava_id_from_payload)}")
        raise credentials_exception

    return strava_id_from_payload


async def get_current_user_strava_id_optional(token: Optional[str] = Depends(oauth2_scheme_optional)) -> Optional[int]:
    """
    Dependency to optionally get the Strava ID from the current user's JWT.
    If no token is provided (e.g., user not logged in), or if the token is invalid/expired,
    it returns None instead of raising an error.
    """
    if token is None:
        return None
    
    payload = verify_token(token) # verify_token already handles JWTError, ExpiredSignatureError by returning None
    if payload is None:
        return None
    
    strava_id_from_payload = payload.get("strava_id")
    if strava_id_from_payload is None or not isinstance(strava_id_from_payload, int):
        return None
        
    return strava_id_from_payload

# Example of a protected route (not part of this subtask, just for illustration)
# from fastapi import APIRouter
# router = APIRouter()
# @router.get("/users/me")
# async def read_users_me(current_user_id: int = Depends(get_current_user_strava_id)):
#     return {"strava_id": current_user_id}
#
# @router.get("/users/me_optional")
# async def read_users_me_optional(current_user_id: Optional[int] = Depends(get_current_user_strava_id_optional)):
#     if current_user_id is None:
#         return {"msg": "Hello, guest!"}
#     return {"strava_id": current_user_id, "msg": "Hello, authenticated user!"}
