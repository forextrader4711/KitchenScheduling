from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.schemas.resource import ShiftCreate, ShiftRead

router = APIRouter()


@router.get("/", response_model=list[ShiftRead])
async def list_shifts(session: Annotated[AsyncSession, Depends(get_db_session)]) -> list[ShiftRead]:
    shifts = await shift_repo.list_shifts(session)
    return [ShiftRead.model_validate(shift) for shift in shifts]


@router.post("/", response_model=ShiftRead, status_code=status.HTTP_201_CREATED)
async def create_shift(
    payload: ShiftCreate, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> ShiftRead:
    shift = await shift_repo.create_shift(session, payload)
    await session.commit()
    return ShiftRead.model_validate(shift)
