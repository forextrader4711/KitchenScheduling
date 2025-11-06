from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.core.config import Settings, get_settings
from kitchen_scheduler.db.session import get_db_session
from kitchen_scheduler.repositories import system as system_repo
from kitchen_scheduler.schemas.system import (
    HolidayRead,
    MonthlyParametersCreate,
    MonthlyParametersRead,
    MonthlyParametersUpdate,
    SchedulingRuleConfigCreate,
    SchedulingRuleConfigRead,
    SchedulingRuleConfigUpdate,
)
from kitchen_scheduler.services.holidays import get_vaud_public_holidays
from kitchen_scheduler.services.rules import SchedulingRules, load_default_rules

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


@router.get("/monthly-parameters", response_model=list[MonthlyParametersRead])
async def list_monthly_parameters(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> list[MonthlyParametersRead]:
    parameters = await system_repo.list_monthly_parameters(session)
    return [MonthlyParametersRead.model_validate(item) for item in parameters]


@router.post(
    "/monthly-parameters",
    response_model=MonthlyParametersRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_monthly_parameters(
    payload: MonthlyParametersCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MonthlyParametersRead:
    parameters = await system_repo.create_monthly_parameters(session, payload)
    await session.commit()
    return MonthlyParametersRead.model_validate(parameters)


@router.put("/monthly-parameters/{parameters_id}", response_model=MonthlyParametersRead)
async def update_monthly_parameters(
    parameters_id: int,
    payload: MonthlyParametersUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> MonthlyParametersRead:
    parameters = await system_repo.get_monthly_parameters(session, parameters_id)
    if not parameters:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monthly parameters not found")
    parameters = await system_repo.update_monthly_parameters(session, parameters, payload)
    await session.commit()
    return MonthlyParametersRead.model_validate(parameters)


@router.delete("/monthly-parameters/{parameters_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monthly_parameters(
    parameters_id: int,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    parameters = await system_repo.get_monthly_parameters(session, parameters_id)
    if not parameters:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Monthly parameters not found")
    await system_repo.delete_monthly_parameters(session, parameters)
    await session.commit()


def _map_rule_config(config) -> SchedulingRuleConfigRead:
    return SchedulingRuleConfigRead(
        id=config.id,
        name=config.name,
        version=config.version,
        rules=SchedulingRules.model_validate(config.rules),
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/rules/active", response_model=SchedulingRuleConfigRead)
async def read_active_rules(
    session: Annotated[AsyncSession, Depends(get_db_session)]
) -> SchedulingRuleConfigRead:
    config = await system_repo.get_active_rule_config(session)
    if not config:
        payload = SchedulingRuleConfigCreate(rules=load_default_rules().rules)
        config = await system_repo.create_rule_config(session, payload)
        await session.commit()
    return _map_rule_config(config)


@router.get("/holidays", response_model=list[HolidayRead])
async def list_holidays(year: int | None = Query(default=None)) -> list[HolidayRead]:
    target_year = year or datetime.utcnow().year
    holidays = get_vaud_public_holidays(target_year)
    return [HolidayRead.model_validate(item) for item in holidays]


@router.post("/rules", response_model=SchedulingRuleConfigRead, status_code=status.HTTP_201_CREATED)
async def create_rule_config(
    payload: SchedulingRuleConfigCreate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SchedulingRuleConfigRead:
    config = await system_repo.create_rule_config(session, payload)
    await session.commit()
    return _map_rule_config(config)


@router.put("/rules/{config_id}", response_model=SchedulingRuleConfigRead)
async def update_rule_config(
    config_id: int,
    payload: SchedulingRuleConfigUpdate,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> SchedulingRuleConfigRead:
    config = await system_repo.get_rule_config(session, config_id)
    if not config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule configuration not found")
    config = await system_repo.update_rule_config(session, config, payload)
    await session.commit()
    return _map_rule_config(config)
