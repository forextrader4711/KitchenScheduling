import { Card, CardContent, List, ListItem, ListItemText, Typography } from "@mui/material";
import ReportProblemIcon from "@mui/icons-material/ReportProblem";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const ViolationsPanel = () => {
  const { t } = useTranslation();
  const { violations } = useScheduleStore();

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
              <ListItem key={violation.id} disablePadding>
                <ListItemText primary={violation.message} secondary={violation.category} />
              </ListItem>
            ))}
          </List>
        )}
      </CardContent>
    </Card>
  );
};

export default ViolationsPanel;
