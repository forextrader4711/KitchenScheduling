import { create } from "zustand";

import api from "../services/api";
import {
  PlanningEntry,
  PlanSuggestedChange,
  Resource,
  ResourceAbsence,
  SummaryItem,
  ViolationItem,
  WeeklyAvailabilityEntry
} from "../types";

type ResourceDto = {
  id: number;
  name: string;
  role: string;
  availability_percent: number;
  contract_hours_per_month: number;
  preferred_days_off?: string | null;
  vacation_days?: string | null;
  language: string;
  notes?: string | null;
  availability_template?: WeeklyAvailabilityEntryDto[] | null;
  preferred_shift_codes?: number[] | null;
  undesired_shift_codes?: number[] | null;
  absences?: ResourceAbsenceDto[];
};

type WeeklyAvailabilityEntryDto = {
  day: string;
  is_available: boolean;
  start_time?: string | null;
  end_time?: string | null;
};

type ResourceAbsenceDto = {
  id: number;
  start_date: string;
  end_date: string;
  absence_type: "vacation" | "sick_leave" | "training" | "other";
  comment?: string | null;
};

type PlanningEntryDto = {
  id: number;
  resource_id: number;
  date: string;
  shift_code?: number | null;
  absence_type?: string | null;
  comment?: string | null;
};

type PlanViolationDto = {
  code: string;
  message: string;
  severity: "info" | "warning" | "critical";
  meta?: Record<string, unknown>;
  scope?: "schedule" | "day" | "resource" | "week" | "month";
  day?: string | null;
  resource_id?: number | null;
  iso_week?: string | null;
};

type PlanScenarioSummaryDto = {
  id: number;
  month: string;
  name: string;
  status: string;
  updated_at: string;
};

type PlanPhaseDto = {
  scenario?: PlanScenarioSummaryDto | null;
  entries: PlanningEntryDto[];
  violations: PlanViolationDto[];
  insights?: PlanInsightsDto;
  rule_statuses?: RuleStatusDto[];
  suggestions?: PlanSuggestionDto[];
  summaries?: PlanSummaryDto[];
};

type PlanOverviewDto = {
  month: string;
  preparation?: PlanPhaseDto | null;
  approved?: PlanPhaseDto | null;
  holidays?: string[];
};

type PlanInsightItemDto = {
  severity: "info" | "warning" | "critical";
  violations: PlanViolationDto[];
};

type PlanInsightsDto = {
  daily: Record<string, PlanInsightItemDto>;
  resource: Record<string, PlanInsightItemDto>;
  weekly: Record<string, PlanInsightItemDto>;
  monthly: Record<string, PlanInsightItemDto>;
};

type RuleStatusDto = {
  code: string;
  translation_key: string;
  status: "ok" | "warning" | "critical";
  violations: PlanViolationDto[];
};

type PlanSuggestedChangeDto = {
  action: "assign_shift" | "set_rest_day" | "remove_assignment";
  resource_id: number;
  date: string;
  shift_code?: number | null;
  absence_type?: string | null;
};

type PlanSuggestionDto = {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  related_violation?: string | null;
  change?: PlanSuggestedChangeDto | null;
  metadata?: Record<string, unknown>;
};

type PlanSummaryDto = {
  resource_id: number;
  resource_name: string;
  actual_hours: number;
  due_hours: number;
  due_real_hours: number;
  opening_balance_hours: number;
  closing_balance_hours: number;
  working_days: number;
  vacation_days: number;
};

type PlanVersionDto = {
  id: number;
  scenario_id: number;
  version_label: string;
  published_at: string | null;
  published_by: string | null;
  summary_hours: string | null;
  created_at: string;
};

type PlanPhaseState = {
  scenario: {
    id: number;
    name: string;
    status: string;
    updatedAt: string;
  } | null;
  entries: PlanningEntry[];
  violations: ViolationItem[];
  summaries: SummaryItem[];
  insights: PlanInsightsState;
  ruleStatuses: RuleStatusState[];
  versions: PlanVersionState[];
  suggestions: PlanSuggestionState[];
};

type PlanPhaseKey = "preparation" | "approved";

type PlanInsightsState = {
  daily: Record<string, PlanInsightStateItem>;
  resource: Record<number, PlanInsightStateItem>;
  weekly: Record<string, PlanInsightStateItem>;
  monthly: Record<string, PlanInsightStateItem>;
};

type PlanInsightStateItem = {
  severity: "info" | "warning" | "critical";
  violations: ViolationItem[];
};

type RuleStatusState = {
  code: string;
  translationKey: string;
  status: "ok" | "warning" | "critical";
  violations: ViolationItem[];
  count: number;
};

type PlanVersionState = {
  id: number;
  label: string;
  createdAt: string;
  summary: {
    entries?: number;
    violations?: number;
    critical_violations?: number;
  } | null;
};

type PlanSuggestionState = {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  relatedViolation?: string | null;
  change?: PlanSuggestedChange | null;
  metadata?: Record<string, unknown>;
};

interface ScheduleState {
  month: string | null;
  isLoading: boolean;
  resources: Resource[];
  plans: Record<PlanPhaseKey, PlanPhaseState | null>;
  activePhase: PlanPhaseKey;
  holidays: string[];
  setActivePhase: (phase: PlanPhaseKey) => void;
  loadInitialData: () => Promise<void>;
  refreshPreparationPlan: (label?: string) => Promise<void>;
  generateOptimisedPlan: (label?: string) => Promise<void>;
  refreshOverviewOnly: () => Promise<void>;
}

const fallbackResources: Resource[] = [
  {
    id: 1,
    name: "Alice Dupont",
    role: "cook",
    availabilityPercent: 100,
    contractHoursPerMonth: 160,
    language: "fr",
    availabilityTemplate: undefined,
    preferredShiftCodes: undefined,
    undesiredShiftCodes: undefined,
    absences: []
  },
  {
    id: 2,
    name: "Marc Leroy",
    role: "kitchen_assistant",
    availabilityPercent: 80,
    contractHoursPerMonth: 128,
    language: "fr",
    availabilityTemplate: undefined,
    preferredShiftCodes: undefined,
    undesiredShiftCodes: undefined,
    absences: []
  }
];

const fallbackEntries: PlanningEntry[] = [
  {
    id: 1,
    resourceId: 1,
    date: new Date().toISOString(),
    shiftCode: 1
  },
  {
    id: 2,
    resourceId: 2,
    date: new Date().toISOString(),
    shiftCode: 10
  }
];

const computeSummaries = (entries: PlanningEntry[], resources: Resource[]): SummaryItem[] => {
  const fallbackWorkingDays = 20;
  const due = fallbackWorkingDays * 8.3;
  const dueReal = fallbackWorkingDays * 8.5;
  return resources.map((resource) => {
    const worked = entries.filter((entry) => entry.resourceId === resource.id).length * 8;
    const opening = 0;
    const closing = opening + worked - due;
    return {
      resourceId: resource.id,
      name: resource.name,
      actualHours: worked,
      dueHours: due,
      dueRealHours: dueReal,
      openingBalanceHours: opening,
      closingBalanceHours: closing,
      workingDays: fallbackWorkingDays,
      vacationDays: 0
    };
  });
};

const hydrateViolation = (
  violation: PlanViolationDto,
  index: number,
  prefix: string
): ViolationItem => {
  const id = `${prefix}-${violation.code}-${index}`;
  return {
    id,
    category: violation.code,
    severity: violation.severity,
    message: violation.message,
    rawMessage: violation.message,
    meta: violation.meta ?? {},
    day: violation.day ?? null,
    resourceId:
      typeof violation.resource_id === "number"
        ? violation.resource_id
        : violation.resource_id
        ? Number.parseInt(String(violation.resource_id), 10) || null
        : null,
    isoWeek: violation.iso_week ?? null
  };
};

const normalizeWeeklyAvailability = (
  entries?: WeeklyAvailabilityEntryDto[] | null
): WeeklyAvailabilityEntry[] | undefined => {
  if (!entries) {
    return undefined;
  }
  return entries.map((entry) => ({
    day: entry.day as WeeklyAvailabilityEntry["day"],
    isAvailable: entry.is_available,
    startTime: entry.start_time ?? undefined,
    endTime: entry.end_time ?? undefined
  }));
};

const normalizeAbsences = (absences?: ResourceAbsenceDto[] | null): ResourceAbsence[] | undefined => {
  if (!absences) {
    return undefined;
  }
  return absences.map((absence) => ({
    id: absence.id,
    startDate: absence.start_date,
    endDate: absence.end_date,
    absenceType: absence.absence_type,
    comment: absence.comment ?? undefined
  }));
};

const mapPlanningEntry = (entry: PlanningEntryDto): PlanningEntry => ({
  id: entry.id,
  resourceId: entry.resource_id,
  date: entry.date,
  shiftCode: entry.shift_code,
  absenceType: entry.absence_type,
  comment: entry.comment
});

const mapViolations = (violations: PlanViolationDto[], prefix: string): ViolationItem[] =>
  violations.map((violation, index) => hydrateViolation(violation, index, prefix));

function mapInsights(insights: PlanInsightsDto | undefined): PlanInsightsState {
  if (!insights) {
    return { daily: {}, resource: {}, weekly: {}, monthly: {} };
  }

  const build = (
    source: Record<string, PlanInsightItemDto>,
    prefix: string
  ): Record<string, PlanInsightStateItem> => {
    return Object.entries(source ?? {}).reduce<Record<string, PlanInsightStateItem>>((acc, [key, value]) => {
      acc[key] = {
        severity: value.severity,
        violations: value.violations.map((violation, index) =>
          hydrateViolation(violation, index, `${prefix}-${key}`)
        )
      };
      return acc;
    }, {});
  };

  const integerResourceMap: Record<number, PlanInsightStateItem> = {};
  Object.entries(insights.resource ?? {}).forEach(([key, value]) => {
    const parsed = Number.parseInt(key, 10);
    if (!Number.isNaN(parsed)) {
      integerResourceMap[parsed] = {
        severity: value.severity,
        violations: value.violations.map((violation, index) =>
          hydrateViolation(violation, index, `resource-${parsed}`)
        )
      };
    }
  });

  return {
    daily: build(insights.daily ?? {}, "daily"),
    resource: integerResourceMap,
    weekly: build(insights.weekly ?? {}, "weekly"),
    monthly: build(insights.monthly ?? {}, "monthly")
  };
}

function mapSummariesFromDto(summaries: PlanSummaryDto[] | undefined): SummaryItem[] {
  if (!summaries) {
    return [];
  }
  return summaries.map((summary) => ({
    resourceId: summary.resource_id,
    name: summary.resource_name,
    actualHours: summary.actual_hours,
    dueHours: summary.due_hours,
    dueRealHours: summary.due_real_hours,
    openingBalanceHours: summary.opening_balance_hours,
    closingBalanceHours: summary.closing_balance_hours,
    workingDays: summary.working_days,
    vacationDays: summary.vacation_days
  }));
}

function mapRuleStatuses(
  statuses: RuleStatusDto[] | undefined,
  prefix: string
): RuleStatusState[] {
  if (!statuses) {
    return [];
  }

  return statuses.map((status) => {
    const violations = status.violations?.map((violation, index) =>
      hydrateViolation(violation, index, `${prefix}-${status.code}`)
    );
    return {
      code: status.code,
      translationKey: status.translation_key,
      status: status.status,
      violations: violations ?? [],
      count: violations?.length ?? 0
    };
  });
}

function mapSuggestions(
  suggestions: PlanSuggestionDto[] | undefined,
  prefix: string
): PlanSuggestionState[] {
  if (!suggestions) {
    return [];
  }

  return suggestions.map((suggestion, index) => ({
    id: suggestion.id ?? `${prefix}-suggestion-${index}`,
    type: suggestion.type,
    title: suggestion.title,
    description: suggestion.description,
    severity: suggestion.severity,
    relatedViolation: suggestion.related_violation ?? undefined,
    change: suggestion.change
      ? {
          action: suggestion.change.action,
          resourceId: suggestion.change.resource_id,
          date: suggestion.change.date,
          shiftCode: suggestion.change.shift_code ?? undefined,
          absenceType: suggestion.change.absence_type ?? undefined
        }
      : undefined,
    metadata: suggestion.metadata ?? {}
  }));
}

function mapVersions(versions: PlanVersionDto[] | undefined): PlanVersionState[] {
  if (!versions) {
    return [];
  }
  return versions.map((version) => {
    let summary: PlanVersionState["summary"] = null;
    if (version.summary_hours) {
      try {
        summary = JSON.parse(version.summary_hours) as PlanVersionState["summary"];
      } catch {
        summary = null;
      }
    }
    return {
      id: version.id,
      label: version.version_label,
      createdAt: version.created_at,
      summary
    };
  });
}

const fetchPlanVersions = async (scenarioId: number): Promise<PlanVersionState[]> => {
  const response = await api.get<PlanVersionDto[]>(`/planning/versions/${scenarioId}`);
  return mapVersions(response.data);
};

const buildPlansFromOverview = async (
  overview: PlanOverviewDto,
  resources: Resource[]
): Promise<{ preparation: PlanPhaseState | null; approved: PlanPhaseState | null }> => {
  const preparationPrefix = overview.preparation?.scenario?.id
    ? `scenario-${overview.preparation.scenario.id}-prep`
    : "preparation";
  let preparationPlan = buildPlanPhaseState(overview.preparation, resources, preparationPrefix);
  if (preparationPlan?.scenario) {
    const versions = await fetchPlanVersions(preparationPlan.scenario.id);
    preparationPlan = { ...preparationPlan, versions };
  }

  const approvedPrefix = overview.approved?.scenario?.id
    ? `scenario-${overview.approved.scenario.id}-approved`
    : "approved";
  let approvedPlan = buildPlanPhaseState(overview.approved, resources, approvedPrefix);
  if (approvedPlan?.scenario) {
    const versions = await fetchPlanVersions(approvedPlan.scenario.id);
    approvedPlan = { ...approvedPlan, versions };
  }

  return { preparation: preparationPlan, approved: approvedPlan };
};

const buildPlanPhaseState = (
  phase: PlanPhaseDto | null | undefined,
  resources: Resource[],
  prefix: string
): PlanPhaseState | null => {
  if (!phase) {
    return null;
  }
  const entries = phase.entries.map(mapPlanningEntry);
  const insights = mapInsights(phase.insights);
  return {
    scenario: phase.scenario
      ? {
          id: phase.scenario.id,
          name: phase.scenario.name,
          status: phase.scenario.status,
          updatedAt: phase.scenario.updated_at
        }
      : null,
    entries,
    violations: mapViolations(phase.violations ?? [], `${prefix}-violations`),
    summaries:
      phase.summaries && phase.summaries.length
        ? mapSummariesFromDto(phase.summaries)
        : computeSummaries(entries, resources),
    insights,
    ruleStatuses: mapRuleStatuses(phase.rule_statuses, prefix),
    versions: [],
    suggestions: mapSuggestions(phase.suggestions, `${prefix}-suggestion`)
  };
};

const useScheduleStore = create<ScheduleState>((set, get) => ({
  month: null,
  isLoading: false,
  resources: [],
  plans: {
    preparation: null,
    approved: null
  },
  activePhase: "preparation",
  holidays: [],
  setActivePhase: (phase) =>
    set((state) => {
      if (phase === "approved" && !state.plans.approved) {
        return {};
      }
      return { activePhase: phase };
    }),
  loadInitialData: async () => {
    set({ isLoading: true });

    const fallbackMonth = new Date().toISOString().slice(0, 7);

    try {
      const [resourcesResponse, overviewResponse] = await Promise.all([
        api.get<ResourceDto[]>("/resources"),
        api.get<PlanOverviewDto>("/planning/overview", { params: { month: fallbackMonth } })
      ]);

      const resources: Resource[] = resourcesResponse.data.map((item) => ({
        id: item.id,
        name: item.name,
        role: item.role,
        availabilityPercent: item.availability_percent,
        contractHoursPerMonth: item.contract_hours_per_month,
        preferredDaysOff: item.preferred_days_off,
        vacationDays: item.vacation_days,
        language: item.language,
        notes: item.notes,
        availabilityTemplate: normalizeWeeklyAvailability(item.availability_template),
        preferredShiftCodes: item.preferred_shift_codes ?? undefined,
        undesiredShiftCodes: item.undesired_shift_codes ?? undefined,
        absences: normalizeAbsences(item.absences)
      }));

      let overview = overviewResponse.data;
      const preparationPrefix = overview.preparation?.scenario?.id
        ? `scenario-${overview.preparation.scenario.id}-prep`
        : "preparation";
      let preparationPlan = buildPlanPhaseState(overview.preparation, resources, preparationPrefix);

      if (!preparationPlan || preparationPlan.entries.length === 0) {
        await api.post("/planning/generate", { month: fallbackMonth });
        const refreshed = await api.get<PlanOverviewDto>("/planning/overview", {
          params: { month: fallbackMonth }
        });
        overview = refreshed.data;
        preparationPlan = buildPlanPhaseState(
          overview.preparation,
          resources,
          overview.preparation?.scenario?.id
            ? `scenario-${overview.preparation.scenario.id}-prep`
            : "preparation"
        );
      }

      if (preparationPlan?.scenario) {
        const versions = await fetchPlanVersions(preparationPlan.scenario.id);
        preparationPlan = { ...preparationPlan, versions };
      }

      let approvedPlan = buildPlanPhaseState(
        overview.approved,
        resources,
        overview.approved?.scenario?.id ? `scenario-${overview.approved.scenario.id}-approved` : "approved"
      );
      if (approvedPlan?.scenario) {
        const versions = await fetchPlanVersions(approvedPlan.scenario.id);
        approvedPlan = { ...approvedPlan, versions };
      }

      const resolvedMonth = overview.month ?? fallbackMonth;
      set({
        month: resolvedMonth,
        resources,
        plans: {
          preparation: preparationPlan,
          approved: approvedPlan
        },
        activePhase: preparationPlan ? "preparation" : approvedPlan ? "approved" : "preparation",
        holidays: overview.holidays ?? [],
        isLoading: false
      });
    } catch (error) {
      console.warn("API unavailable, loading fallback data.", error);
      set({
        month: fallbackMonth,
        resources: fallbackResources,
        plans: {
          preparation: {
            scenario: null,
            entries: fallbackEntries,
            violations: [],
            summaries: computeSummaries(fallbackEntries, fallbackResources),
            insights: { daily: {}, resource: {}, weekly: {}, monthly: {} },
            ruleStatuses: [],
            versions: [],
            suggestions: []
          },
          approved: null
        },
        activePhase: "preparation",
        holidays: [],
        isLoading: false
      });
    }
  },
  refreshPreparationPlan: async (label?: string) => {
    const month = get().month ?? new Date().toISOString().slice(0, 7);
    set({ isLoading: true });
    try {
      await api.post("/planning/generate", { month, label });
      await get().refreshOverviewOnly();
    } catch (error) {
      console.warn("Failed to refresh preparation plan.", error);
      set({ isLoading: false });
    }
  },
  generateOptimisedPlan: async (label?: string) => {
    const month = get().month ?? new Date().toISOString().slice(0, 7);
    set({ isLoading: true });
    try {
      await api.post("/planning/generate/optimized", { month, label });
      await get().refreshOverviewOnly();
    } catch (error) {
      console.warn("Failed to generate optimized plan.", error);
      set({ isLoading: false });
    }
  },
  refreshOverviewOnly: async () => {
    const month = get().month ?? new Date().toISOString().slice(0, 7);
    set({ isLoading: true });

    try {
      const overviewResponse = await api.get<PlanOverviewDto>("/planning/overview", {
        params: { month }
      });
      const resources = get().resources.length ? get().resources : fallbackResources;
      let preparationPlan = buildPlanPhaseState(
        overviewResponse.data.preparation,
        resources,
        overviewResponse.data.preparation?.scenario?.id
          ? `scenario-${overviewResponse.data.preparation.scenario.id}-prep`
          : "preparation"
      );
      if (preparationPlan?.scenario) {
        const versions = await fetchPlanVersions(preparationPlan.scenario.id);
        preparationPlan = { ...preparationPlan, versions };
      }

      let approvedPlan = buildPlanPhaseState(
        overviewResponse.data.approved,
        resources,
        overviewResponse.data.approved?.scenario?.id
          ? `scenario-${overviewResponse.data.approved.scenario.id}-approved`
          : "approved"
      );
      if (approvedPlan?.scenario) {
        const versions = await fetchPlanVersions(approvedPlan.scenario.id);
        approvedPlan = { ...approvedPlan, versions };
      }

      const resolvedMonth = overviewResponse.data.month ?? month;
      set((state) => ({
        plans: {
          preparation: preparationPlan,
          approved: approvedPlan
        },
        activePhase: preparationPlan ? state.activePhase : approvedPlan ? "approved" : "preparation",
        month: resolvedMonth,
        holidays: overviewResponse.data.holidays ?? state.holidays,
        isLoading: false
      }));
    } catch (error) {
      console.warn("Failed to refresh plan overview.", error);
      set({ isLoading: false });
    }
  }
}));

export default useScheduleStore;
