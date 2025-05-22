from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.db.base import Base
# Import models to ensure they are registered with Base.metadata
from app.models.strava_user import StravaUserDB # Ensure StravaUserDB is imported

settings = Settings()

async_engine = create_async_engine(settings.DATABASE_URL, echo=True) # echo=True for development

AsyncSessionFactory = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session

async def init_db():
    # Import all modules here that might define models so they
    # are registered properly on the metadata. Otherwise
    # you will have to import them first before calling init_db()
    # Base.metadata.create_all(bind=engine)
    # For async, it's a bit different:
    async with async_engine.begin() as conn:
        # In a real application, you might use Alembic for migrations
        await conn.run_sync(Base.metadata.create_all)
