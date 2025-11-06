import { SyntheticEvent, useEffect, useMemo, useState } from "react";
import {
  AppBar,
  Box,
  Button,
  Chip,
  type ChipProps,
  Container,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Fade,
  Grid,
  IconButton,
  Stack,
  Tab,
  Tabs,
  TextField,
  Toolbar,
  Typography
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useTranslation } from "react-i18next";

import PlanningGrid from "./components/PlanningGrid";
import MasterDataPanel from "./components/MasterDataPanel";
import SummaryPanel from "./components/SummaryPanel";
import ViolationsPanel from "./components/ViolationsPanel";
import PlanningInsightsPanel from "./components/PlanningInsightsPanel";
import PlanVersionHistory from "./components/PlanVersionHistory";
import PlanSuggestionsPanel from "./components/PlanSuggestionsPanel";
import useScheduleStore from "./state/scheduleStore";

const App = () => {
  const { t, i18n } = useTranslation();
  const {
    loadInitialData,
    refreshPreparationPlan,
    month,
    resources,
    plans,
    activePhase,
    setActivePhase,
    isLoading
  } = useScheduleStore();
  const [tab, setTab] = useState<"planning" | "masterData">("planning");
  const [generateDialogOpen, setGenerateDialogOpen] = useState(false);
  const [versionLabel, setVersionLabel] = useState("");

  useEffect(() => {
    void loadInitialData();
  }, [loadInitialData]);

  const toggleLanguage = () => {
    const next = i18n.language === "en" ? "fr" : "en";
    void i18n.changeLanguage(next);
  };

  const handleTabChange = (_event: SyntheticEvent, value: "planning" | "masterData") => {
    setTab(value);
  };

  const handlePhaseChange = (_event: SyntheticEvent, value: "preparation" | "approved") => {
    setActivePhase(value);
  };

  const heroMonthLabel = useMemo(() => {
    if (!month) {
      return "";
    }
    const anchorDate = new Date(`${month}-01T00:00:00`);
    return anchorDate.toLocaleDateString(i18n.language === "fr" ? "fr-FR" : "en-US", {
      month: "long",
      year: "numeric"
    });
  }, [i18n.language, month]);

  const preparationViolations = plans.preparation?.violations.length ?? 0;
  const approvedPlan = plans.approved;
  const statusChip: { color: ChipProps["color"]; label: string } =
    activePhase === "preparation"
      ? {
          color: preparationViolations ? "warning" : "success",
          label: preparationViolations
            ? t("planning.preparationIssues", {
                defaultValue: "{{count}} rule issues",
                count: preparationViolations
              })
            : t("planning.preparationAllClear", { defaultValue: "All rules satisfied" })
        }
      : approvedPlan
      ? {
          color: "success" as const,
          label: t("planning.approvedReady", { defaultValue: "Approved plan stored" })
        }
      : {
          color: "default" as const,
          label: t("planning.noApprovedPlan", { defaultValue: "Awaiting approval" })
        };

  const phaseHint =
    activePhase === "preparation"
      ? t("planning.preparationHint", {
          defaultValue: "Resolve rule violations before approving the plan."
        })
      : approvedPlan
      ? t("planning.approvedHint", {
          defaultValue: "Review the approved plan and tracked hours."
        })
      : t("planning.approvedEmpty", {
          defaultValue: "No approved plan stored yet."
        });

  const primaryActionLabel =
    activePhase === "preparation"
      ? t("planning.generateAndSaveButton", { defaultValue: "Generate compliant plan" })
      : t("planning.refreshButton", { defaultValue: "Refresh data" });

  const handlePrimaryAction = () => {
    if (activePhase === "preparation") {
      const now = new Date();
      const formatted = now.toISOString().slice(0, 16).replace("T", " ");
      setVersionLabel(`Auto ${formatted}`);
      setGenerateDialogOpen(true);
    } else {
      void loadInitialData();
    }
  };

  const handleGenerateConfirm = async () => {
    await refreshPreparationPlan(versionLabel.trim() || undefined);
    setGenerateDialogOpen(false);
  };

  return (
    <Box display="flex" flexDirection="column" height="100%">
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <IconButton edge="start" color="inherit" aria-label="menu" sx={{ mr: 2 }}>
            <MenuIcon />
          </IconButton>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            {t("app.title")}
          </Typography>
          <Button color="inherit" onClick={toggleLanguage}>
            {t("actions.toggleLanguage")}
          </Button>
        </Toolbar>
      </AppBar>

      <Container maxWidth={false} sx={{ flexGrow: 1, py: 3, px: { xs: 2, md: 4 } }}>
        <Box
          sx={{
            mb: 4,
            p: 3,
            borderRadius: 4,
            border: "1px solid rgba(51, 88, 255, 0.14)",
            background:
              "linear-gradient(135deg, rgba(51, 88, 255, 0.14) 0%, rgba(255, 181, 71, 0.14) 100%)",
            display: "flex",
            flexDirection: { xs: "column", md: "row" },
            alignItems: { xs: "flex-start", md: "center" },
            justifyContent: "space-between",
            gap: 2
          }}
        >
          <Stack spacing={1}>
            <Typography variant="h4">
              {heroMonthLabel ? t("planning.gridTitle", { month: heroMonthLabel }) : t("app.title")}
            </Typography>
            <Typography variant="body1" color="text.secondary">
              {t("planning.heroSubtitle", {
                defaultValue:
                  "Review generated schedules, balance hours, and keep master data up to date."
              })}
            </Typography>
          </Stack>
          <Stack direction="row" spacing={2} alignItems="center">
            <Chip
              color="primary"
              label={`${resources.length} ${
                resources.length === 1
                  ? t("planning.resource")
                  : t("planning.resourcePlural", { defaultValue: `${t("planning.resource")}s` })
              }`}
            />
            <Chip color={statusChip.color} label={statusChip.label} />
            <Button variant="contained" disabled={isLoading} onClick={handlePrimaryAction}>
              {primaryActionLabel}
            </Button>
          </Stack>
        </Box>

        <Tabs
          value={tab}
          onChange={handleTabChange}
          sx={{ borderBottom: (theme) => `1px solid ${theme.palette.divider}`, mb: 3 }}
        >
          <Tab label={t("planning.tabLabel")} value="planning" />
          <Tab label={t("masterData.tabLabel")} value="masterData" />
        </Tabs>

        <Fade in={tab === "planning"} mountOnEnter unmountOnExit timeout={350}>
          <Box>
            <Box sx={{ mb: 3 }}>
              <Tabs
                value={activePhase}
                onChange={handlePhaseChange}
                sx={{ borderBottom: (theme) => `1px solid ${theme.palette.divider}`, mb: 1.5 }}
              >
                <Tab label={t("planning.preparationTab")} value="preparation" />
                <Tab
                  label={t("planning.approvedTab")}
                  value="approved"
                  disabled={!approvedPlan || approvedPlan.entries.length === 0}
                />
              </Tabs>
              <Typography variant="body2" color="text.secondary">
                {phaseHint}
              </Typography>
            </Box>
            <Stack spacing={3}>
              <PlanningGrid />

              <Grid container spacing={3} alignItems="stretch">
                {activePhase === "preparation" ? (
                  <Grid item xs={12} md={6} xl={3}>
                    <ViolationsPanel />
                  </Grid>
                ) : null}
                {activePhase === "preparation" ? (
                  <Grid item xs={12} md={6} xl={3}>
                    <PlanSuggestionsPanel />
                  </Grid>
                ) : null}
                <Grid item xs={12} md={6} xl={3}>
                  <PlanningInsightsPanel />
                </Grid>
                <Grid item xs={12} md={6} xl={3}>
                  <PlanVersionHistory />
                </Grid>
                {activePhase === "approved" && approvedPlan ? (
                  <Grid item xs={12} md={6} xl={3}>
                    <SummaryPanel />
                  </Grid>
                ) : null}
                {activePhase === "approved" && !approvedPlan ? (
                  <Grid item xs={12} md={6} xl={3}>
                    <Box
                      sx={{
                        borderRadius: 3,
                        border: "1px dashed rgba(51, 88, 255, 0.3)",
                        p: 3,
                        bgcolor: "rgba(51, 88, 255, 0.04)"
                      }}
                    >
                      <Typography variant="subtitle1" sx={{ fontWeight: 600 }} gutterBottom>
                        {t("planning.noApprovedPlan", { defaultValue: "Awaiting approval" })}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        {t("planning.approvedEmpty", {
                          defaultValue: "Run and approve a plan to see the final overview here."
                        })}
                      </Typography>
                    </Box>
                  </Grid>
                ) : null}
              </Grid>
            </Stack>
          </Box>
        </Fade>

        <Fade in={tab === "masterData"} mountOnEnter unmountOnExit timeout={350}>
          <Box>
            <MasterDataPanel />
          </Box>
        </Fade>
      </Container>

      <Dialog open={generateDialogOpen} onClose={() => setGenerateDialogOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t("planning.generateDialog.title")}</DialogTitle>
        <DialogContent>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t("planning.generateDialog.description")}
          </Typography>
          <TextField
            label={t("planning.generateDialog.label")}
            fullWidth
            value={versionLabel}
            onChange={(event) => setVersionLabel(event.target.value)}
            autoFocus
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setGenerateDialogOpen(false)}>{t("planning.generateDialog.cancel")}</Button>
          <Button
            onClick={() => void handleGenerateConfirm()}
            variant="contained"
            disabled={isLoading}
          >
            {t("planning.generateDialog.confirm")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default App;
