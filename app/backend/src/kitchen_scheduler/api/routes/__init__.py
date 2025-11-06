from fastapi import APIRouter

from . import auth, planning, resources, shifts, system, versions

api_router = APIRouter()

api_router.include_router(system.router, prefix="/system", tags=["system"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(shifts.router, prefix="/shifts", tags=["shifts"])
api_router.include_router(planning.router, prefix="/planning", tags=["planning"])
api_router.include_router(versions.router, prefix="/planning", tags=["plan_versions"])
