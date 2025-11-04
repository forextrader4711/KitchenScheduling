import { useMemo } from "react";
import {
  Box,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Skeleton,
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
      <Card sx={{ minHeight: 420 }}>
        <CardContent>
          <Skeleton variant="text" width="45%" sx={{ mb: 2 }} />
          <Skeleton variant="rounded" height={280} />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card sx={{ minHeight: 420 }}>
      <CardHeader
        title={
          <Typography variant="h6" sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {t("planning.gridTitle", { month })}
            <Chip
              label={`${resources.length} ${
                resources.length === 1
                  ? t("planning.resource")
                  : t("planning.resourcePlural", { defaultValue: `${t("planning.resource")}s` })
              }`}
            />
          </Typography>
        }
        subheader={t("planning.gridHint", {
          defaultValue: "Use master data to adjust resources or shifts, then refresh the plan."
        })}
      />
      <CardContent sx={{ pt: 0 }}>
        <Box sx={{ overflowX: "auto" }}>
          <Table size="small" stickyHeader>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600 }}>{t("planning.resource")}</TableCell>
                {daysInMonth.map((day) => (
                  <TableCell
                    key={day}
                    align="center"
                    sx={{
                      fontWeight: 600,
                      borderLeft: day === daysInMonth[0] ? undefined : "1px solid rgba(51, 88, 255, 0.08)"
                    }}
                  >
                    {day}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {Object.entries(resourceMap).map(([resourceId, name], rowIndex) => (
                <TableRow
                  key={resourceId}
                  sx={{
                    bgcolor: rowIndex % 2 === 0 ? "rgba(51, 88, 255, 0.02)" : "transparent",
                    "&:hover": { bgcolor: "rgba(51, 88, 255, 0.06)" }
                  }}
                >
                  <TableCell component="th" scope="row" sx={{ fontWeight: 600 }}>
                    {name}
                  </TableCell>
                  {daysInMonth.map((day, index) => {
                    const key = `${resourceId}-${day}`;
                    const value = cellLookup[key] ?? "";
                    return (
                      <TableCell
                        key={key}
                        align="center"
                        sx={{
                          p: 1,
                          borderLeft: index === 0 ? undefined : "1px solid rgba(51, 88, 255, 0.08)"
                        }}
                      >
                        <Typography variant="body2" sx={{ fontWeight: value ? 600 : 400 }}>
                          {value}
                        </Typography>
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
