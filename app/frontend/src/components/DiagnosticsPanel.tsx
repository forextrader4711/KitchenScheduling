import { useMemo } from "react";
import {
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Divider,
  List,
  ListItem,
  ListItemText,
  Stack,
  Typography
} from "@mui/material";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

type RelaxationInput = {
  minimum_daily_staff_delta?: number;
  role_minimum_deltas?: Record<string, number>;
};

const DiagnosticsPanel = () => {
  const { t } = useTranslation();
  const { generationDiagnostics, generateOptimisedPlan, generateHeuristicPlan, isLoading } =
    useScheduleStore();

  if (!generationDiagnostics) {
    return null;
  }

  const suggestedRelaxations = useMemo<RelaxationInput | null>(() => {
    if (!generationDiagnostics) {
      return null;
    }
    const relaxations: RelaxationInput = {};
    if (generationDiagnostics.staffing?.length) {
      relaxations.minimum_daily_staff_delta = -1;
    }
    if (generationDiagnostics.roles?.length) {
      const roleDeltas: Record<string, number> = {};
      generationDiagnostics.roles.forEach((item) => {
        roleDeltas[item.role] = Math.min(roleDeltas[item.role] ?? 0, -1);
      });
      if (Object.keys(roleDeltas).length > 0) {
        relaxations.role_minimum_deltas = roleDeltas;
      }
    }
    return Object.keys(relaxations).length ? relaxations : null;
  }, [generationDiagnostics]);

  const handleRetry = () => {
    void generateOptimisedPlan(undefined, suggestedRelaxations ?? undefined);
  };

  const handleHeuristic = () => {
    void generateHeuristicPlan();
  };

  const sectionTitle = (label: string, count: number) => (
    <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
      <Chip size="small" color="warning" icon={<WarningAmberIcon fontSize="small" />} label={count} />
      <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
        {label}
      </Typography>
    </Stack>
  );

  const relaxationSummary = () => {
    if (!suggestedRelaxations) {
      return (
        <Typography variant="body2" color="text.secondary">
          {t("planning.diagnostics.noRelaxations", {
            defaultValue: "Retry will use the current constraints. Adjust availability or relaxations if needed."
          })}
        </Typography>
      );
    }
    const items: string[] = [];
    if (suggestedRelaxations.minimum_daily_staff_delta) {
      items.push(
        t("planning.diagnostics.relaxationStaffing", {
          defaultValue: "Daily staffing minimum minus {{delta}}",
          delta: Math.abs(suggestedRelaxations.minimum_daily_staff_delta)
        })
      );
    }
    if (suggestedRelaxations.role_minimum_deltas) {
      Object.entries(suggestedRelaxations.role_minimum_deltas).forEach(([role, delta]) => {
        items.push(
          t("planning.diagnostics.relaxationRole", {
            defaultValue: "{{role}} minimum minus {{delta}}",
            role,
            delta: Math.abs(delta)
          })
        );
      });
    }
    return (
      <Typography variant="body2" color="text.secondary">
        {items.join(" · ")}
      </Typography>
    );
  };

  return (
    <Card sx={{ height: "100%" }}>
      <CardHeader
        title={t("planning.diagnostics.title", { defaultValue: "Optimizer diagnostics" })}
        subheader={
          generationDiagnostics.summary ||
          t("planning.diagnostics.summaryFallback", {
            defaultValue: "Latest solver issues requiring attention."
          })
        }
      />
      <CardContent>
        <Stack spacing={2}>
          {generationDiagnostics.staffing?.length ? (
            <Box>
              {sectionTitle(
                t("planning.diagnostics.staffing", { defaultValue: "Daily staffing shortfalls" }),
                generationDiagnostics.staffing.length
              )}
              <List dense disablePadding>
                {generationDiagnostics.staffing.map((item) => (
                  <ListItem key={`${item.date}-staff`} disableGutters>
                    <ListItemText
                      primary={t("planning.diagnostics.staffingEntry", {
                        defaultValue: "{{date}}: {{available}} / {{required}} resources",
                        date: item.date,
                        available: item.available,
                        required: item.required
                      })}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          ) : null}

          {generationDiagnostics.roles?.length ? (
            <Box>
              <Divider sx={{ my: 1.5 }} />
              {sectionTitle(
                t("planning.diagnostics.roles", { defaultValue: "Role composition gaps" }),
                generationDiagnostics.roles.length
              )}
              <List dense disablePadding>
                {generationDiagnostics.roles.map((item) => (
                  <ListItem key={`${item.date}-${item.role}`} disableGutters>
                    <ListItemText
                      primary={t("planning.diagnostics.roleEntry", {
                        defaultValue: "{{date}}: {{role}} available {{available}} / {{required}} required",
                        date: item.date,
                        role: item.role,
                        available: item.available,
                        required: item.required
                      })}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          ) : null}

          {generationDiagnostics.capacity?.length ? (
            <Box>
              <Divider sx={{ my: 1.5 }} />
              {sectionTitle(
                t("planning.diagnostics.capacity", { defaultValue: "Resource capacity conflicts" }),
                generationDiagnostics.capacity.length
              )}
              <List dense disablePadding>
                {generationDiagnostics.capacity.map((item) => (
                  <ListItem key={`capacity-${item.resource_id}`} disableGutters>
                    <ListItemText
                      primary={t("planning.diagnostics.capacityEntry", {
                        defaultValue:
                          "{{resource}} available {{available}}h / {{required}}h required by contract",
                        resource: item.resource_name ?? `#${item.resource_id}`,
                        available: item.available_hours.toFixed(1),
                        required: item.required_hours.toFixed(1)
                      })}
                    />
                  </ListItem>
                ))}
              </List>
            </Box>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.diagnostics.noDetails", {
                defaultValue: "No specific constraint breakdown available."
              })}
            </Typography>
          )}
          <Divider sx={{ my: 1.5 }} />
          <Stack direction={{ xs: "column", md: "row" }} spacing={1}>
            <Button
              variant="contained"
              disabled={isLoading}
              onClick={handleRetry}
            >
              {t("planning.diagnostics.retryButton", {
                defaultValue: "Retry optimizer with relaxations"
              })}
            </Button>
            <Button
              variant="outlined"
              disabled={isLoading}
              onClick={handleHeuristic}
            >
              {t("planning.diagnostics.heuristicButton", {
                defaultValue: "Use heuristic fallback"
              })}
            </Button>
          </Stack>
          {relaxationSummary()}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default DiagnosticsPanel;
