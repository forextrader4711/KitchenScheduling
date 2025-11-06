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
  availabilityTemplate?: WeeklyAvailabilityEntry[] | null;
  preferredShiftCodes?: number[] | null;
  undesiredShiftCodes?: number[] | null;
  absences?: ResourceAbsence[];
}

export interface WeeklyAvailabilityEntry {
  day: "monday" | "tuesday" | "wednesday" | "thursday" | "friday" | "saturday" | "sunday";
  isAvailable: boolean;
  startTime?: string | null;
  endTime?: string | null;
}

export interface ResourceAbsence {
  id: number;
  startDate: string;
  endDate: string;
  absenceType: "vacation" | "sick_leave" | "training" | "other";
  comment?: string | null;
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
  category: string;
  severity: "info" | "warning" | "critical";
  message?: string;
  meta?: Record<string, unknown>;
  day?: string | null;
  resourceId?: number | null;
  isoWeek?: string | null;
  rawMessage?: string;
}

export interface RuleStatus {
  code: string;
  translationKey: string;
  status: "ok" | "warning" | "critical";
  violations: ViolationItem[];
  count: number;
}

export interface PlanSuggestedChange {
  action: "assign_shift" | "set_rest_day" | "remove_assignment";
  resourceId: number;
  date: string;
  shiftCode?: number | null;
  absenceType?: string | null;
}

export interface PlanSuggestion {
  id: string;
  type: string;
  title: string;
  description: string;
  severity: "info" | "warning" | "critical";
  relatedViolation?: string | null;
  change?: PlanSuggestedChange | null;
  metadata?: Record<string, unknown>;
}

export interface Shift {
  code: number;
  description: string;
  start: string;
  end: string;
  hours: number;
}
