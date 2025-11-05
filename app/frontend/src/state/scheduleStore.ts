import { create } from "zustand";

import api from "../services/api";
import {
  PlanningEntry,
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
};

type PlanOverviewDto = {
  month: string;
  preparation?: PlanPhaseDto | null;
  approved?: PlanPhaseDto | null;
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

interface ScheduleState {
  month: string | null;
  isLoading: boolean;
  resources: Resource[];
  plans: Record<PlanPhaseKey, PlanPhaseState | null>;
  activePhase: PlanPhaseKey;
  setActivePhase: (phase: PlanPhaseKey) => void;
  loadInitialData: () => Promise<void>;
  refreshPreparationPlan: () => Promise<void>;
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
  return resources.map((resource) => {
    const worked = entries.filter((entry) => entry.resourceId === resource.id).length * 8;
    return {
      resourceId: resource.id,
      name: resource.name,
      workedHours: worked,
      contractHours: resource.contractHoursPerMonth
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
    summaries: computeSummaries(entries, resources),
    insights
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

      const approvedPlan = buildPlanPhaseState(
        overview.approved,
        resources,
        overview.approved?.scenario?.id ? `scenario-${overview.approved.scenario.id}-approved` : "approved"
      );

      set({
        month: fallbackMonth,
        resources,
        plans: {
          preparation: preparationPlan,
          approved: approvedPlan
        },
        activePhase: preparationPlan ? "preparation" : approvedPlan ? "approved" : "preparation",
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
            insights: { daily: {}, resource: {}, weekly: {}, monthly: {} }
          },
          approved: null
        },
        activePhase: "preparation",
        isLoading: false
      });
    }
  },
  refreshPreparationPlan: async () => {
    const month = get().month ?? new Date().toISOString().slice(0, 7);
    set({ isLoading: true });

    try {
      await api.post("/planning/generate", { month });
      const overviewResponse = await api.get<PlanOverviewDto>("/planning/overview", {
        params: { month }
      });
      const resources = get().resources.length ? get().resources : fallbackResources;
      const preparationPlan = buildPlanPhaseState(
        overviewResponse.data.preparation,
        resources,
        overviewResponse.data.preparation?.scenario?.id
          ? `scenario-${overviewResponse.data.preparation.scenario.id}-prep`
          : "preparation"
      );
      const approvedPlan = buildPlanPhaseState(
        overviewResponse.data.approved,
        resources,
        overviewResponse.data.approved?.scenario?.id
          ? `scenario-${overviewResponse.data.approved.scenario.id}-approved`
          : "approved"
      );

      set((state) => ({
        plans: {
          preparation: preparationPlan,
          approved: approvedPlan
        },
        activePhase: preparationPlan ? state.activePhase : approvedPlan ? "approved" : "preparation",
        isLoading: false
      }));
    } catch (error) {
      console.warn("Failed to refresh preparation plan.", error);
      set({ isLoading: false });
    }
  }
}));

export default useScheduleStore;
