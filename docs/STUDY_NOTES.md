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


## Phase 3: Login, Roles, Authorization

### What Was Built

**Schema Additions** (Migration `41ba727beb2c`)
- Added `password_hash` column to `users` table for authentication
- Created `idempotency_keys` table for idempotent request handling
- Created `comments` table for item comments
- Created `notifications` table for user notifications
- Added `search_vector` column to `items` with GIN index for full-text search
- Created PostgreSQL trigger function to auto-update `search_vector` on item insert/update
- Created PostgreSQL trigger function to prevent updates/deletes on `events` (append-only enforcement)

**Authentication Module** (`app/auth/`)
- `security.py`: Password hashing with argon2, JWT token creation/verification
- `authorization.py`: Central `authorize()` function with permission matrix
  - Role-based permissions: VIEWER (read, comment), MEMBER (read, create, update, claim, comment), LEAD/ADMIN (all actions)
  - Cross-team access returns ValueError (404 scenario)
  - Resource validation (404 if not found)
- `dependencies.py`: FastAPI dependencies for `get_current_user` and `get_optional_user` from JWT cookie

**API Endpoints** (`app/routers/auth.py`)
- `POST /auth/login`: Email/password login, sets httpOnly JWT cookie (7-day expiry)
- `POST /auth/logout`: Clears JWT cookie
- `GET /auth/me`: Returns current user info with team memberships

**Test Suite** (`tests/test_authorization.py`)
- `test_permission_matrix`: Validates all 4 roles have correct permissions for all actions
- `test_cross_team_access_returns_404`: Users from one team cannot access another team's resources
- `test_nonexistent_resource_returns_404`: Accessing nonexistent resources raises ValueError
- `test_get_team_memberships`: Validates user can belong to multiple teams with different roles
- `test_viewer_cannot_delete`: Viewers cannot delete items
- `test_admin_can_approve`: Admins can approve items

### Why This Approach

- **Argon2 for password hashing**: Memory-hard algorithm resistant to GPU/ASIC attacks, recommended by OWASP
- **JWT in httpOnly cookie**: Prevents XSS attacks while maintaining session state, more secure than localStorage
- **Centralized authorization**: Single `authorize()` function enforces consistent permission checks across all endpoints
- **404 for cross-team access**: Security by obscurity - users don't learn about resources they can't access
- **PostgreSQL triggers for append-only**: Database-level enforcement prevents accidental event modification even if application logic fails
- **Full-text search with TSVECTOR**: Native PostgreSQL text search with GIN index for efficient querying
- **Idempotency keys table**: Prevents duplicate operations on network retries without distributed locks

### Reviewer Questions

**Q1: Why use httpOnly cookies instead of Authorization header for JWT?**
A: httpOnly cookies prevent XSS attacks - JavaScript cannot read the token, unlike localStorage. The cookie is automatically sent with requests, reducing boilerplate. The trade-off is CSRF vulnerability, which can be mitigated with SameSite attribute (set to 'lax') and CSRF tokens for state-changing operations. For this application, the security benefits outweigh the complexity.

**Q2: Why enforce append-only at the database level with a trigger instead of just in application code?**
A: Database-level enforcement provides defense in depth. If application code has a bug or if someone runs raw SQL updates, the trigger still prevents modification. This is especially important for audit trails where event integrity is critical. The trade-off is slightly more complex migrations, but the security benefit is worth it for compliance requirements.

**Q3: Why use a permission matrix instead of checking roles inline in each endpoint?**
A: A centralized permission matrix is easier to maintain and audit. When adding a new role or action, you only update one place (`ROLE_PERMISSIONS`). It also makes authorization logic testable independently of endpoints. The trade-off is slightly more indirection, but the maintainability benefit is significant for a system with multiple roles and actions.

### Break-It Drills

**Drill 1: Make authorization fail by removing a permission from the matrix**
- File: `app/auth/authorization.py`
- Change: Remove `Action.READ` from `Role.VIEWER` in `ROLE_PERMISSIONS`
- Result: The `test_permission_matrix` test will fail because viewers should be able to read but cannot

**Drill 2: Make login fail by breaking JWT cookie setting**
- File: `app/routers/auth.py`
- Change: Change `httponly=True` to `httponly=False` in the `response.set_cookie()` call
- Result: The authentication will still work, but the security test (if added) would fail because the cookie is accessible to JavaScript
