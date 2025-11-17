from datetime import datetime
from typing import Any, List, Literal

from pydantic import BaseModel, ConfigDict, Field

from kitchen_scheduler.schemas.resource import PlanningEntryRead


class PlanScenarioBase(BaseModel):
    month: str  # YYYY-MM
    name: str = "Draft"
    status: str = "draft"


class PlanScenarioCreate(PlanScenarioBase):
    entries: List[PlanningEntryRead] = []


class PlanScenarioRead(PlanScenarioBase):
    id: int
    created_at: datetime
    updated_at: datetime
    violations: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class PlanScenarioUpdate(BaseModel):
    name: str | None = None
    status: str | None = None


class PlanGenerationRelaxations(BaseModel):
    """Optional relaxations planners can request when generating a plan."""

    minimum_daily_staff_delta: int | None = None
    role_minimum_deltas: dict[str, int] | None = None
    max_hours_per_week_delta: int | None = None
    max_working_days_per_week_delta: int | None = None
    max_consecutive_working_days_delta: int | None = None


class PlanGenerationRequest(BaseModel):
    month: str
    label: str | None = None
    relaxations: PlanGenerationRelaxations | None = None


class PlanViolation(BaseModel):
    code: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"
    meta: dict[str, Any] = Field(default_factory=dict)
    scope: Literal["schedule", "day", "resource", "week", "month"] = "schedule"
    day: str | None = None
    resource_id: int | None = None
    iso_week: str | None = None


class StaffingShortfallDiagnostic(BaseModel):
    date: str
    required: int
    available: int


class RoleShortfallDiagnostic(BaseModel):
    date: str
    role: str
    required: int
    available: int


class ResourceCapacityDiagnostic(BaseModel):
    resource_id: int
    resource_name: str | None = None
    required_hours: float
    available_hours: float


class PlanGenerationDiagnostics(BaseModel):
    summary: str | None = None
    staffing: list[StaffingShortfallDiagnostic] = Field(default_factory=list)
    roles: list[RoleShortfallDiagnostic] = Field(default_factory=list)
    capacity: list[ResourceCapacityDiagnostic] = Field(default_factory=list)


class PlanGenerationResponse(BaseModel):
    entries: List[PlanningEntryRead]
    violations: List[PlanViolation] = Field(default_factory=list)
    engine: Literal["optimizer", "heuristic", "manual"] = "heuristic"
    status: Literal["success", "fallback", "error"] = "success"
    duration_ms: int | None = None
    diagnostics: PlanGenerationDiagnostics | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanVersionRead(BaseModel):
    id: int
    scenario_id: int
    version_label: str
    published_at: datetime | None
    published_by: str | None
    summary_hours: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanScenarioSummary(BaseModel):
    id: int
    month: str
    name: str
    status: str
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanInsightItem(BaseModel):
    severity: Literal["info", "warning", "critical"]
    violations: list[PlanViolation] = Field(default_factory=list)


class PlanInsights(BaseModel):
    daily: dict[str, PlanInsightItem] = Field(default_factory=dict)
    resource: dict[int, PlanInsightItem] = Field(default_factory=dict)
    weekly: dict[str, PlanInsightItem] = Field(default_factory=dict)
    monthly: dict[str, PlanInsightItem] = Field(default_factory=dict)


class RuleStatus(BaseModel):
    code: str
    translation_key: str
    status: Literal["ok", "warning", "critical"]
    violations: list[PlanViolation] = Field(default_factory=list)


class PlanSuggestedChange(BaseModel):
    action: Literal["assign_shift", "set_rest_day", "remove_assignment"]
    resource_id: int
    date: str  # ISO date
    shift_code: int | None = None
    absence_type: str | None = None


class PlanSuggestion(BaseModel):
    id: str
    type: str
    title: str
    description: str
    severity: Literal["info", "warning", "critical"] = "warning"
    related_violation: str | None = None
    change: PlanSuggestedChange | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanSummaryItem(BaseModel):
    resource_id: int
    resource_name: str
    actual_hours: float
    due_hours: float
    due_real_hours: float
    opening_balance_hours: float
    closing_balance_hours: float
    working_days: int
    vacation_days: int


class PlanPhaseRead(BaseModel):
    scenario: PlanScenarioSummary | None = None
    entries: list[PlanningEntryRead] = Field(default_factory=list)
    violations: list[PlanViolation] = Field(default_factory=list)
    insights: PlanInsights = Field(default_factory=PlanInsights)
    rule_statuses: list[RuleStatus] = Field(default_factory=list)
    suggestions: list[PlanSuggestion] = Field(default_factory=list)
    summaries: list[PlanSummaryItem] = Field(default_factory=list)


class PlanOverviewResponse(BaseModel):
    month: str
    preparation: PlanPhaseRead | None = None
    approved: PlanPhaseRead | None = None
    holidays: list[str] = Field(default_factory=list)
