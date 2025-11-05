import { TFunction } from "i18next";

import { ViolationItem } from "../types";

const getLocale = (language?: string) => (language === "fr" ? "fr-FR" : "en-US");

const formatDate = (value: unknown, language?: string) => {
  if (!value || typeof value !== "string") {
    return value ?? "";
  }
  const parsed = new Date(`${value}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString(getLocale(language), { day: "numeric", month: "long", year: "numeric" });
};

const formatNumber = (value: unknown, language?: string) => {
  const numeric = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numeric)) {
    return value ?? "";
  }
  return new Intl.NumberFormat(getLocale(language), { maximumFractionDigits: 2 }).format(numeric);
};

interface FormatOptions {
  resourceNames?: Record<number, string>;
  language?: string;
  roleResolver?: (role: string) => string;
}

const getResourceName = (id: number | null | undefined, t: TFunction, options?: FormatOptions) => {
  if (!id) {
    return t("planning.unknownResource");
  }
  return options?.resourceNames?.[id] ?? t("planning.unknownResource");
};

const getRoleName = (role: unknown, t: TFunction) => {
  if (typeof role !== "string") {
    return String(role ?? "");
  }
  return t(`masterData.roles.${role}`, { defaultValue: role.replace(/_/g, " ") });
};

const formatViolationMessage = (
  t: TFunction,
  violation: ViolationItem,
  options?: FormatOptions
): string => {
  const meta = violation.meta ?? {};
  const language = options?.language;

  switch (violation.category) {
    case "staffing-shortfall":
      return t("planning.violationMessages.staffing-shortfall", {
        assigned: formatNumber(meta.assigned, language),
        required: formatNumber(meta.required, language),
        date: formatDate(meta.date, language)
      });
    case "role-min-shortfall":
      return t("planning.violationMessages.role-min-shortfall", {
        role: getRoleName(meta.role, t),
        date: formatDate(meta.date, language),
        assigned: formatNumber(meta.assigned, language),
        min: formatNumber(meta.min, language)
      });
    case "role-max-exceeded":
      return t("planning.violationMessages.role-max-exceeded", {
        role: getRoleName(meta.role, t),
        date: formatDate(meta.date, language),
        assigned: formatNumber(meta.assigned, language),
        max: formatNumber(meta.max, language)
      });
    case "uncovered-day":
      return t("planning.violationMessages.uncovered-day", {
        date: formatDate(meta.date ?? violation.day, language)
      });
    case "hours-per-week-exceeded":
      return t("planning.violationMessages.hours-per-week-exceeded", {
        resourceName: getResourceName(violation.resourceId, t, options),
        week: meta.week ?? violation.isoWeek ?? "",
        hours: formatNumber(meta.hours, language),
        limit: formatNumber(meta.limit, language)
      });
    case "days-per-week-exceeded":
      return t("planning.violationMessages.days-per-week-exceeded", {
        resourceName: getResourceName(violation.resourceId, t, options),
        week: meta.week ?? violation.isoWeek ?? "",
        days: formatNumber(meta.days, language),
        limit: formatNumber(meta.limit, language)
      });
    case "consecutive-days-exceeded":
      return t("planning.violationMessages.consecutive-days-exceeded", {
        resourceName: getResourceName(violation.resourceId, t, options),
        streak: formatNumber(meta.streak, language)
      });
    case "insufficient-consecutive-rest":
      return t("planning.violationMessages.insufficient-consecutive-rest", {
        resourceName: getResourceName(violation.resourceId, t, options),
        required_off: formatNumber(meta.required_off, language)
      });
    case "empty-schedule":
      return t("planning.violationMessages.empty-schedule");
    default:
      return violation.rawMessage ?? violation.message ?? "";
  }
};

export default formatViolationMessage;
