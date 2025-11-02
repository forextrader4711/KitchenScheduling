import { useMemo } from "react";
import {
  Box,
  Card,
  CardContent,
  CircularProgress,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { useTranslation } from "react-i18next";

import useScheduleStore from "../state/scheduleStore";

const PlanningGrid = () => {
  const { t } = useTranslation();
  const { isLoading, month, planningEntries, resources } = useScheduleStore();

  const daysInMonth = useMemo(() => {
    if (!month) {
      return [];
    }
    const [year, monthIndex] = month.split("-").map(Number);
    const days = new Date(year, monthIndex, 0).getDate();
    return Array.from({ length: days }, (_, day) => day + 1);
  }, [month]);

  const resourceMap = useMemo(() => {
    return resources.reduce<Record<number, string>>((acc, resource) => {
      acc[resource.id] = resource.name;
      return acc;
    }, {});
  }, [resources]);

  const cellLookup = useMemo(() => {
    return planningEntries.reduce<Record<string, string>>((acc, entry) => {
      const entryDate = new Date(entry.date);
      const key = `${entry.resourceId}-${entryDate.getDate()}`;
      const shiftLabel =
        entry.shiftCode !== undefined && entry.shiftCode !== null
          ? String(entry.shiftCode)
          : entry.absenceType ?? "";
      acc[key] = shiftLabel;
      return acc;
    }, {});
  }, [planningEntries]);

  if (isLoading) {
    return (
      <Card sx={{ minHeight: 400, display: "flex", alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </Card>
    );
  }

  return (
    <Card sx={{ minHeight: 400 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t("planning.gridTitle", { month })}
        </Typography>
        <Divider sx={{ mb: 2 }} />
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t("planning.resource")}</TableCell>
                {daysInMonth.map((day) => (
                  <TableCell key={day} align="center">
                    {day}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(resourceMap).map(([resourceId, name]) => (
                <TableRow key={resourceId}>
                  <TableCell component="th" scope="row">
                    {name}
                  </TableCell>
                  {daysInMonth.map((day) => {
                    const key = `${resourceId}-${day}`;
                    const value = cellLookup[key] ?? "";
                    return (
                      <TableCell key={key} align="center">
                        <Typography variant="body2">{value}</Typography>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Box>
      </CardContent>
    </Card>
  );
};

export default PlanningGrid;
