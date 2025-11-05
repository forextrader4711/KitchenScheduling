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
    const delta = Math.round(summary.workedHours - summary.contractHours);
            const adherence =
              summary.contractHours > 0
                ? Math.min(140, Math.round((summary.workedHours / summary.contractHours) * 100))
                : 0;
            const chipLabel =
              delta === 0
                ? t("summary.onTrack", { defaultValue: "On track" })
                : delta > 0
                ? t("summary.overTarget", { defaultValue: "+{{hours}} h", hours: delta })
                : t("summary.underTarget", { defaultValue: "{{hours}} h remaining", hours: Math.abs(delta) });
            const chipColor = delta === 0 ? "success" : delta > 0 ? "warning" : "info";

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
                      worked: summary.workedHours,
                      contract: summary.contractHours
                    })}
                  </Typography>
                  <LinearProgress
                    variant="determinate"
                    value={Math.min(100, adherence)}
                    sx={{ mt: 1.5, borderRadius: 999, height: 6 }}
                    color={delta > 0 ? "warning" : "primary"}
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
