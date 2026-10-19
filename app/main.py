from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.config import settings
from app.routers import auth, items

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

# Include routers
app.include_router(auth.router)
app.include_router(items.router)
app.add_api_route("/me", auth.get_me, methods=["GET"], response_model=auth.UserResponse, tags=["authentication"])


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Map ValueError from authorization to 404 per system design."""
    return JSONResponse(
        status_code=404,
        content={"detail": str(exc)},
    )


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }
