import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.testclient import TestClient
from app.db.session import AsyncSessionLocal, engine
from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Create a test database session if database is reachable, else skip."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        pytest.skip(f"PostgreSQL database connection refused: {exc}")

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
