import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from typing import AsyncGenerator
import asyncio # Required for pytest.fixture scope="session" with async

from app.db.base import Base
from app.db.session import get_db_session
from app.main import app # Import your FastAPI app
from app.config import Settings

# Use a separate DB for testing (in-memory SQLite)
# Using a file-based DB for tests can be easier to inspect/debug.
# :memory: is also an option but can have limitations with some SQLite features across connections.
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db" 

@pytest.fixture(scope="session")
def test_settings():
    # This ensures that tests use a dedicated, predictable secret key and test database.
    return Settings(DATABASE_URL=TEST_DATABASE_URL, SECRET_KEY="test_secret_key_for_pytest_!@#$")

# Fixture to ensure event loop is managed correctly for session-scoped async fixtures
@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def test_engine(test_settings, event_loop): # event_loop fixture ensures loop is available
    engine = create_async_engine(test_settings.DATABASE_URL, echo=False) # Usually False for tests
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn: 
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose() # Dispose of the engine


@pytest.fixture(scope="function") # function scope for clean DB per test
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a clean database session for each test function.
    Rolls back transactions after the test to ensure isolation.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()
    
    AsyncTestSessionFactory = sessionmaker(
        bind=connection, class_=AsyncSession, expire_on_commit=False
    )
    session = AsyncTestSessionFactory()
    
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture(scope="function")
def override_get_db(db_session: AsyncSession):
    """
    Fixture to override the 'get_db_session' dependency in the FastAPI app
    for the duration of a test.
    """
    async def _override_get_db():
        yield db_session
    return _override_get_db

# TestClient fixture
from fastapi.testclient import TestClient

@pytest.fixture(scope="function")
def client(override_get_db, test_settings) -> TestClient: # Added test_settings
    """
    Provides a TestClient instance for making HTTP requests to the FastAPI app.
    Ensures that database dependencies are overridden with the test session.
    """
    # Override settings for the app instance if necessary,
    # though ideally settings are injected or read fresh.
    # For now, assume security functions will use patched settings (see test_security.py)
    app.dependency_overrides[get_db_session] = override_get_db
    
    # If your app's settings are module-level and read at import time in various places,
    # direct patching of those instances might be needed here or via autouse fixtures.
    # e.g., from app.core.security import settings as security_settings
    # monkeypatch.setattr(security_settings, 'SECRET_KEY', test_settings.SECRET_KEY)
    
    test_client = TestClient(app)
    yield test_client # Use yield to allow for teardown if TestClient had any
    app.dependency_overrides.clear() # Clear overrides after test
