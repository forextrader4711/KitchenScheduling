import { Alert, Button, Card, CardActions, CardContent, Divider, Stack, Typography } from "@mui/material";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import api from "../services/api";
import useScheduleStore from "../state/scheduleStore";

const suggestionSeverityColor: Record<"info" | "warning" | "critical", "info" | "warning" | "error"> = {
  info: "info",
  warning: "warning",
  critical: "error"
};

const roleKeyMap: Record<string, string> = {
  pot_washers: "pot_washer",
  kitchen_assistants: "kitchen_assistant",
  apprentices: "apprentice",
  cooks: "cook",
  relief_cooks: "relief_cook"
};

const formatDate = (isoDate: string | undefined, locale: string) => {
  if (!isoDate) {
    return undefined;
  }
  try {
    return new Date(isoDate).toLocaleDateString(locale, {
      year: "numeric",
      month: "long",
      day: "numeric"
    });
  } catch {
    return isoDate;
  }
};

const PlanSuggestionsPanel = () => {
  const { t, i18n } = useTranslation();
  const { plans, activePhase, refreshOverviewOnly, isLoading } = useScheduleStore();
  const activePlan = plans[activePhase];
  const suggestions = activePlan?.suggestions ?? [];
  const scenarioId = activePlan?.scenario?.id ?? null;
  const [showAll, setShowAll] = useState(false);
  const [applyingId, setApplyingId] = useState<string | null>(null);

  const locale = i18n.language === "fr" ? "fr-CH" : "en-GB";

  const visibleSuggestions = useMemo(
    () => (showAll ? suggestions : suggestions.slice(0, 3)),
    [showAll, suggestions]
  );

  const resolveRoleLabel = (rawRole: unknown) => {
    if (typeof rawRole !== "string") {
      return undefined;
    }
    const normalizedKey = roleKeyMap[rawRole] ?? rawRole.replace(/s$/, "");
    const roleKey = normalizedKey.replace(/\s+/g, "_");
    const direct = t(`masterData.roles.${roleKey}`, { defaultValue: "" });
    if (direct) {
      return direct;
    }
    const shortLabel = t(`masterData.roleLabels.${roleKey}`, { defaultValue: "" });
    if (shortLabel) {
      return shortLabel;
    }
    return normalizedKey.replace(/_/g, " ");
  };

  const buildSuggestionCopy = (suggestion: (typeof suggestions)[number]) => {
    const meta = suggestion.metadata ?? {};
    const resourceName = typeof meta?.resource_name === "string" ? meta.resource_name : undefined;
    const roleLabel = resolveRoleLabel(meta?.role);
    const isoDate = typeof meta?.date === "string" ? meta.date : undefined;
    const formattedDate = formatDate(isoDate, locale);
    const replacements = {
      resource: resourceName ?? "",
      role: roleLabel ?? (typeof meta?.role === "string" ? meta.role : ""),
      roleRaw: typeof meta?.role === "string" ? meta.role : "",
      date: formattedDate ?? isoDate ?? "",
      week: typeof meta?.week === "string" ? meta.week : ""
    };

    const title = t(`planning.suggestions.types.${suggestion.type}.title`, {
      defaultValue: suggestion.title,
      ...replacements
    });
    const description = t(`planning.suggestions.types.${suggestion.type}.description`, {
      defaultValue: suggestion.description,
      ...replacements
    });

    return {
      title,
      description,
      displayDate: formattedDate ?? isoDate,
      displayRole: roleLabel ?? (typeof meta?.role === "string" ? meta.role : undefined)
    };
  };

  if (!suggestions.length) {
    return null;
  }

  const handleApply = async (suggestionId: string) => {
    if (!scenarioId) {
      return;
    }
    const suggestion = suggestions.find((item) => item.id === suggestionId);
    if (!suggestion?.change) {
      return;
    }

    try {
      setApplyingId(suggestionId);
      const labelText =
        t("planning.suggestions.appliedLabel", {
          title: suggestion.title,
          defaultValue: `Applied suggestion: ${suggestion.title}`
        }) || suggestion.title;

      await api.post(`/planning/scenarios/${scenarioId}/apply-suggestion`, {
        change: {
          action: suggestion.change.action,
          resource_id: suggestion.change.resourceId,
          date: suggestion.change.date,
          shift_code: suggestion.change.shiftCode ?? null,
          absence_type: suggestion.change.absenceType ?? null
        },
        label: labelText
      });
      await refreshOverviewOnly();
    } catch (error) {
      console.warn("Failed to apply suggestion", error);
    } finally {
      setApplyingId(null);
    }
  };

  return (
    <Card variant="outlined" sx={{ borderRadius: 2 }}>
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="h6">{t("planning.suggestions.title")}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t("planning.suggestions.subtitle")}
          </Typography>
          <Divider />
          <Stack spacing={1.25}>
            {visibleSuggestions.map((suggestion) => {
              const localized = buildSuggestionCopy(suggestion);
              const dateLine = suggestion.metadata?.date
                ? t("planning.suggestions.date", {
                    date: localized.displayDate ?? (suggestion.metadata?.date as string)
                  })
                : null;
              const roleLine = suggestion.metadata?.role
                ? t("planning.suggestions.role", {
                    role: localized.displayRole ?? (suggestion.metadata?.role as string)
                  })
                : null;
              const weekLine =
                typeof suggestion.metadata?.week === "string"
                  ? t("planning.suggestions.week", { week: suggestion.metadata.week as string })
                  : null;

              return (
                <Alert
                  key={suggestion.id}
                  severity={suggestionSeverityColor[suggestion.severity]}
                  variant="outlined"
                  icon={false}
                >
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    {localized.title}
                  </Typography>
                  <Typography variant="body2">{localized.description}</Typography>
                  {dateLine || roleLine || weekLine ? (
                    <Typography variant="caption" color="text.secondary">
                      {[dateLine, roleLine, weekLine].filter(Boolean).join(" · ")}
                    </Typography>
                  ) : null}
                  {suggestion.change ? (
                    <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
                      <Button
                        variant="contained"
                        size="small"
                        disabled={isLoading || applyingId === suggestion.id}
                        onClick={() => void handleApply(suggestion.id)}
                      >
                        {t("planning.suggestions.apply")}
                      </Button>
                    </Stack>
                  ) : null}
                </Alert>
              );
            })}
          </Stack>
        </Stack>
      </CardContent>
      {suggestions.length > 3 ? (
        <CardActions sx={{ justifyContent: "flex-end", pt: 0 }}>
          <Button onClick={() => setShowAll((prev) => !prev)} size="small">
            {showAll ? t("planning.suggestions.showLess") : t("planning.suggestions.showAll")}
          </Button>
        </CardActions>
      ) : null}
    </Card>
  );
};

export default PlanSuggestionsPanel;
