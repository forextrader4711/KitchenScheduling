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
  IconButton,
  MenuItem,
  Slide,
  Snackbar,
  SlideProps,
  Stack,
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
import { Resource, Shift } from "../types";

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
};

type ResourcePayload = Omit<ResourceDto, "id">;

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
  notes: dto.notes
});

const toResourcePayload = (resource: Resource): ResourcePayload => ({
  name: resource.name,
  role: resource.role,
  availability_percent: resource.availabilityPercent,
  contract_hours_per_month: resource.contractHoursPerMonth,
  preferred_days_off: resource.preferredDaysOff ?? null,
  vacation_days: resource.vacationDays ?? null,
  language: resource.language,
  notes: resource.notes ?? null
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
    notes: ""
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
      setFormState(resource);
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
        notes: ""
      });
      setEditingResource(null);
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
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>{t("common.cancel")}</Button>
          <Button onClick={handleSubmit} variant="contained">
            {editingResource ? t("common.save") : t("common.create")}
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
