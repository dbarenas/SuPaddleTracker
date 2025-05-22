from pydantic import BaseModel

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    """
    Data contained within the JWT.
    'sub' (subject) will store the user's identifier (e.g., strava_id).
    """
    strava_id: int | None = None
    # 'sub' is typically a string, so we'll store strava_id also as strava_id
    # and the create_access_token function will use str(strava_id) for 'sub'.
    # Alternatively, sub could be directly defined here as str if preferred.
