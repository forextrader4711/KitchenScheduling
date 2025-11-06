import { Card, CardContent, Divider, Stack, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const PlanVersionHistory = () => {
  const { t, i18n } = useTranslation();
  const activePhase = useScheduleStore((state) => state.activePhase);
  const plan = useScheduleStore((state) => state.plans[activePhase]);

  if (!plan || !plan.versions || plan.versions.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="h6">{t("planning.versionHistory.title")}</Typography>
          <Divider />
          <Stack spacing={1}>
            {plan.versions.map((version) => {
              const createdDate = new Date(version.createdAt).toLocaleString(
                i18n.language === "fr" ? "fr-FR" : "en-US",
                {
                  dateStyle: "medium",
                  timeStyle: "short"
                }
              );
              const summary = version.summary ?? {};
              return (
                <Stack key={version.id} spacing={0.25}>
                  <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                    {version.label}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {createdDate}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {t("planning.versionHistory.entries", { count: summary.entries ?? 0 })} ·{" "}
                    {t("planning.versionHistory.violations", { count: summary.violations ?? 0 })} ·{" "}
                    {t("planning.versionHistory.critical", { count: summary.critical_violations ?? 0 })}
                  </Typography>
                </Stack>
              );
            })}
          </Stack>
        </Stack>
      </CardContent>
    </Card>
  );
};

export default PlanVersionHistory;
