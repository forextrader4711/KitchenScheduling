import { create } from "zustand";

import api from "../services/api";
import { PlanningEntry, Resource, SummaryItem, ViolationItem } from "../types";

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
};

type PlanScenarioDto = {
  id: number;
  month: string;
  name: string;
  status: string;
  violations?: PlanViolationDto[];
};

interface ScheduleState {
  month: string | null;
  isLoading: boolean;
  resources: Resource[];
  planningEntries: PlanningEntry[];
  summaries: SummaryItem[];
  violations: ViolationItem[];
  loadInitialData: () => Promise<void>;
}

const fallbackResources: Resource[] = [
  {
    id: 1,
    name: "Alice Dupont",
    role: "cook",
    availabilityPercent: 100,
    contractHoursPerMonth: 160,
    language: "fr"
  },
  {
    id: 2,
    name: "Marc Leroy",
    role: "kitchen_assistant",
    availabilityPercent: 80,
    contractHoursPerMonth: 128,
    language: "fr"
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

const useScheduleStore = create<ScheduleState>((set) => ({
  month: null,
  isLoading: false,
  resources: [],
  planningEntries: [],
  summaries: [],
  violations: [],
  loadInitialData: async () => {
    set({ isLoading: true });

    const fallbackMonth = new Date().toISOString().slice(0, 7);

    try {
      const [resourcesResponse, planResponse, scenariosResponse] = await Promise.all([
        api.get<ResourceDto[]>("/resources"),
        api.post<{ entries: PlanningEntryDto[]; violations: PlanViolationDto[] }>(
          "/planning/generate",
          { month: fallbackMonth }
        ),
        api.get<PlanScenarioDto[]>("/planning/scenarios")
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
        notes: item.notes
      }));

      const entries: PlanningEntry[] = planResponse.data.entries.map((entry) => ({
        id: entry.id,
        resourceId: entry.resource_id,
        date: entry.date,
        shiftCode: entry.shift_code,
        absenceType: entry.absence_type,
        comment: entry.comment
      }));

      const scenarioViolations =
        scenariosResponse.data.find((scenario) => scenario.month === fallbackMonth)?.violations ??
        planResponse.data.violations ??
        [];

      const violations: ViolationItem[] = scenarioViolations.map((violation, index) => ({
        id: `${violation.code}-${index}`,
        message: violation.message,
        category: violation.code,
        severity: violation.severity
      }));

      set({
        month: fallbackMonth,
        resources,
        planningEntries: entries,
        summaries: computeSummaries(entries, resources),
        violations,
        isLoading: false
      });
    } catch (error) {
      console.warn("API unavailable, loading fallback data.", error);
      set({
        month: fallbackMonth,
        resources: fallbackResources,
        planningEntries: fallbackEntries,
        summaries: computeSummaries(fallbackEntries, fallbackResources),
        violations: [],
        isLoading: false
      });
    }
  }
}));

export default useScheduleStore;
