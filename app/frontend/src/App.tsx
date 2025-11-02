import { useEffect } from "react";
import {
  AppBar,
  Box,
  Button,
  Container,
  Grid,
  IconButton,
  Toolbar,
  Typography
} from "@mui/material";
import MenuIcon from "@mui/icons-material/Menu";
import { useTranslation } from "react-i18next";

import PlanningGrid from "./components/PlanningGrid";
import SummaryPanel from "./components/SummaryPanel";
import ViolationsPanel from "./components/ViolationsPanel";
import useScheduleStore from "./state/scheduleStore";

const App = () => {
  const { t, i18n } = useTranslation();
  const { loadInitialData } = useScheduleStore();

  useEffect(() => {
    void loadInitialData();
  }, [loadInitialData]);

  const toggleLanguage = () => {
    const next = i18n.language === "en" ? "fr" : "en";
    void i18n.changeLanguage(next);
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

      <Container maxWidth="xl" sx={{ flexGrow: 1, py: 3 }}>
        <Grid container spacing={3} height="100%">
          <Grid item xs={12} md={8}>
            <PlanningGrid />
          </Grid>
          <Grid item xs={12} md={4}>
            <SummaryPanel />
            <Box mt={3}>
              <ViolationsPanel />
            </Box>
          </Grid>
        </Grid>
      </Container>
    </Box>
  );
};

export default App;
