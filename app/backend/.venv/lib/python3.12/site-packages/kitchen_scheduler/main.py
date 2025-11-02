from fastapi import FastAPI

from kitchen_scheduler.api.routes import api_router
from kitchen_scheduler.core.config import get_settings


def create_application() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.project_name,
        version=settings.version,
        description="API for generating and managing professional kitchen schedules.",
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_application()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health endpoint for infrastructure monitoring."""
    return {"status": "ok"}
