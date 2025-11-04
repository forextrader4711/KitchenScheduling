from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from kitchen_scheduler.db.models.system import MonthlyParameters, SchedulingRuleConfig
from kitchen_scheduler.schemas.system import (
    MonthlyParametersCreate,
    MonthlyParametersUpdate,
    SchedulingRuleConfigCreate,
    SchedulingRuleConfigUpdate,
)


async def list_monthly_parameters(session: AsyncSession) -> list[MonthlyParameters]:
    result = await session.execute(select(MonthlyParameters))
    return list(result.scalars().all())


async def create_monthly_parameters(
    session: AsyncSession, payload: MonthlyParametersCreate
) -> MonthlyParameters:
    parameters = MonthlyParameters(**payload.model_dump())
    session.add(parameters)
    await session.flush()
    await session.refresh(parameters)
    return parameters


async def get_monthly_parameters(
    session: AsyncSession, parameters_id: int
) -> MonthlyParameters | None:
    return await session.get(MonthlyParameters, parameters_id)


async def update_monthly_parameters(
    session: AsyncSession,
    parameters: MonthlyParameters,
    payload: MonthlyParametersUpdate,
) -> MonthlyParameters:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(parameters, field, value)
    await session.flush()
    await session.refresh(parameters)
    return parameters


async def delete_monthly_parameters(session: AsyncSession, parameters: MonthlyParameters) -> None:
    await session.delete(parameters)


async def get_active_rule_config(session: AsyncSession) -> SchedulingRuleConfig | None:
    result = await session.execute(
        select(SchedulingRuleConfig)
        .where(SchedulingRuleConfig.is_active.is_(True))
        .order_by(SchedulingRuleConfig.updated_at.desc())
    )
    return result.scalars().first()


async def get_rule_config(session: AsyncSession, config_id: int) -> SchedulingRuleConfig | None:
    return await session.get(SchedulingRuleConfig, config_id)


async def create_rule_config(
    session: AsyncSession, payload: SchedulingRuleConfigCreate
) -> SchedulingRuleConfig:
    if payload.is_active:
        await session.execute(update(SchedulingRuleConfig).values(is_active=False))
    config = SchedulingRuleConfig(
        name=payload.name,
        version=payload.version,
        rules=payload.rules.model_dump(),
        is_active=payload.is_active,
    )
    session.add(config)
    await session.flush()
    await session.refresh(config)
    return config


async def update_rule_config(
    session: AsyncSession,
    config: SchedulingRuleConfig,
    payload: SchedulingRuleConfigUpdate,
) -> SchedulingRuleConfig:
    data = payload.model_dump(exclude_unset=True)
    if data.get("is_active"):
        await session.execute(
            update(SchedulingRuleConfig)
            .where(SchedulingRuleConfig.id != config.id)
            .values(is_active=False)
        )
    for field, value in data.items():
        if field == "rules" and value is not None:
            setattr(config, field, value.model_dump())
        else:
            setattr(config, field, value)
    await session.flush()
    await session.refresh(config)
    return config
