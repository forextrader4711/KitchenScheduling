import { forwardRef, useMemo, useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import EditIcon from "@mui/icons-material/Edit";
import {
  Alert,
  Avatar,
  Box,
  Button,
  Card,
  CardContent,
  CardHeader,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  MenuItem,
  Slide,
  Snackbar,
  SlideProps,
  Stack,
  Switch,
  Tab,
  Tabs,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import { useMutation, useQuery, useQueryClient } from "react-query";
import { useTranslation } from "react-i18next";

import api from "../services/api";
import useScheduleStore from "../state/scheduleStore";
import { Resource, ResourceAbsence, Shift, WeeklyAvailabilityEntry } from "../types";

type NotifyPayload = { message: string; severity: "success" | "error" };

type ResourceDto = {
  id: number;
  name: string;
  role: string;
  availability_percent: number;
  contract_hours_per_month: number;
  preferred_days_off?: string | null;
  vacation_days?: string | null;
  language: string;
  notes?: string | null;
  availability_template?: WeeklyAvailabilityEntryDto[] | null;
  preferred_shift_codes?: number[] | null;
  undesired_shift_codes?: number[] | null;
  absences?: ResourceAbsenceDto[];
};

type WeeklyAvailabilityEntryDto = {
  day: string;
  is_available: boolean;
  start_time?: string | null;
  end_time?: string | null;
};

type ResourceAbsenceDto = {
  id: number;
  start_date: string;
  end_date: string;
  absence_type: "vacation" | "sick_leave" | "training" | "other";
  comment?: string | null;
};

type ResourcePayload = Omit<ResourceDto, "id" | "absences">;

type AbsenceFormState = {
  startDate: string;
  endDate: string;
  absenceType: ResourceAbsence["absenceType"];
  comment: string;
};

type ShiftDto = {
  code: number;
  description: string;
  start: string;
  end: string;
  hours: number;
};

const toResource = (dto: ResourceDto): Resource => ({
  id: dto.id,
  name: dto.name,
  role: dto.role,
  availabilityPercent: dto.availability_percent,
  contractHoursPerMonth: dto.contract_hours_per_month,
  preferredDaysOff: dto.preferred_days_off,
  vacationDays: dto.vacation_days,
  language: dto.language,
  notes: dto.notes,
  availabilityTemplate: dto.availability_template
    ? dto.availability_template.map((entry) => ({
        day: entry.day as WeeklyAvailabilityEntry["day"],
        isAvailable: entry.is_available,
        startTime: entry.start_time ?? undefined,
        endTime: entry.end_time ?? undefined
      }))
    : undefined,
  preferredShiftCodes: dto.preferred_shift_codes ?? undefined,
  undesiredShiftCodes: dto.undesired_shift_codes ?? undefined,
  absences: dto.absences
    ? dto.absences.map((absence) => ({
        id: absence.id,
        startDate: absence.start_date,
        endDate: absence.end_date,
        absenceType: absence.absence_type,
        comment: absence.comment ?? undefined
      }))
    : []
});

const toResourcePayload = (resource: Resource): ResourcePayload => ({
  name: resource.name,
  role: resource.role,
  availability_percent: resource.availabilityPercent,
  contract_hours_per_month: resource.contractHoursPerMonth,
  preferred_days_off: resource.preferredDaysOff ?? null,
  vacation_days: resource.vacationDays ?? null,
  language: resource.language,
  notes: resource.notes ?? null,
  availability_template: resource.availabilityTemplate
    ? resource.availabilityTemplate.map((entry) => ({
        day: entry.day,
        is_available: entry.isAvailable,
        start_time: entry.startTime ?? null,
        end_time: entry.endTime ?? null
      }))
    : null,
  preferred_shift_codes: resource.preferredShiftCodes ?? null,
  undesired_shift_codes: resource.undesiredShiftCodes ?? null
});

const toShift = (dto: ShiftDto): Shift => ({
  code: dto.code,
  description: dto.description,
  start: dto.start,
  end: dto.end,
  hours: dto.hours
});

const SlideTransition = forwardRef<HTMLDivElement, SlideProps>(function SlideTransition(props, ref) {
  return <Slide direction="up" ref={ref} {...props} />;
});

const toSlug = (value: string) =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");

const defaultAvailabilityTemplate = (): WeeklyAvailabilityEntry[] => [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
].map((day) => ({
  day: day as WeeklyAvailabilityEntry["day"],
  isAvailable: day !== "saturday" && day !== "sunday",
  startTime: null,
  endTime: null
}));

const ABSENCE_TYPES: Array<ResourceAbsence["absenceType"]> = [
  "vacation",
  "sick_leave",
  "training",
  "other"
];

const parseShiftCodes = (input: string): number[] => {
  return input
    .split(/[\s,;]+/)
    .map((code) => code.trim())
    .filter(Boolean)
    .map((value) => Number.parseInt(value, 10))
    .filter((code) => !Number.isNaN(code));
};

const formatShiftCodes = (codes?: number[] | null): string => {
  if (!codes || codes.length === 0) {
    return "";
  }
  return codes.join(", ");
};

const mapAbsenceDto = (dto: ResourceAbsenceDto): ResourceAbsence => ({
  id: dto.id,
  startDate: dto.start_date,
  endDate: dto.end_date,
  absenceType: dto.absence_type,
  comment: dto.comment ?? undefined
});

const dayOrder: WeeklyAvailabilityEntry["day"][] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday"
];

const AvailabilityEditor = ({
  value,
  onChange
}: {
  value: WeeklyAvailabilityEntry[];
  onChange: (entries: WeeklyAvailabilityEntry[]) => void;
}) => {
  const { t } = useTranslation();

  const upsertEntry = (day: WeeklyAvailabilityEntry["day"], updater: (entry: WeeklyAvailabilityEntry) => WeeklyAvailabilityEntry) => {
    const entriesMap = new Map(value.map((entry) => [entry.day, entry] as const));
    const current = entriesMap.get(day) ?? {
      day,
      isAvailable: true,
      startTime: null,
      endTime: null
    };
    entriesMap.set(day, updater(current));
    onChange(dayOrder.map((d) => entriesMap.get(d) ?? {
      day: d,
      isAvailable: false,
      startTime: null,
      endTime: null
    }));
  };

  return (
    <Stack spacing={1.5} mt={1}>
      {dayOrder.map((day) => {
        const entry = value.find((item) => item.day === day) ?? {
          day,
          isAvailable: day !== "saturday" && day !== "sunday",
          startTime: null,
          endTime: null
        };
        return (
          <Box
            key={day}
            sx={{
              p: 1.5,
              border: "1px solid rgba(51, 88, 255, 0.1)",
              borderRadius: 2,
              bgcolor: entry.isAvailable ? "rgba(51, 88, 255, 0.06)" : "transparent"
            }}
          >
            <Stack direction="row" spacing={2} alignItems="center" justifyContent="space-between">
              <FormControlLabel
                control={
                  <Switch
                    checked={entry.isAvailable}
                    onChange={(event) =>
                      upsertEntry(day, (current) => ({
                        ...current,
                        isAvailable: event.target.checked,
                        startTime: event.target.checked ? current.startTime : null,
                        endTime: event.target.checked ? current.endTime : null
                      }))
                    }
                    color="primary"
                  />
                }
                label={t(`common.weekdays.${day}`)}
              />
              {entry.isAvailable && (
                <Stack direction="row" spacing={2} sx={{ minWidth: 220 }}>
                  <TextField
                    label={t("masterData.availability.startTime")}
                    type="time"
                    value={entry.startTime ?? ""}
                    onChange={(event) =>
                      upsertEntry(day, (current) => ({ ...current, startTime: event.target.value || null }))
                    }
                    size="small"
                    fullWidth
                    InputLabelProps={{ shrink: true }}
                  />
                  <TextField
                    label={t("masterData.availability.endTime")}
                    type="time"
                    value={entry.endTime ?? ""}
                    onChange={(event) =>
                      upsertEntry(day, (current) => ({ ...current, endTime: event.target.value || null }))
                    }
                    size="small"
                    fullWidth
                    InputLabelProps={{ shrink: true }}
                  />
                </Stack>
              )}
            </Stack>
          </Box>
        );
      })}
    </Stack>
  );
};

const MasterDataPanel = () => {
  const { t } = useTranslation();
  const [tab, setTab] = useState(0);
  const [toast, setToast] = useState<{ open: boolean; message: string; severity: "success" | "error" }>(
    { open: false, message: "", severity: "success" }
  );

  const handleNotify = (payload: NotifyPayload) => {
    setToast({ open: true, ...payload });
  };

  const handleToastClose = () => {
    setToast((prev) => ({ ...prev, open: false }));
  };

  return (
    <Card>
      <CardHeader title={t("masterData.title")} subheader={t("masterData.subtitle")} />
      <CardContent>
        <Tabs value={tab} onChange={(_, newValue: number) => setTab(newValue)} sx={{ mb: 2 }}>
          <Tab label={t("masterData.resourcesTab")} />
          <Tab label={t("masterData.shiftsTab")} />
        </Tabs>
        {tab === 0 ? (
          <ResourceManager onNotify={handleNotify} />
        ) : (
          <ShiftManager onNotify={handleNotify} />
        )}
      </CardContent>
      <Snackbar
        open={toast.open}
        autoHideDuration={3500}
        onClose={handleToastClose}
        anchorOrigin={{ vertical: "bottom", horizontal: "right" }}
        TransitionComponent={SlideTransition}
      >
        <Alert onClose={handleToastClose} severity={toast.severity} variant="filled" sx={{ borderRadius: 2 }}>
          {toast.message}
        </Alert>
      </Snackbar>
    </Card>
  );
};

const useLocalizedRoles = (t: ReturnType<typeof useTranslation>["t"]) => [
  { value: "cook", label: t("masterData.roles.cook") },
  { value: "kitchen_assistant", label: t("masterData.roles.kitchen_assistant") },
  { value: "pot_washer", label: t("masterData.roles.pot_washer") },
  { value: "apprentice", label: t("masterData.roles.apprentice") },
  { value: "relief_cook", label: t("masterData.roles.relief_cook") }
];

const useErrorMessage = (t: ReturnType<typeof useTranslation>["t"]) => {
  return (error: unknown) => {
    if (error && typeof error === "object" && "message" in error && typeof error.message === "string") {
      return error.message;
    }
    return t("common.unexpectedError");
  };
};

const ResourceManager = ({ onNotify }: { onNotify: (payload: NotifyPayload) => void }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { loadInitialData } = useScheduleStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [sortAscending, setSortAscending] = useState(true);
  const [editingResource, setEditingResource] = useState<Resource | null>(null);
  const roleOptions = useLocalizedRoles(t);
  const roleLabelMap = useMemo(
    () =>
      roleOptions.reduce<Record<string, string>>((acc, option) => {
        acc[option.value] = option.label;
        return acc;
      }, {}),
    [roleOptions]
  );
  const [formState, setFormState] = useState<Resource>({
    id: 0,
    name: "",
    role: roleOptions[0].value,
    availabilityPercent: 100,
    contractHoursPerMonth: 160,
    preferredDaysOff: "",
    vacationDays: "",
    language: "en",
    notes: "",
    availabilityTemplate: defaultAvailabilityTemplate(),
    preferredShiftCodes: [],
    undesiredShiftCodes: [],
    absences: []
  });
  const [absenceDialogOpen, setAbsenceDialogOpen] = useState(false);
  const [absenceDraft, setAbsenceDraft] = useState<AbsenceFormState>(() => {
    const today = new Date().toISOString().slice(0, 10);
    return {
      startDate: today,
      endDate: today,
      absenceType: "vacation",
      comment: ""
    };
  });

  const { data: resourceDtos = [], isLoading } = useQuery<ResourceDto[]>(["resources"], async () => {
    const response = await api.get<ResourceDto[]>("resources/");
    return response.data;
  });

  const resources = useMemo(() => resourceDtos.map(toResource), [resourceDtos]);
  const sortedResources = useMemo(() => {
    return [...resources].sort((a, b) => {
      const labelA = roleLabelMap[a.role] ?? a.role;
      const labelB = roleLabelMap[b.role] ?? b.role;
      if (labelA === labelB) {
        return a.name.localeCompare(b.name);
      }
      return sortAscending ? labelA.localeCompare(labelB) : labelB.localeCompare(labelA);
    });
  }, [resources, roleLabelMap, sortAscending]);
  const resolveErrorMessage = useErrorMessage(t);

  const resetForm = (resource?: Resource | null) => {
    if (resource) {
      setFormState({
        ...resource,
        availabilityTemplate: resource.availabilityTemplate
          ? resource.availabilityTemplate.map((entry) => ({ ...entry }))
          : defaultAvailabilityTemplate(),
        preferredShiftCodes: resource.preferredShiftCodes ? [...resource.preferredShiftCodes] : [],
        undesiredShiftCodes: resource.undesiredShiftCodes ? [...resource.undesiredShiftCodes] : [],
        absences: resource.absences ? [...resource.absences] : []
      });
      setEditingResource(resource);
    } else {
      setFormState({
        id: 0,
        name: "",
        role: roleOptions[0].value,
        availabilityPercent: 100,
        contractHoursPerMonth: 160,
        preferredDaysOff: "",
        vacationDays: "",
        language: "en",
        notes: "",
        availabilityTemplate: defaultAvailabilityTemplate(),
        preferredShiftCodes: [],
        undesiredShiftCodes: [],
        absences: []
      });
      setEditingResource(null);
    }
  };

  const handleOpenAbsenceDialog = () => {
    if (!editingResource) {
      return;
    }
    const today = new Date().toISOString().slice(0, 10);
    setAbsenceDraft({ startDate: today, endDate: today, absenceType: "vacation", comment: "" });
    setAbsenceDialogOpen(true);
  };

  const handleAbsenceFieldChange = <K extends keyof AbsenceFormState>(key: K, value: AbsenceFormState[K]) => {
    setAbsenceDraft((prev) => ({ ...prev, [key]: value }));
  };

  const handleSaveAbsence = async () => {
    if (!editingResource) {
      return;
    }
    try {
      const response = await api.post<ResourceAbsenceDto>(
        `resources/${editingResource.id}/absences`,
        {
          start_date: absenceDraft.startDate,
          end_date: absenceDraft.endDate,
          absence_type: absenceDraft.absenceType,
          comment: absenceDraft.comment || null
        }
      );
      const saved = mapAbsenceDto(response.data);
      setFormState((prev) =>
        prev
          ? {
              ...prev,
              absences: [...(prev.absences ?? []), saved]
            }
          : prev
      );
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      handleNotify({ message: t("masterData.notifications.absenceCreated"), severity: "success" });
      setAbsenceDialogOpen(false);
      void queryClient.invalidateQueries(["resources"]);
    } catch (error) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      handleNotify({ message: t("common.unexpectedError"), severity: "error" });
    }
  };

  const handleRemoveAbsence = async (absenceId: number) => {
    if (!editingResource) {
      return;
    }
    try {
      await api.delete(`resources/${editingResource.id}/absences/${absenceId}`);
      setFormState((prev) =>
        prev
          ? {
              ...prev,
              absences: prev.absences?.filter((absence) => absence.id !== absenceId) ?? []
            }
          : prev
      );
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      handleNotify({ message: t("masterData.notifications.absenceDeleted"), severity: "success" });
      void queryClient.invalidateQueries(["resources"]);
    } catch (error) {
      // eslint-disable-next-line @typescript-eslint/no-unsafe-call
      handleNotify({ message: t("common.unexpectedError"), severity: "error" });
    }
  };

  const handleOpenDialog = (resource?: Resource) => {
    resetForm(resource ?? null);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const invalidateResources = async () => {
    await queryClient.invalidateQueries(["resources"]);
    await loadInitialData();
  };

  const createResourceMutation = useMutation(
    async (payload: ResourcePayload) => {
      const response = await api.post<ResourceDto>("resources/", payload);
      return toResource(response.data);
    },
    {
      onSuccess: () => {
        void invalidateResources();
        onNotify({ message: t("masterData.notifications.resourceCreated"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const updateResourceMutation = useMutation(
    async (resource: Resource) => {
      const payload = toResourcePayload(resource);
      const response = await api.put<ResourceDto>(`resources/${resource.id}`, payload);
      return toResource(response.data);
    },
    {
      onSuccess: () => {
        void invalidateResources();
        onNotify({ message: t("masterData.notifications.resourceUpdated"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const deleteResourceMutation = useMutation(
    async (resourceId: number) => {
      await api.delete(`resources/${resourceId}`);
    },
    {
      onSuccess: () => {
        void invalidateResources();
        onNotify({ message: t("masterData.notifications.resourceDeleted"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const handleSubmit = () => {
    const payload = toResourcePayload(formState);
    if (editingResource) {
      updateResourceMutation.mutate({ ...formState });
    } else {
      createResourceMutation.mutate(payload);
    }
    setDialogOpen(false);
  };

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h6">{t("masterData.resourcesHeading")}</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => handleOpenDialog()}
          disabled={isLoading}
        >
          {t("masterData.addResource")}
        </Button>
      </Stack>

      <Table size="small" sx={{ "& td": { borderBottomColor: "rgba(51, 88, 255, 0.08)" } }}>
        <TableHead>
          <TableRow>
            <TableCell>{t("masterData.columns.name")}</TableCell>
            <TableCell
              sx={{ cursor: "pointer" }}
              onClick={() => setSortAscending((prev) => !prev)}
            >
              <Stack direction="row" spacing={1} alignItems="center">
                <Typography variant="body2" sx={{ fontWeight: 600 }}>
                  {t("masterData.columns.role")}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {sortAscending ? "▲" : "▼"}
                </Typography>
              </Stack>
            </TableCell>
            <TableCell align="right">{t("masterData.columns.availability")}</TableCell>
            <TableCell align="right">{t("masterData.columns.contractHours")}</TableCell>
            <TableCell>{t("masterData.columns.language")}</TableCell>
            <TableCell align="right" width={120}>
              {t("masterData.columns.actions")}
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {sortedResources.map((resource) => (
            <TableRow key={resource.id} hover>
              <TableCell>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Avatar sx={{ bgcolor: "primary.light", color: "primary.contrastText" }}>
                    {resource.name
                      .split(" ")
                      .map((part) => part.charAt(0).toUpperCase())
                      .join("")
                      .slice(0, 2)}
                  </Avatar>
                  <Typography variant="subtitle2" sx={{ fontWeight: 600 }}>
                    {resource.name}
                  </Typography>
                </Stack>
              </TableCell>
            <TableCell>
              <Chip
                size="small"
                color="primary"
                variant="outlined"
                label={roleLabelMap[resource.role] ?? resource.role.replace("_", " ")}
                sx={{ textTransform: "capitalize" }}
              />
            </TableCell>
              <TableCell align="right">{resource.availabilityPercent}</TableCell>
              <TableCell align="right">{resource.contractHoursPerMonth}</TableCell>
              <TableCell>{resource.language}</TableCell>
              <TableCell align="right">
                <IconButton aria-label="edit" size="small" onClick={() => handleOpenDialog(resource)}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  aria-label="delete"
                  size="small"
                  color="error"
                  onClick={() => deleteResourceMutation.mutate(resource.id)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
          {resources.length === 0 && (
            <TableRow>
              <TableCell colSpan={6}>
                <Typography variant="body2" color="text.secondary">
                  {t("masterData.noResources")}
                </Typography>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingResource ? t("masterData.editResource") : t("masterData.addResource")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("masterData.form.name")}
              value={formState.name}
              onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
              required
              fullWidth
            />
            <TextField
              select
              label={t("masterData.form.role")}
              value={formState.role}
              onChange={(event) => setFormState((prev) => ({ ...prev, role: event.target.value }))}
              fullWidth
            >
              {roleOptions.map((role) => (
                <MenuItem key={role.value} value={role.value}>
                  {role.label}
                </MenuItem>
              ))}
            </TextField>
              <Stack direction="row" spacing={2}>
              <TextField
                label={t("masterData.form.availability")}
                type="number"
                value={formState.availabilityPercent}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, availabilityPercent: Number(event.target.value) }))
                }
                fullWidth
                inputProps={{ min: 0, max: 100 }}
              />
              <TextField
                label={t("masterData.form.contractHours")}
                type="number"
                value={formState.contractHoursPerMonth}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, contractHoursPerMonth: Number(event.target.value) }))
                }
                fullWidth
              />
            </Stack>
            <TextField
              label={t("masterData.form.preferredDaysOff")}
              value={formState.preferredDaysOff ?? ""}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, preferredDaysOff: event.target.value || undefined }))
              }
              fullWidth
            />
            <TextField
              label={t("masterData.form.vacationDays")}
              value={formState.vacationDays ?? ""}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, vacationDays: event.target.value || undefined }))
              }
              fullWidth
            />
            <TextField
              label={t("masterData.form.language")}
              value={formState.language}
              onChange={(event) => setFormState((prev) => ({ ...prev, language: event.target.value }))}
              fullWidth
            />
            <TextField
              label={t("masterData.form.notes")}
              value={formState.notes ?? ""}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, notes: event.target.value || undefined }))
              }
              fullWidth
              multiline
              minRows={2}
            />
            <TextField
              label={t("masterData.form.preferredShifts")}
              value={formatShiftCodes(formState.preferredShiftCodes)}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  preferredShiftCodes: parseShiftCodes(event.target.value)
                }))
              }
              fullWidth
              helperText={t("masterData.form.preferredShiftsHint")}
            />
            <TextField
              label={t("masterData.form.undesiredShifts")}
              value={formatShiftCodes(formState.undesiredShiftCodes)}
              onChange={(event) =>
                setFormState((prev) => ({
                  ...prev,
                  undesiredShiftCodes: parseShiftCodes(event.target.value)
                }))
              }
              fullWidth
              helperText={t("masterData.form.undesiredShiftsHint")}
            />
          </Stack>
          <Box mt={3}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {t("masterData.availability.heading")}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t("masterData.availability.helper")}
            </Typography>
            <AvailabilityEditor
              value={formState.availabilityTemplate ?? defaultAvailabilityTemplate()}
              onChange={(entries) =>
                setFormState((prev) => ({ ...prev, availabilityTemplate: entries }))
              }
            />
          </Box>
          <Box mt={3}>
            <Stack direction="row" justifyContent="space-between" alignItems="center">
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                {t("masterData.absences.heading")}
              </Typography>
              <Button
                variant="outlined"
                size="small"
                onClick={handleOpenAbsenceDialog}
                disabled={!editingResource}
              >
                {t("masterData.absences.add")}
              </Button>
            </Stack>
            {formState.absences && formState.absences.length > 0 ? (
              <Stack direction="row" spacing={1} flexWrap="wrap" mt={2} useFlexGap>
                {formState.absences.map((absence) => (
                  <Chip
                    key={absence.id}
                    label={`${new Date(absence.startDate).toLocaleDateString()} → ${new Date(
                      absence.endDate
                    ).toLocaleDateString()} · ${t(`masterData.absenceTypes.${absence.absenceType}`)}`}
                    onDelete={() => void handleRemoveAbsence(absence.id)}
                    color="secondary"
                    variant="outlined"
                    sx={{ mb: 1 }}
                  />
                ))}
              </Stack>
            ) : (
              <Typography variant="body2" color="text.secondary" mt={1.5}>
                {t("masterData.absences.empty")}
              </Typography>
            )}
          </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingResource ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={absenceDialogOpen} onClose={() => setAbsenceDialogOpen(false)} maxWidth="xs" fullWidth>
        <DialogTitle>{t("masterData.absences.addTitle")}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("masterData.absences.startDate")}
              type="date"
              value={absenceDraft.startDate}
              onChange={(event) => handleAbsenceFieldChange("startDate", event.target.value)}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              label={t("masterData.absences.endDate")}
              type="date"
              value={absenceDraft.endDate}
              onChange={(event) => handleAbsenceFieldChange("endDate", event.target.value)}
              InputLabelProps={{ shrink: true }}
            />
            <TextField
              select
              label={t("masterData.absences.type")}
              value={absenceDraft.absenceType}
              onChange={(event) =>
                handleAbsenceFieldChange(
                  "absenceType",
                  event.target.value as ResourceAbsence["absenceType"]
                )
              }
            >
              {ABSENCE_TYPES.map((type) => (
                <MenuItem key={type} value={type}>
                  {t(`masterData.absenceTypes.${type}`)}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              label={t("masterData.absences.comment")}
              value={absenceDraft.comment}
              onChange={(event) => handleAbsenceFieldChange("comment", event.target.value)}
              fullWidth
              multiline
              minRows={2}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAbsenceDialogOpen(false)}>{t("common.cancel")}</Button>
          <Button onClick={() => void handleSaveAbsence()} variant="contained" disabled={!editingResource}>
            {t("masterData.absences.save")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

const ShiftManager = ({ onNotify }: { onNotify: (payload: NotifyPayload) => void }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { loadInitialData } = useScheduleStore();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingShift, setEditingShift] = useState<Shift | null>(null);
  const [formState, setFormState] = useState<Shift>({
    code: 0,
    description: "",
    start: "07:00",
    end: "16:00",
    hours: 8
  });

  const { data: shiftDtos = [] } = useQuery<ShiftDto[]>(["shifts"], async () => {
    const response = await api.get<ShiftDto[]>("shifts/");
    return response.data;
  });

  const shifts = useMemo(() => shiftDtos.map(toShift), [shiftDtos]);
  const resolveErrorMessage = useErrorMessage(t);

  const resetForm = (shift?: Shift | null) => {
    if (shift) {
      setFormState(shift);
      setEditingShift(shift);
    } else {
      setFormState({
        code: 0,
        description: "",
        start: "07:00",
        end: "16:00",
        hours: 8
      });
      setEditingShift(null);
    }
  };

  const handleOpenDialog = (shift?: Shift) => {
    resetForm(shift ?? null);
    setDialogOpen(true);
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
  };

  const invalidateShifts = async () => {
    await queryClient.invalidateQueries(["shifts"]);
    await loadInitialData();
  };

  const createShiftMutation = useMutation(
    async (shift: Shift) => {
      const response = await api.post<ShiftDto>("shifts/", {
        code: shift.code,
        description: shift.description,
        start: shift.start,
        end: shift.end,
        hours: shift.hours
      });
      return toShift(response.data);
    },
    {
      onSuccess: () => {
        void invalidateShifts();
        onNotify({ message: t("masterData.notifications.shiftCreated"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const updateShiftMutation = useMutation(
    async (shift: Shift) => {
      const response = await api.put<ShiftDto>(`shifts/${shift.code}`, {
        description: shift.description,
        start: shift.start,
        end: shift.end,
        hours: shift.hours
      });
      return toShift(response.data);
    },
    {
      onSuccess: () => {
        void invalidateShifts();
        onNotify({ message: t("masterData.notifications.shiftUpdated"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const deleteShiftMutation = useMutation(
    async (shiftCode: number) => {
      await api.delete(`shifts/${shiftCode}`);
    },
    {
      onSuccess: () => {
        void invalidateShifts();
        onNotify({ message: t("masterData.notifications.shiftDeleted"), severity: "success" });
      },
      onError: (error) => {
        onNotify({ message: resolveErrorMessage(error), severity: "error" });
      }
    }
  );

  const handleSubmit = () => {
    if (!formState.description) {
      return;
    }
    if (editingShift) {
      updateShiftMutation.mutate(formState);
    } else {
      createShiftMutation.mutate(formState);
    }
    setDialogOpen(false);
  };

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 2 }}>
        <Typography variant="h6">{t("masterData.shiftsHeading")}</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenDialog()}>
          {t("masterData.addShift")}
        </Button>
      </Stack>

      <Table size="small" sx={{ "& td": { borderBottomColor: "rgba(51, 88, 255, 0.08)" } }}>
        <TableHead>
          <TableRow>
            <TableCell>{t("masterData.columns.code")}</TableCell>
            <TableCell>{t("masterData.columns.description")}</TableCell>
            <TableCell>{t("masterData.columns.start")}</TableCell>
            <TableCell>{t("masterData.columns.end")}</TableCell>
            <TableCell align="right">{t("masterData.columns.hours")}</TableCell>
            <TableCell align="right" width={120}>
              {t("masterData.columns.actions")}
            </TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {shifts.map((shift) => (
            <TableRow key={shift.code} hover>
              <TableCell>{shift.code}</TableCell>
              <TableCell>
                {shift.description
                  ? t(`masterData.shiftNames.${toSlug(shift.description)}`, {
                      defaultValue: shift.description
                    })
                  : ""}
              </TableCell>
              <TableCell>{shift.start}</TableCell>
              <TableCell>{shift.end}</TableCell>
              <TableCell align="right">{shift.hours}</TableCell>
              <TableCell align="right">
                <IconButton aria-label="edit" size="small" onClick={() => handleOpenDialog(shift)}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  aria-label="delete"
                  size="small"
                  color="error"
                  onClick={() => deleteShiftMutation.mutate(shift.code)}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
          {shifts.length === 0 && (
            <TableRow>
              <TableCell colSpan={6}>
                <Typography variant="body2" color="text.secondary">
                  {t("masterData.noShifts")}
                </Typography>
              </TableCell>
            </TableRow>
          )}
        </TableBody>
      </Table>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>
          {editingShift ? t("masterData.editShift") : t("masterData.addShift")}
        </DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label={t("masterData.form.code")}
              type="number"
              value={formState.code}
              onChange={(event) => setFormState((prev) => ({ ...prev, code: Number(event.target.value) }))}
              fullWidth
              disabled={Boolean(editingShift)}
            />
            <TextField
              label={t("masterData.form.description")}
              value={formState.description}
              onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
              fullWidth
              required
            />
            <Stack direction="row" spacing={2}>
              <TextField
                label={t("masterData.form.start")}
                value={formState.start}
                onChange={(event) => setFormState((prev) => ({ ...prev, start: event.target.value }))}
                fullWidth
              />
              <TextField
                label={t("masterData.form.end")}
                value={formState.end}
                onChange={(event) => setFormState((prev) => ({ ...prev, end: event.target.value }))}
                fullWidth
              />
            </Stack>
            <TextField
              label={t("masterData.form.hours")}
              type="number"
              value={formState.hours}
              onChange={(event) => setFormState((prev) => ({ ...prev, hours: Number(event.target.value) }))}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingShift ? t("common.save") : t("common.create")}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default MasterDataPanel;
