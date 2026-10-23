import pytest
import pytest_asyncio
import os
import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from fastapi.testclient import TestClient
from app.config import settings
from app.db.session import engine
from app.main import app


@pytest.fixture
def client():
    """Create a FastAPI test client."""
    return TestClient(app)


# Override database URL for tests to use a separate test database
test_database_url = settings.database_url.replace("/ops_challenge", "/ops_challenge_test")
os.environ["DATABASE_URL"] = test_database_url

# Create a separate engine for the test database
test_engine = create_async_engine(
    test_database_url,
    echo=False,
    pool_pre_ping=True,
    poolclass=NullPool,  # Use NullPool for tests to avoid connection issues
)

TestSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="session")
async def setup_test_database():
    """Create the test database and run migrations."""
    # Connect to the default postgres database to create the test database
    default_db_url = settings.database_url.replace("/ops_challenge", "/postgres")
    default_engine = create_async_engine(default_db_url, poolclass=NullPool)
    
    # Use a connection in autocommit mode for DROP/CREATE DATABASE
    async with default_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        try:
            # Drop if exists first to ensure clean state
            await conn.execute(text("DROP DATABASE IF EXISTS ops_challenge_test"))
            # Create the test database
            await conn.execute(text("CREATE DATABASE ops_challenge_test"))
        except Exception as e:
            print(f"Error creating test database: {e}")
            raise
        finally:
            await conn.close()
    
    await default_engine.dispose()
    
    # Run migrations on the test database using alembic command
    import subprocess
    
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd="C:\\Users\\Siyona\\Documents\\newtonite-ops-challenge",
        env={**os.environ, "DATABASE_URL": test_database_url},
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        print(f"Migration failed: {result.stderr}")
        print(f"Migration stdout: {result.stdout}")
        raise Exception("Migration failed")
    
    yield
    
    # Cleanup: Drop the test database
    default_engine = create_async_engine(default_db_url, poolclass=NullPool)
    async with default_engine.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        # Terminate all connections to the test database
        await conn.execute(text("""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = 'ops_challenge_test'
            AND pid <> pg_backend_pid()
        """))
        await conn.execute(text("DROP DATABASE IF EXISTS ops_challenge_test"))
        await conn.close()
    
    await default_engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(setup_test_database):
    """Create a test database session with table truncation for isolation."""
    async with TestSessionLocal() as session:
        yield session
        # Truncate all tables after each test to ensure isolation
        await session.execute(text("""
            TRUNCATE TABLE 
                team_members, 
                items, 
                events, 
                outbox_messages, 
                users, 
                teams,
                comments,
                notifications,
                idempotency_keys
            RESTART IDENTITY CASCADE
        """))
        await session.commit()
