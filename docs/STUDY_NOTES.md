# Study Notes

## Phase 1: Scaffold + Health Endpoint + README

### What Was Built

**Project Setup**
- Initialized a Python 3.12 project using `uv` package manager
- Created directory structure: `app/` (application code), `tests/` (test suite), `docs/` (documentation)
- Configured FastAPI with health check endpoint at `/health`
- Set up basic configuration management using Pydantic Settings
- Added `.env.example` template for environment variables
- Created comprehensive README with setup and run instructions
- Added `.gitignore` to exclude sensitive files and build artifacts

**Health Endpoint** (`app/main.py`)
- Simple GET endpoint at `/health` that returns service status
- Returns JSON with status, service name, and version
- Used for monitoring and load balancer health checks

**Configuration** (`app/config.py`)
- Pydantic Settings class for type-safe configuration
- Loads from environment variables and `.env` file
- Default database URL for PostgreSQL connection
- App name and version metadata

**Testing** (`tests/test_health.py`)
- Basic test for health endpoint using FastAPI TestClient
- Verifies 200 status code and expected response structure
- Uses pytest as the test framework

### Why This Approach

- **uv package manager**: Fast, modern Python package manager that handles dependencies and virtual environments automatically
- **FastAPI**: Modern async web framework with automatic OpenAPI documentation
- **Pydantic Settings**: Type-safe configuration that validates at startup
- **Separate app directory**: Keeps application code isolated from project root
- **Environment variables**: Standard practice for managing secrets and config

### Reviewer Questions

**Q1: Why use uv instead of pip/poetry?**
A: uv is significantly faster than pip (10-100x) and simpler than Poetry. It manages both dependencies and virtual environments in one tool, has better lockfile support, and is the modern recommended approach for Python projects. It also handles Python version management, which is helpful for ensuring Python 3.12 is used.

**Q2: Why is the app code in an `app/` directory instead of `src/`?**
A: The project was initialized with `uv init` which creates a `src/` directory by default, but I created an `app/` directory separately for the application code. This is a common pattern to separate library code (`src/`) from application code (`app/`). For this web application, `app/` is more conventional as it clearly indicates this is an application, not a reusable library.

**Q3: Why use Pydantic Settings instead of reading environment variables directly with os.getenv?**
A: Pydantic Settings provides type safety, automatic validation, and better IDE support. It converts environment variables to the correct types (strings, ints, etc.) and will fail fast at startup if required variables are missing or invalid. This prevents runtime errors and makes configuration more maintainable.

### Break-It Drills

**Drill 1: Make `test_health_check` fail by changing the health endpoint response**
- File: `app/main.py`
- Change: Change `"status": "healthy"` to `"status": "unhealthy"` on line 14
- Result: The test assertion `assert data["status"] == "healthy"` will fail

**Drill 2: Make `test_health_check` fail by removing a required field**
- File: `app/main.py`
- Change: Delete the line `"version": settings.app_version,` from the return dictionary
- Result: The test assertion `assert "version" in data` will fail


## Phase 2: Database Schema, Migrations, Seed Data

### What Was Built

**Database Models** (`app/models/`)
- `User`: User accounts with email, name, and timestamps
- `Team`: Team/group representation with unique names
- `TeamMember`: Junction table linking users to teams with roles (viewer, member, lead, admin)
- `Item`: Operational work items with type, priority, status, version (for stale edit detection), and metadata
- `Event`: Append-only event log for all item changes with old/new state snapshots
- `OutboxMessage`: Outbox pattern table for reliable background job processing with retry logic

**Database Connection** (`app/db/`)
- `base.py`: SQLAlchemy DeclarativeBase for all models
- `session.py`: Async engine configuration with connection pooling, async session factory, and FastAPI dependency

**Alembic Migrations** (`alembic/`)
- Configured for async PostgreSQL with asyncpg driver
- Modified `env.py` to load models from `app.models` and use async engine
- Created initial migration with all tables, indexes, and foreign key constraints
- Migration includes proper cascade deletes (CASCADE, SET NULL) for data integrity

**Seed Script** (`scripts/seed.py`)
- Creates 5 teams and 15 users with team memberships
- Generates 50,000 items in batches of 1,000 to avoid memory issues
- Items have realistic data: random types, priorities, statuses, dates within last 90 days
- Creates sample events for 1,000 items (not all 50k to save time)
- Uses async SQLAlchemy for efficient bulk inserts

**Docker Configuration**
- `docker-compose.yml`: PostgreSQL 16 Alpine container with healthcheck and volume persistence
- `Dockerfile`: Multi-stage build for the application (for future use)

### Why This Approach

- **UUID primary keys**: Better for distributed systems, harder to guess, no sequential pattern
- **Async SQLAlchemy 2.0**: Modern async ORM that integrates well with FastAPI, prevents blocking the event loop
- **Connection pooling**: 10 base connections with 20 overflow for handling concurrent requests efficiently
- **Batch inserts in seed script**: Prevents memory exhaustion when inserting 50,000 records
- **Outbox pattern**: Ensures reliable background job processing by writing to a table first, then processing
- **Foreign key cascades**: Automatic cleanup of related data (CASCADE) or nullification (SET NULL) for referential integrity
- **Indexes on foreign keys and query columns**: Optimizes common query patterns (team_id, status, created_at)
- **Composite indexes**: Support multi-column queries (team_id + status, priority + status)

### Reviewer Questions

**Q1: Why use UUIDs instead of auto-increment integers for primary keys?**
A: UUIDs are better for distributed systems because they can be generated without coordination, don't expose record counts, and are harder to guess for security. They also allow merging data from different sources without ID conflicts. The trade-off is slightly larger storage and slightly slower indexing, but for this application the benefits outweigh the costs.

**Q2: Why use the outbox pattern instead of directly publishing events?**
A: The outbox pattern ensures exactly-once delivery of events by writing the event to the database in the same transaction as the business operation. This prevents lost events if the message broker is down or if the application crashes after the database commit but before publishing. A background worker then processes the outbox table and publishes events with retry logic. The trade-off is slight complexity and latency, but it's the gold standard for reliable event publishing.

**Q3: Why seed 50,000 items instead of fewer?**
A: This proves the application can handle scale and validates that pagination, filtering, and search work correctly with realistic data volumes. It also tests database performance with larger datasets. The seed script uses batch inserts (1,000 at a time) to avoid memory issues, demonstrating the importance of batching for bulk operations.

### Break-It Drills

**Drill 1: Make migration fail by removing a required column**
- File: `alembic/versions/6f3ade99d56e_initial_schema.py`
- Change: Delete the line `sa.Column('title', sa.String(500), nullable=False),` from the items table
- Result: The seed script will fail when trying to create items without a title (SQLAlchemy will complain about missing required field)

**Drill 2: Make seed script fail by breaking the foreign key constraint**
- File: `scripts/seed.py`
- Change: Change `team_id=random.choice(team_ids)` to `team_id=uuid.uuid4()` (using a random UUID not in the database)
- Result: The database will reject the insert due to foreign key constraint violation (team_id must reference an existing team)
