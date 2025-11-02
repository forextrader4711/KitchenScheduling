import { Card, CardContent, List, ListItem, ListItemText, Typography } from "@mui/material";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const SummaryPanel = () => {
  const { t } = useTranslation();
  const { summaries } = useScheduleStore();

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t("summary.title")}
        </Typography>
        <List dense>
          {summaries.map((summary) => (
            <ListItem key={summary.resourceId} disablePadding>
              <ListItemText
                primary={summary.name}
                secondary={t("summary.hours", {
                  worked: summary.workedHours,
                  contract: summary.contractHours
                })}
              />
            </ListItem>
          ))}
        </List>
      </CardContent>
    </Card>
  );
};

export default SummaryPanel;
