from typing import Annotated

from fastapi import APIRouter, Depends

from kitchen_scheduler.core.config import Settings, get_settings

router = APIRouter()


@router.get("/settings")
async def read_settings(
    settings: Annotated[Settings, Depends(get_settings)]
) -> dict[str, str]:
    """Expose basic runtime metadata for diagnostics."""
    return {
        "environment": settings.environment,
        "project": settings.project_name,
        "version": settings.version,
    }
