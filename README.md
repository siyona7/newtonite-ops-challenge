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
   - Ensure PostgreSQL is running locally
   - Create a database:
     ```powershell
     # Using psql
     psql -U postgres -c "CREATE DATABASE ops_challenge;"
     ```
   - Update `DATABASE_URL` in `.env` to match your PostgreSQL credentials

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

Docker Compose is available for containerized deployments:
```powershell
docker-compose up -d
```

Note: Docker is not required for local development.

## Project Structure

```
newtonite-ops-challenge/
├── app/                # Application source code
│   ├── main.py        # FastAPI application entry point
│   └── config.py      # Configuration settings
├── tests/             # Test suite
│   └── test_health.py # Health endpoint tests
├── docs/              # Documentation
│   └── STUDY_NOTES.md # Phase-by-phase learning notes
├── .env.example       # Environment variables template
├── .gitignore         # Git ignore rules
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
