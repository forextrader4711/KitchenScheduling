from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import shift as shift_repo
from kitchen_scheduler.schemas.resource import ShiftCreate, ShiftRead, ShiftUpdate

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


@router.put("/{shift_code}", response_model=ShiftRead)
async def update_shift(
    shift_code: int,
    payload: ShiftUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ShiftRead:
    shift = await shift_repo.get_shift(session, shift_code)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    shift = await shift_repo.update_shift(session, shift, payload)
    await session.commit()
    return ShiftRead.model_validate(shift)


@router.delete("/{shift_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_code: int, session: Annotated[AsyncSession, Depends(get_db_session)]
) -> None:
    shift = await shift_repo.get_shift(session, shift_code)
    if not shift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shift not found")
    await shift_repo.delete_shift(session, shift)
    await session.commit()
