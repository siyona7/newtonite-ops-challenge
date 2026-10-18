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
