export interface Resource {
  id: number;
  name: string;
  role: string;
  availabilityPercent: number;
  contractHoursPerMonth: number;
  preferredDaysOff?: string | null;
  vacationDays?: string | null;
  language: string;
  notes?: string | null;
}

export interface PlanningEntry {
  id: number;
  resourceId: number;
  date: string;
  shiftCode?: number | null;
  absenceType?: string | null;
  comment?: string | null;
}

export interface SummaryItem {
  resourceId: number;
  name: string;
  workedHours: number;
  contractHours: number;
}

export interface ViolationItem {
  id: string;
  message: string;
  category: string;
  severity: "info" | "warning" | "critical";
}
