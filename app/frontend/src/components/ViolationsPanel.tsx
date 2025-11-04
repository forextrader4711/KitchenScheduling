import { Card, CardContent, Chip, List, ListItem, Stack, Typography } from "@mui/material";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const ViolationsPanel = () => {
  const { t } = useTranslation();
  const { violations } = useScheduleStore();

  const severityColor: Record<typeof violations[number]["severity"], "error" | "warning" | "info"> =
    {
      critical: "error",
      warning: "warning",
      info: "info"
    };

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom display="flex" alignItems="center" gap={1}>
          <ReportProblemIcon color={violations.length ? "warning" : "disabled"} />
          {t("violations.title")}
        </Typography>
        {violations.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            {t("violations.none")}
          </Typography>
        ) : (
          <List dense>
            {violations.map((violation) => (
              <ListItem
                key={violation.id}
                disablePadding
                sx={{
                  mb: 1.5,
                  "&:last-of-type": { mb: 0 }
                }}
              >
                <Stack spacing={1.25} sx={{ width: "100%" }}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                      {violation.category}
                    </Typography>
                    <Chip
                      size="small"
                      color={severityColor[violation.severity]}
                      label={violation.severity.toUpperCase()}
                    />
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    {violation.message}
                  </Typography>
                </Stack>
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default ViolationsPanel;
