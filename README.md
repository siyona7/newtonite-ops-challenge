# Operations Under Pressure

An internal web application for teams to create and manage operational work items (incidents, payments, customer issues, compliance, tasks) with owners, priority, status, history, and approvals.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Pydantic v2, async SQLAlchemy 2.0 + Alembic, PostgreSQL
- **Testing**: pytest, pytest-asyncio, httpx
- **Frontend** (later phases): React + TypeScript + Vite + TanStack Query + Tailwind
- **Package Manager**: uv

## Prerequisites

- Python 3.12+ (managed by uv)
- PostgreSQL 14+ (for local development)
- Windows 11 with PowerShell

## Installation

1. **Clone the repository** (if not already cloned):
   ```powershell
   git clone https://github.com/siyona7/newtonite-ops-challenge.git
   cd newtonite-ops-challenge
   ```

2. **Install dependencies with uv**:
   ```powershell
   uv sync
   ```

3. **Set up environment variables**:
   ```powershell
   Copy-Item .env.example .env
   ```
   Then edit `.env` with your actual database credentials.

4. **Set up PostgreSQL**:

   **Option A: Using Docker Compose (Recommended)**
   ```powershell
   # Start PostgreSQL container
   docker-compose up -d

   # Wait for database to be ready (check healthcheck)
   docker-compose logs postgres

   # Run database migrations
   uv run alembic upgrade head

   # Seed the database with test data (50,000 items)
   uv run python scripts/seed.py
   ```

   **Option B: Local PostgreSQL**
   - Ensure PostgreSQL is running locally
   - Create a database:
     ```powershell
     # Using psql
     psql -U postgres -c "CREATE DATABASE ops_challenge;"
     ```
   - Update `DATABASE_URL` in `.env` to match your PostgreSQL credentials
   - Run migrations: `uv run alembic upgrade head`
   - Seed data: `uv run python scripts/seed.py`

## Running the Application

Start the development server:
```powershell
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## Running Tests

Run all tests:
```powershell
uv run pytest
```

Run tests with coverage:
```powershell
uv run pytest --cov=app --cov=tests
```

Run specific test file:
```powershell
uv run pytest tests/test_health.py
```

## API Documentation

Once the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Health Check

Test the health endpoint:
```powershell
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "Operations Under Pressure",
  "version": "0.1.0"
}
```

## Docker (Optional)

Docker Compose is available for containerized deployments.

### PowerShell Commands for Docker Setup

Once Docker Desktop is installed and running:

```powershell
# 1. Copy environment variables template
Copy-Item .env.example .env

# 2. Start PostgreSQL container
docker-compose up -d

# 3. Wait for database to be ready (check healthcheck logs)
docker-compose logs postgres

# 4. Run database migrations
uv run alembic upgrade head

# 5. Seed the database with test data (50,000 items)
uv run python scripts/seed.py

# 6. Start the application
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Docker Commands

```powershell
# View container logs
docker-compose logs postgres

# Stop containers
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v

# Restart containers
docker-compose restart
```

Note: Docker is not required for local development but is recommended for consistent database setup.

## Project Structure

```
newtonite-ops-challenge/
├── app/                # Application source code
│   ├── main.py        # FastAPI application entry point
│   ├── config.py      # Configuration settings
│   ├── db/            # Database configuration
│   │   ├── base.py    # SQLAlchemy base model
│   │   └── session.py # Async session management
│   └── models/        # SQLAlchemy ORM models
│       ├── user.py    # User, TeamMember models
│       ├── team.py    # Team model
│       ├── item.py    # Item model with enums
│       ├── event.py   # Event model
│       └── outbox.py  # Outbox message model
├── tests/             # Test suite
│   └── test_health.py # Health endpoint tests
├── scripts/           # Utility scripts
│   └── seed.py        # Database seeding script
├── alembic/           # Database migrations
│   ├── versions/      # Migration files
│   └── env.py         # Alembic environment config
├── docs/              # Documentation
│   └── STUDY_NOTES.md # Phase-by-phase learning notes
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
├── docker-compose.yml # Docker Compose configuration
├── Dockerfile         # Docker image definition
├── pyproject.toml     # Project dependencies and metadata
└── README.md          # This file
```

## Development Phases

This project is built in phases:
1. ✅ Scaffold + health endpoint + README
2. Database schema, migrations, seed data
3. Login + roles + authorization module + tests
4. Items CRUD with versions + events + paginated list
5. Behaviors 1-4 (atomic claim, stale edits, idempotency, workflow/auth) with tests
6. Comments/history
7. Outbox worker + tests
8. Dashboard/search/scale proof
9. Frontend (React + TypeScript)
10. Documentation (README, ENGINEERING_DECISIONS.md, KNOWN_LIMITATIONS.md)

## Key Features

- **Atomic claim**: Single conditional UPDATE prevents race conditions
- **Stale edits**: Version control with If-Match header
- **Idempotency**: Idempotency-Key header prevents duplicate operations
- **Workflow enforcement**: Per-team roles and status-transition validation
- **Append-only history**: All changes recorded as events
- **Background jobs**: Postgres outbox pattern with retries
- **Scale**: Keyset pagination, full-text search, 50,000 seed items

## License

Internal use only.
