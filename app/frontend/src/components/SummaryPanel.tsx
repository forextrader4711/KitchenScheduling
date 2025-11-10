import {
  Box,
  Avatar,
  Card,
  CardContent,
  Chip,
  LinearProgress,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const SummaryPanel = () => {
  const { t } = useTranslation();
  const { plans, activePhase, resources } = useScheduleStore();
  const summaries = plans[activePhase]?.summaries ?? [];

  const resourceById = resources.reduce<Record<number, typeof resources[number]>>((acc, resource) => {
    acc[resource.id] = resource;
    return acc;
  }, {});

  const getInitials = (name: string) => {
    const [first, second] = name.split(" ");
    if (!second) {
      return first.charAt(0).toUpperCase();
    }
    return `${first.charAt(0)}${second.charAt(0)}`.toUpperCase();
  };

  const formatHours = (value: number): string => {
    const sign = value < 0 ? "-" : "";
    const totalMinutes = Math.round(Math.abs(value) * 60);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return `${sign}${hours}:${minutes.toString().padStart(2, "0")}`;
  };

  return (
    <Card sx={{ height: "100%" }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t("summary.title")}
        </Typography>
        {summaries.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("summary.empty", { defaultValue: "No hour summary available yet." })}
          </Typography>
        ) : (
          <Stack spacing={2}>
            {summaries.map((summary) => {
              const resource = resourceById[summary.resourceId];
              const actual = summary.actualHours;
              const due = summary.dueHours;
              const dueReal = summary.dueRealHours;
              const opening = summary.openingBalanceHours;
              const closing = summary.closingBalanceHours;
              const closingDelta = Math.round(closing * 100) / 100;
              const adherence =
                due > 0 ? Math.min(140, Math.round((actual / due) * 100)) : 0;
              const absClosing = Math.abs(closingDelta);
              const chipLabel =
                closingDelta === 0
                  ? t("summary.onTrack")
                  : closingDelta > 0
                  ? t("summary.overTarget", { hours: formatHours(absClosing) })
                  : t("summary.underTarget", { hours: formatHours(absClosing) });
              const chipColor = closingDelta === 0 ? "success" : closingDelta > 0 ? "warning" : "info";

              return (
                <Paper
                  key={summary.resourceId}
                  variant="outlined"
                sx={{
                  p: 2,
                  borderRadius: 3,
                  border: "1px solid rgba(51, 88, 255, 0.12)",
                  display: "flex",
                  alignItems: "center",
                  gap: 2
                }}
                >
                  <Avatar
                    sx={{
                      bgcolor: "primary.main",
                      color: "primary.contrastText",
                    width: 48,
                    height: 48,
                    fontWeight: 600
                  }}
                >
                  {getInitials(summary.name)}
                  </Avatar>
                  <Box sx={{ flexGrow: 1 }}>
                    <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                      {summary.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t("summary.hours", {
                        actual: formatHours(actual),
                        due: formatHours(due),
                        dueReal: formatHours(dueReal)
                      })}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {t("summary.balance", {
                        opening: formatHours(opening),
                        closing: formatHours(closing)
                      })}
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={Math.min(100, adherence)}
                      sx={{ mt: 1.5, borderRadius: 999, height: 6 }}
                      color={closingDelta > 0 ? "warning" : closingDelta < 0 ? "info" : "primary"}
                    />
                  </Box>
                  <Stack spacing={1} alignItems="flex-end">
                    {resource?.role ? (
                      <Chip
                      label={t(`masterData.roles.${resource.role}`, {
                        defaultValue: resource.role.replace("_", " ")
                      })}
                      size="small"
                      color="primary"
                      variant="outlined"
                    />
                  ) : null}
                      <Chip label={chipLabel} size="small" color={chipColor} />
                </Stack>
              </Paper>
              );
            })}
          </Stack>
        )}
      </CardContent>
    </Card>
  );
};

export default SummaryPanel;
