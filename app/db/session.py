from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import settings

# Create async engine for PostgreSQL
engine = create_async_engine(
    settings.database_url,
    echo=False,  # Set to True for SQL query logging during development
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,  # Connection pool size
    max_overflow=20,  # Additional connections when pool is exhausted
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Prevent objects from being expired after commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncSession:
    """
    Dependency for FastAPI to get database session.
    Yields a session and ensures it's closed after the request.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
