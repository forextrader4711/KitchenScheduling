import { useMemo, useState } from "react";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tooltip,
  Typography
} from "@mui/material";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";
import { ResourceAbsence } from "../types";
import DayDetailDrawer from "./DayDetailDrawer";
import formatViolationMessage from "../utils/formatViolation";

const severityVisuals: Record<"info" | "warning" | "critical", { dot: string; bg: string; text: string }> = {
  info: {
    dot: "#2563eb",
    bg: "rgba(37, 99, 235, 0.12)",
    text: "primary.main"
  },
  warning: {
    dot: "#f59e0b",
    bg: "rgba(245, 158, 11, 0.14)",
    text: "warning.main"
  },
  critical: {
    dot: "#dc2626",
    bg: "rgba(220, 38, 38, 0.14)",
    text: "error.main"
  }
};

type AvailabilityHint =
  | {
      status: "absence";
      absenceType: ResourceAbsence["absenceType"];
    }
  | {
      status: "unavailable";
    }
  | {
      status: "available";
      window?: {
        start?: string | null;
        end?: string | null;
      };
    };

const PlanningGrid = () => {
  const { t, i18n } = useTranslation();
  const { isLoading, month, plans, activePhase, resources } = useScheduleStore();
  const activePlan = plans[activePhase];
  const planningEntries = activePlan?.entries ?? [];
  const dailyInsights = activePlan?.insights.daily ?? {};
  const resourceInsights = activePlan?.insights.resource ?? {};
  const [selectedDay, setSelectedDay] = useState<string | null>(null);

  const monthMeta = useMemo(() => {
    if (!month) {
      return null;
    }
    const [yearRaw, monthRaw] = month.split("-");
    const year = Number(yearRaw);
    const monthNumber = Number(monthRaw);
    if (Number.isNaN(year) || Number.isNaN(monthNumber)) {
      return null;
    }
    return {
      year,
      monthNumber,
      monthIndex: monthNumber - 1,
      isoPrefix: `${yearRaw.padStart(4, "0")}-${monthRaw.padStart(2, "0")}`
    };
  }, [month]);

  const daysInMonth = useMemo(() => {
    if (!monthMeta) {
      return [];
    }
    const days = new Date(monthMeta.year, monthMeta.monthNumber, 0).getDate();
    return Array.from({ length: days }, (_, day) => day + 1);
  }, [monthMeta]);

  const resourceNames = useMemo(() => {
    return resources.reduce<Record<number, string>>((acc, resource) => {
      acc[resource.id] = resource.name;
      return acc;
    }, {});
  }, [resources]);

  const resourceRows = useMemo(
    () =>
      resources.map((resource) => ({
        id: resource.id,
        name: resource.name,
        role: resource.role
      })),
    [resources]
  );

  const cellLookup = useMemo(() => {
    return planningEntries.reduce<Record<string, string>>((acc, entry) => {
      const parts = entry.date.split("-");
      const dayPart = parts[2];
      const dayNumber = Number(dayPart);
      if (Number.isNaN(dayNumber)) {
        return acc;
      }
      const key = `${entry.resourceId}-${dayNumber}`;
      const shiftLabel =
        entry.shiftCode !== undefined && entry.shiftCode !== null
          ? String(entry.shiftCode)
          : entry.absenceType ?? "";
      acc[key] = shiftLabel;
      return acc;
    }, {});
  }, [planningEntries]);

  const availabilityHints = useMemo(() => {
    if (!monthMeta) {
      return {};
    }

    const weekdayLookup = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"];
    const hints: Record<string, AvailabilityHint> = {};

    resources.forEach((resource) => {
      const absences = resource.absences ?? [];
      const template = resource.availabilityTemplate ?? [];

      daysInMonth.forEach((day) => {
        const key = `${resource.id}-${day}`;
        const isoDate = `${monthMeta.isoPrefix}-${String(day).padStart(2, "0")}`;
        const absence = absences.find(
          (entry) => entry.startDate <= isoDate && isoDate <= entry.endDate
        );
        if (absence) {
          hints[key] = { status: "absence", absenceType: absence.absenceType };
          return;
        }

        const weekdayName = weekdayLookup[new Date(monthMeta.year, monthMeta.monthIndex, day).getDay()];
        const availabilityEntry = template.find((entry) => entry.day === weekdayName);

        if (availabilityEntry) {
          if (!availabilityEntry.isAvailable) {
            hints[key] = { status: "unavailable" };
            return;
          }

          hints[key] = {
            status: "available",
            window: {
              start: availabilityEntry.startTime ?? null,
              end: availabilityEntry.endTime ?? null
            }
          };
          return;
        }
      });
    });

    return hints;
  }, [resources, daysInMonth, monthMeta]);

  if (isLoading) {
    return (
      <Card sx={{ minHeight: 420 }}>
        <CardContent>
          <Skeleton variant="text" width="45%" sx={{ mb: 2 }} />
          <Skeleton variant="rounded" height={280} />
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <Card sx={{ minHeight: 420 }}>
        <CardHeader
          title={
            <Typography variant="h6" sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              {t("planning.gridTitle", { month })}
              <Chip
                label={`${resources.length} ${
                  resources.length === 1
                    ? t("planning.resource")
                    : t("planning.resourcePlural", { defaultValue: `${t("planning.resource")}s` })
                }`}
              />
            </Typography>
          }
          subheader={t("planning.gridHint", {
            defaultValue: "Use master data to adjust resources or shifts, then refresh the plan."
          })}
        />
        <CardContent sx={{ pt: 0 }}>
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, py: 0.75 }}>{t("planning.resource")}</TableCell>
                <TableCell sx={{ fontWeight: 600, py: 0.75 }}>{t("planning.role")}</TableCell>
                {daysInMonth.map((day) => {
                  const dayKey = monthMeta
                    ? `${monthMeta.isoPrefix}-${String(day).padStart(2, "0")}`
                    : String(day);
                  const dayInsight = dailyInsights[dayKey];
                  const dayVisual = dayInsight ? severityVisuals[dayInsight.severity] : null;
                  const headerContent = (
                    <Box sx={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0.5 }}>
                      <Typography
                        component="span"
                        sx={{ fontWeight: 600, color: dayVisual?.text ?? "inherit" }}
                      >
                        {day}
                      </Typography>
                      {dayVisual ? (
                        <Box
                          sx={{
                            width: 8,
                            height: 8,
                            borderRadius: "50%",
                            bgcolor: dayVisual.dot
                          }}
                        />
                      ) : null}
                    </Box>
                  );

                  const tooltipTitle = dayInsight ? (
                    <Box>
                      {dayInsight.violations.map((violation) => (
                        <Typography key={violation.id} variant="caption" display="block">
                          {formatViolationMessage(t, violation, {
                            resourceNames,
                            language: i18n.language
                          })}
                        </Typography>
                      ))}
                    </Box>
                  ) : undefined;

                  return (
                    <TableCell
                      key={day}
                      align="center"
                      sx={{
                        fontWeight: 600,
                        py: 0.75,
                        borderLeft: day === daysInMonth[0] ? undefined : "1px solid rgba(51, 88, 255, 0.08)",
                        cursor: monthMeta ? "pointer" : "default"
                      }}
                      onClick={() => {
                        if (monthMeta) {
                          setSelectedDay(dayKey);
                        }
                      }}
                    >
                      {dayInsight ? (
                        <Tooltip title={tooltipTitle} placement="top" arrow>
                          <Box>{headerContent}</Box>
                        </Tooltip>
                      ) : (
                        headerContent
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            </TableHead>
            <TableBody>
              {resourceRows.map((resource, rowIndex) => {
                const resourceInsight = resourceInsights[resource.id];
                const resourceVisual = resourceInsight ? severityVisuals[resourceInsight.severity] : null;
                const zebraBg = rowIndex % 2 === 0 ? "rgba(51, 88, 255, 0.02)" : "transparent";
                const rowBg = resourceVisual ? resourceVisual.bg : zebraBg;

                const resourceTooltip = resourceInsight ? (
                  <Box>
                    {resourceInsight.violations.map((violation) => (
                      <Typography key={violation.id} variant="caption" display="block">
                        {formatViolationMessage(t, violation, {
                          resourceNames,
                          language: i18n.language
                        })}
                      </Typography>
                    ))}
                  </Box>
                ) : undefined;

                return (
                  <TableRow
                    key={resource.id}
                    sx={{
                      bgcolor: rowBg,
                      transition: "background-color 150ms ease",
                      "&:hover": { bgcolor: resourceVisual ? resourceVisual.bg : "rgba(51, 88, 255, 0.06)" }
                    }}
                  >
                    <TableCell
                      component="th"
                      scope="row"
                      sx={{ fontWeight: 600, py: 0.75, whiteSpace: "nowrap", lineHeight: 1.2 }}
                    >
                      <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75 }}>
                        {resourceInsight ? (
                          <Tooltip title={resourceTooltip} placement="right" arrow>
                            <Box
                              sx={{
                                width: 8,
                                height: 8,
                                borderRadius: "50%",
                                bgcolor: resourceVisual?.dot ?? "transparent"
                              }}
                            />
                          </Tooltip>
                        ) : null}
                        <Typography
                          component="span"
                          variant="body2"
                          sx={{
                            fontWeight: 600,
                            color: resourceVisual?.text ?? "inherit",
                            lineHeight: 1.2,
                            whiteSpace: "nowrap"
                          }}
                        >
                          {resource.name}
                        </Typography>
                      </Box>
                    </TableCell>
                    <TableCell
                      sx={{
                        whiteSpace: "nowrap",
                        color: "text.secondary",
                        fontWeight: 500,
                        py: 0.75,
                        lineHeight: 1.2
                      }}
                    >
                      {t(`masterData.roleLabels.${resource.role}`, {
                        defaultValue: t(`masterData.roles.${resource.role}`, {
                          defaultValue: resource.role.replace(/_/g, " ")
                        })
                      })}
                    </TableCell>
                    {daysInMonth.map((day, index) => {
                      const key = `${resource.id}-${day}`;
                      const value = cellLookup[key] ?? "";
                      const hint = availabilityHints[key];
                      const status = hint?.status ?? "available";
                      const absenceLabel =
                        hint?.status === "absence"
                          ? t(`masterData.absenceTypes.${hint.absenceType}`)
                          : "";
                      const unavailableLabel = !value && status === "unavailable" ? t("planning.unavailableCell") : "";
                      const windowLabel =
                        !value &&
                        hint?.status === "available" &&
                        hint.window?.start &&
                        hint.window?.end
                          ? t("planning.availabilityWindow", {
                              start: hint.window.start,
                              end: hint.window.end
                            })
                          : "";

                      const displayLabel = value || absenceLabel || unavailableLabel;
                      const secondaryLabel = windowLabel;
                      const backgroundColor =
                        status === "absence"
                          ? "rgba(220, 38, 38, 0.12)"
                          : status === "unavailable"
                          ? "rgba(107, 114, 128, 0.12)"
                          : undefined;
                      const textColor =
                        status === "absence"
                          ? "error.main"
                          : status === "unavailable"
                          ? "text.secondary"
                          : undefined;

                      return (
                        <TableCell
                          key={key}
                          align="center"
                          sx={{
                            py: 0.75,
                            px: 0.75,
                            borderLeft: index === 0 ? undefined : "1px solid rgba(51, 88, 255, 0.08)",
                            bgcolor: backgroundColor
                          }}
                        >
                          <Typography
                            variant="body2"
                            sx={{ fontWeight: value ? 600 : 500, lineHeight: 1.2 }}
                            color={textColor}
                          >
                            {displayLabel}
                          </Typography>
                          {secondaryLabel ? (
                            <Typography variant="caption" color={textColor ?? "text.secondary"}>
                              {secondaryLabel}
                            </Typography>
                          ) : null}
                        </TableCell>
                      );
                    })}
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Box>
        </CardContent>
      </Card>
      <DayDetailDrawer open={Boolean(selectedDay)} day={selectedDay} onClose={() => setSelectedDay(null)} />
    </>
  );
};

export default PlanningGrid;
