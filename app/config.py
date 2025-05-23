from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    STRAVA_CLIENT_ID: str = "YOUR_STRAVA_CLIENT_ID"
    STRAVA_CLIENT_SECRET: str = "YOUR_STRAVA_CLIENT_SECRET"
    STRAVA_REDIRECT_URI: str = "http://localhost:8000/auth/strava/callback"
    DATABASE_URL: str = "sqlite+aiosqlite:///./strava_app.db"
    # IMPORTANT: This key MUST be changed to a strong, randomly generated key in production
    # and managed securely (e.g., via environment variable).
    SECRET_KEY: str = "YOUR_VERY_SECRET_KEY_FOR_ENCRYPTION_AND_JWT"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 43200  # 30 days
    SECURE_COOKIE: bool = False

    model_config = SettingsConfigDict(env_file=".env")

# Example of how to instantiate and use the settings:
# if __name__ == "__main__":
#     settings = Settings()
#     print(f"Strava Client ID: {settings.STRAVA_CLIENT_ID}")
#     print(f"Strava Client Secret: {settings.STRAVA_CLIENT_SECRET}")
#     print(f"Strava Redirect URI: {settings.STRAVA_REDIRECT_URI}")
