import { SyntheticEvent, useEffect, useMemo, useState } from "react";
import {
  AppBar,
  Box,
  Button,
  Chip,
  Container,
  Fade,
  Grid,
  IconButton,
  Stack,
  Tab,
  Tabs,
  Toolbar,
  Typography
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useTranslation } from "react-i18next";

import PlanningGrid from "./components/PlanningGrid";
import MasterDataPanel from "./components/MasterDataPanel";
import SummaryPanel from "./components/SummaryPanel";
import ViolationsPanel from "./components/ViolationsPanel";
import useScheduleStore from "./state/scheduleStore";

const App = () => {
  const { t, i18n } = useTranslation();
  const { loadInitialData, month, resources, violations } = useScheduleStore();
  const [tab, setTab] = useState<"planning" | "masterData">("planning");

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

      <Container maxWidth="xl" sx={{ flexGrow: 1, py: 3 }}>
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
            <Chip
              color={violations.length ? "warning" : "success"}
              label={
                violations.length
                  ? `${violations.length} ${t("violations.title")}`
                  : t("violations.none")
              }
            />
            <Button variant="contained" onClick={() => void loadInitialData()}>
              {t("planning.refreshButton", { defaultValue: "Refresh data" })}
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
            <Grid container spacing={3}>
              <Grid item xs={12} md={8}>
                <PlanningGrid />
              </Grid>
              <Grid item xs={12} md={4}>
                <Stack spacing={3}>
                  <SummaryPanel />
                  <ViolationsPanel />
                </Stack>
              </Grid>
            </Grid>
          </Box>
        </Fade>

        <Fade in={tab === "masterData"} mountOnEnter unmountOnExit timeout={350}>
          <Box>
            <MasterDataPanel />
          </Box>
        </Fade>
      </Container>
    </Box>
  );
};

export default App;
