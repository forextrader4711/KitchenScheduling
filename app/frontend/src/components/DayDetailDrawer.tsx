import CloseIcon from "@mui/icons-material/Close";
import {
  Box,
  Chip,
  Divider,
  Drawer,
  IconButton,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";
import { Resource, ViolationItem } from "../types";
import formatViolationMessage from "../utils/formatViolation";

type ResourceDayInfo = {
  resource: Resource;
  shiftCode?: number | null;
  absenceLabel?: string;
  availabilityWindow?: string;
  availabilityReason?: "available" | "template" | "absence";
  insightSeverity?: "info" | "warning" | "critical";
  insightViolations: ViolationItem[];
};

const severityChipColor: Record<"info" | "warning" | "critical", "default" | "warning" | "error"> = {
  info: "default",
  warning: "warning",
  critical: "error"
};

interface DayDetailDrawerProps {
  open: boolean;
  day: string | null;
  onClose: () => void;
}

const DayDetailDrawer = ({ open, day, onClose }: DayDetailDrawerProps) => {
  const { t, i18n } = useTranslation();
  const { plans, activePhase, resources } = useScheduleStore();
  const plan = plans[activePhase];

  const {
    assigned,
    available,
    unavailable,
    formattedDate,
    dayViolations,
    resourceNames
  } = useMemo(() => {
    if (!open || !day || !plan) {
      return {
        assigned: [] as ResourceDayInfo[],
        available: [] as ResourceDayInfo[],
        unavailable: [] as ResourceDayInfo[],
        formattedDate: "",
        dayViolations: [] as ViolationItem[],
        resourceNames: {} as Record<number, string>
      };
    }

    const dateObj = new Date(`${day}T00:00:00`);
    if (Number.isNaN(dateObj.getTime())) {
      return {
        assigned: [] as ResourceDayInfo[],
        available: [] as ResourceDayInfo[],
        unavailable: [] as ResourceDayInfo[],
        formattedDate: "",
        dayViolations: [] as ViolationItem[],
        resourceNames: {} as Record<number, string>
      };
    }

    const weekday = dateObj
      .toLocaleDateString("en-US", { weekday: "long" })
      .toLowerCase();

    const resourceMap = new Map<number, Resource>();
    resources.forEach((resource) => resourceMap.set(resource.id, resource));

    const resourceNames = resources.reduce<Record<number, string>>((acc, resource) => {
      acc[resource.id] = resource.name;
      return acc;
    }, {});

    const dayViolations = plan.insights.daily[day]?.violations ?? [];

    const assignedEntries = plan.entries.filter((entry) => entry.date.startsWith(day));
    const assignedResourceIds = new Set<number>();

    const buildInfo = (resource: Resource, overrides: Partial<ResourceDayInfo> = {}): ResourceDayInfo => {
      const templateEntry = resource.availabilityTemplate?.find((item) => item.day === weekday);
      const isTemplateAvailable = templateEntry ? templateEntry.isAvailable : true;
      const windowLabel =
        templateEntry && templateEntry.startTime && templateEntry.endTime
          ? t("planning.dayOverviewWindow", {
              start: templateEntry.startTime,
              end: templateEntry.endTime
            })
          : t("planning.dayOverviewFlexible");

      const absence = (resource.absences ?? []).find((absence) => {
        const start = new Date(`${absence.startDate}T00:00:00`);
        const end = new Date(`${absence.endDate}T00:00:00`);
        return dateObj >= start && dateObj <= end;
      });

      const absenceLabel = absence
        ? t(`masterData.absenceTypes.${absence.absenceType}`, { defaultValue: absence.absenceType })
        : undefined;

      let availabilityReason: ResourceDayInfo["availabilityReason"] = "available";
      if (absenceLabel) {
        availabilityReason = "absence";
      } else if (!isTemplateAvailable) {
        availabilityReason = "template";
      }

      const insight = plan.insights.resource[resource.id];

      return {
        resource,
        availabilityWindow: windowLabel,
        availabilityReason,
        absenceLabel,
        insightSeverity: insight?.severity,
        insightViolations: insight?.violations ?? [],
        ...overrides
      };
    };

    const assigned = assignedEntries
      .map((entry) => {
        const resource = resourceMap.get(entry.resourceId);
        if (!resource) {
          return undefined;
        }
        assignedResourceIds.add(resource.id);
        return buildInfo(resource, { shiftCode: entry.shiftCode });
      })
      .filter((item): item is ResourceDayInfo => Boolean(item))
      .sort((a, b) => a.resource.name.localeCompare(b.resource.name, undefined, { sensitivity: "base" }));

    const available: ResourceDayInfo[] = [];
    const unavailable: ResourceDayInfo[] = [];

    resources.forEach((resource) => {
      if (assignedResourceIds.has(resource.id)) {
        return;
      }
      const info = buildInfo(resource);
      if (info.availabilityReason === "available") {
        available.push(info);
      } else {
        unavailable.push(info);
      }
    });

    const sortByName = (list: ResourceDayInfo[]) =>
      list.sort((a, b) => a.resource.name.localeCompare(b.resource.name, undefined, { sensitivity: "base" }));

    return {
      assigned,
      available: sortByName(available),
      unavailable: sortByName(unavailable),
      formattedDate: dateObj.toLocaleDateString(i18n.language === "fr" ? "fr-FR" : "en-US", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
      }),
      dayViolations,
      resourceNames
    };
  }, [open, day, plan, resources, i18n.language, t]);

  if (!open || !day || !plan) {
    return null;
  }

  const renderResourceCard = (info: ResourceDayInfo, variant: "assigned" | "available" | "unavailable") => {
    const { resource } = info;
    const roleLabel = t(`masterData.roles.${resource.role}`, {
      defaultValue: resource.role.replace("_", " ")
    });
    const preferred =
      resource.preferredShiftCodes && resource.preferredShiftCodes.length > 0
        ? resource.preferredShiftCodes.join(", ")
        : null;
    const undesired =
      resource.undesiredShiftCodes && resource.undesiredShiftCodes.length > 0
        ? resource.undesiredShiftCodes.join(", ")
        : null;

    return (
      <Paper
        key={resource.id}
        variant="outlined"
        sx={{
          p: 1.5,
          borderRadius: 3,
          borderColor:
            info.insightSeverity === "critical"
              ? "error.light"
              : info.insightSeverity === "warning"
              ? "warning.light"
              : "rgba(51,88,255,0.16)"
        }}
      >
        <Stack spacing={1}>
          <Stack direction="row" justifyContent="space-between" alignItems="center">
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {resource.name}
            </Typography>
            <Chip label={roleLabel} size="small" color="primary" variant="outlined" />
          </Stack>

          {variant === "assigned" ? (
            <Typography variant="body2">
              {info.shiftCode !== undefined && info.shiftCode !== null
                ? t("planning.dayOverviewShiftLabel", { code: info.shiftCode })
                : t("planning.dayOverviewNoShift")}
            </Typography>
          ) : null}

          {variant !== "assigned" ? (
            <Typography variant="body2" color="text.secondary">
              {info.availabilityReason === "available"
                ? info.availabilityWindow
                : info.availabilityReason === "absence" && info.absenceLabel
                ? t("planning.dayOverviewAbsenceLabel", { type: info.absenceLabel })
                : t("planning.dayOverviewNotWorking")}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {info.availabilityWindow}
            </Typography>
          )}

          {preferred ? (
            <Typography variant="caption">
              {t("planning.dayOverviewPrefers", { list: preferred })}
            </Typography>
          ) : null}
          {undesired ? (
            <Typography variant="caption">
              {t("planning.dayOverviewAvoids", { list: undesired })}
            </Typography>
          ) : null}

          {info.insightSeverity && info.insightViolations.length ? (
            <Stack spacing={0.5}>
              <Stack direction="row" spacing={1} alignItems="center">
                <Chip
                  size="small"
                  color={severityChipColor[info.insightSeverity]}
                  label={t(`planning.severity.${info.insightSeverity}`)}
                />
                <Typography variant="caption">{t("planning.dayOverviewWarnings")}</Typography>
              </Stack>
              {info.insightViolations.map((violation, index) => (
                <Typography key={index} variant="caption" color="text.secondary">
                  {formatViolationMessage(t, violation, { resourceNames, language: i18n.language })}
                </Typography>
              ))}
            </Stack>
          ) : (
            <Typography variant="caption" color="text.secondary">
              {t("planning.dayOverviewNoWarnings")}
            </Typography>
          )}
        </Stack>
      </Paper>
    );
  };

  return (
    <Drawer anchor="right" open={open} onClose={onClose}>
      <Box sx={{ width: { xs: 360, sm: 400 }, p: 3, display: "flex", flexDirection: "column", gap: 2 }}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h6">{t("planning.dayOverviewTitle")}</Typography>
          <IconButton edge="end" onClick={onClose} aria-label={t("planning.dayOverviewClose")}>
            <CloseIcon />
          </IconButton>
        </Stack>

        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {formattedDate}
        </Typography>

        <Stack spacing={0.75}>
          <Divider textAlign="left">{t("planning.dayOverviewViolations")}</Divider>
          {dayViolations.length > 0 ? (
            dayViolations.map((violation, index) => (
              <Typography key={index} variant="body2" color="text.secondary">
                {formatViolationMessage(t, violation, { resourceNames, language: i18n.language })}
              </Typography>
            ))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.dayOverviewNoWarnings")}
            </Typography>
          )}
        </Stack>

        <Stack spacing={1.25}>
          <Divider textAlign="left">{t("planning.dayOverviewAssigned")}</Divider>
          {assigned.length ? (
            assigned.map((info) => renderResourceCard(info, "assigned"))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.dayOverviewNoAssigned")}
            </Typography>
          )}
        </Stack>

        <Stack spacing={1.25}>
          <Divider textAlign="left">{t("planning.dayOverviewAvailable")}</Divider>
          {available.length ? (
            available.map((info) => renderResourceCard(info, "available"))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.dayOverviewNoAvailable")}
            </Typography>
          )}
        </Stack>

        <Stack spacing={1.25}>
          <Divider textAlign="left">{t("planning.dayOverviewUnavailable")}</Divider>
          {unavailable.length ? (
            unavailable.map((info) => renderResourceCard(info, "unavailable"))
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.dayOverviewNoUnavailable")}
            </Typography>
          )}
        </Stack>

      </Box>
    </Drawer>
  );
};

export default DayDetailDrawer;
