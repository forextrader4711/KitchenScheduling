import { Card, CardContent, Divider, Stack, Typography } from "@mui/material";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const PlanningInsightsPanel = () => {
  const { t, i18n } = useTranslation();
  const { plans, activePhase, month } = useScheduleStore();
  const activePlan = plans[activePhase];
  const insights = activePlan?.insights;
  const ruleStatuses = activePlan?.ruleStatuses ?? [];

  const formattedMonth = useMemo(() => {
    if (!month) {
      return null;
    }
    const anchor = new Date(`${month}-01T00:00:00`);
    return anchor.toLocaleString(i18n.language === "fr" ? "fr-FR" : "en-US", {
      month: "long",
      year: "numeric"
    });
  }, [i18n.language, month]);

  if (!insights) {
    return null;
  }

  const monthStatus = insights.monthly.month;
  const hasRuleStatuses = ruleStatuses.length > 0;

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent>
        <Stack spacing={1.75}>
          <Typography variant="h6">{t("planning.ruleStatus.heading")}</Typography>
          {hasRuleStatuses ? (
            <Stack spacing={0.75}>
              {ruleStatuses.map((status) => {
                const statusLabel =
                  status.status === "ok"
                    ? t("planning.ruleStatus.status.ok")
                    : t(`planning.severity.${status.status}`);
                const countLabel =
                  status.count > 0
                    ? ` · ${t("planning.issueCount", { count: status.count })}`
                    : "";
                return (
                  <Stack key={status.code} spacing={0.25}>
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      {t(status.translationKey)}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      {statusLabel}
                      {countLabel}
                    </Typography>
                  </Stack>
                );
              })}
              <Divider />
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.noInsights")}
            </Typography>
          )}

          {monthStatus ? (
            <Typography variant="body2" color="text.secondary">
              {t("planning.monthlyStatus", {
                severity: t(`planning.severity.${monthStatus.severity}`),
                count: monthStatus.violations.length
              })}
            </Typography>
          ) : null}

          {formattedMonth ? (
            <Typography variant="caption" color="text.secondary">
              {t("planning.insightsFooter", { month: formattedMonth })}
            </Typography>
          ) : null}
        </Stack>
      </CardContent>
    </Card>
  );
};

export default PlanningInsightsPanel;
