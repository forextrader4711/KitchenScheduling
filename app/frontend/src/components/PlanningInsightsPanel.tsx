import { Card, CardContent, Divider, Stack, Typography } from "@mui/material";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const severityRank: Record<"info" | "warning" | "critical", number> = {
  info: 0,
  warning: 1,
  critical: 2
};

const PlanningInsightsPanel = () => {
  const { t, i18n } = useTranslation();
  const { plans, activePhase, month, resources } = useScheduleStore();
  const insights = plans[activePhase]?.insights;

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

  const sortedDays = useMemo(() => {
    if (!insights) {
      return [];
    }
    return Object.entries(insights.daily)
      .sort((a, b) => severityRank[b[1].severity] - severityRank[a[1].severity])
      .slice(0, 4);
  }, [insights]);

  const resourceMap = useMemo(() => {
    return resources.reduce<Record<number, string>>((acc, resource) => {
      acc[resource.id] = resource.name;
      return acc;
    }, {});
  }, [resources]);

  const sortedResources = useMemo(() => {
    if (!insights) {
      return [];
    }
    return Object.entries(insights.resource)
      .sort((a, b) => severityRank[b[1].severity] - severityRank[a[1].severity])
      .slice(0, 4)
      .map(([resourceId, insight]) => ({
        resourceId: Number(resourceId),
        insight
      }));
  }, [insights]);

  const weeklyIssues = useMemo(() => {
    if (!insights) {
      return [];
    }
    return Object.entries(insights.weekly)
      .sort((a, b) => severityRank[b[1].severity] - severityRank[a[1].severity])
      .slice(0, 4);
  }, [insights]);

  if (!insights) {
    return null;
  }

  const monthStatus = insights.monthly.month;

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.75}>
          <Typography variant="h6">{t("planning.insightsTitle")}</Typography>
          {monthStatus ? (
            <Typography variant="body2" color="text.secondary">
              {t("planning.monthlyStatus", {
                severity: t(`planning.severity.${monthStatus.severity}`),
                count: monthStatus.violations.length
              })}
            </Typography>
          ) : (
            <Typography variant="body2" color="text.secondary">
              {t("planning.noInsights")}
            </Typography>
          )}

          {sortedDays.length > 0 ? (
            <Stack spacing={0.75}>
              <Divider textAlign="left">{t("planning.dailyBreakdown")}</Divider>
              {sortedDays.map(([day, item]) => (
                <Typography key={day} variant="body2">
                  <strong>
                    {new Date(`${day}T00:00:00`).toLocaleDateString(
                      i18n.language === "fr" ? "fr-FR" : "en-US",
                      { day: "numeric", month: "short" }
                    )}
                  </strong>
                  {": "}
                  {t("planning.issueCount", {
                    count: item.violations.length
                  })}
                  {" · "}
                  {t(`planning.severity.${item.severity}`)}
                </Typography>
              ))}
            </Stack>
          ) : null}

          {sortedResources.length > 0 ? (
            <Stack spacing={0.75}>
              <Divider textAlign="left">{t("planning.resourceBreakdown")}</Divider>
              {sortedResources.map(({ resourceId, insight }) => (
                <Typography key={resourceId} variant="body2">
                  <strong>{resourceMap[resourceId] ?? t("planning.unknownResource")}</strong>
                  {": "}
                  {t("planning.issueCount", { count: insight.violations.length })}
                  {" · "}
                  {t(`planning.severity.${insight.severity}`)}
                </Typography>
              ))}
            </Stack>
          ) : null}

          {weeklyIssues.length > 0 ? (
            <Stack spacing={0.75}>
              <Divider textAlign="left">{t("planning.weeklyBreakdown")}</Divider>
              {weeklyIssues.map(([week, item]) => (
                <Typography key={week} variant="body2">
                  <strong>{week}</strong>
                  {": "}
                  {t("planning.issueCount", { count: item.violations.length })}
                  {" · "}
                  {t(`planning.severity.${item.severity}`)}
                </Typography>
              ))}
            </Stack>
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
