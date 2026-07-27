import { createFileRoute } from "@tanstack/react-router";
import { useHasRole } from "@/lib/permissions";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Label } from "@/components/ui/label";
import { roleLabels } from "@/lib/mock-data";
import type { Role } from "@/lib/mock-data";
import { AnimatePresence, motion } from "framer-motion";
import { useState, useEffect, useMemo, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchUsers,
  createUser,
  updateUser,
  activateUser,
  deactivateUser,
  resetUserPassword,
  deleteUser,
} from "@/lib/api/accounts";
import type { AccountUser } from "@/lib/api/accounts";
import { fetchDepartments, fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Department, Direction, Unit } from "@/lib/api/directions-units";
import { toast } from "sonner";
import {
  Search,
  Shield,
  UserPlus,
  Pencil,
  KeyRound,
  UserCheck,
  UserX,
  Trash2,
  Plus,
} from "lucide-react";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/users")({
  head: () => ({ meta: [{ title: "Utilisateurs & Rôles — Admin EDG" }] }),
  component: AdminUsers,
});

const ROLES: Role[] = ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"];

const statusBadge: Record<string, string> = {
  active: "bg-success/15 text-success",
  inactive: "bg-muted text-muted-foreground",
  suspended: "bg-destructive/15 text-destructive",
};
const statusLabel: Record<string, string> = {
  active: "Actif",
  inactive: "Inactif",
  suspended: "Suspendu",
};

type FormData = {
  name: string;
  firstname: string;
  email: string;
  role: Role;
  matricule: string;
  job: string;
  direction_id: string;
  department_id: string;
  unit_id: string;
  is_edg_employee: boolean;
  password: string;
};

const emptyForm = (): FormData => ({
  name: "",
  firstname: "",
  email: "",
  role: "user",
  matricule: "",
  job: "",
  direction_id: "",
  department_id: "",
  unit_id: "",
  is_edg_employee: true,
  password: "",
});

type OrgTarget = "direction" | "department" | "unit";

const USER_FORM_ROLE_OPTIONS: Array<{ value: Role; label: string }> = [
  { value: "user", label: roleLabels.user },
  { value: "agent-support", label: roleLabels["agent-support"] },
  { value: "chief-service", label: roleLabels["chief-service"] },
  { value: "chief-departement", label: roleLabels["chief-departement"] },
  { value: "director", label: roleLabels.director },
  { value: "admin", label: roleLabels.admin },
];

// Niveau organisationnel requis selon BR-ADMIN-USER-ORG-001 :
// director -> direction ; chief-departement -> departement ; les autres -> service/unite.
function orgTargetForRole(role: Role): OrgTarget {
  if (role === "director") return "direction";
  if (role === "chief-departement") return "department";
  return "unit";
}

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
}

function fullName(u?: { name: string; firstname?: string } | null): string {
  if (!u) return "";
  return [u.firstname, u.name].filter(Boolean).join(" ");
}

function AdminUsers() {
  const qc = useQueryClient();
  const isAdmin = useHasRole("admin");

  // ── State ──────────────────────────────────────────────────────────────────
  const [q, setQ] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [roleFilter, setRoleFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");

  // dialogs
  const [createOpen, setCreateOpen] = useState(false);
  const [editUser, setEditUser] = useState<AccountUser | null>(null);
  const [resetUser, setResetUser] = useState<AccountUser | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<AccountUser | null>(null);
  const [newPassword, setNewPassword] = useState("");

  // form
  const [form, setForm] = useState<FormData>(emptyForm());

  // ── Action rapide flottante (visible apres scroll) ──────────────────────────
  const pageRef = useRef<HTMLDivElement>(null);
  const [showQuickCreate, setShowQuickCreate] = useState(false);

  useEffect(() => {
    const scrollEl = pageRef.current?.closest("main");
    if (!scrollEl) return;
    const handleScroll = () => setShowQuickCreate(scrollEl.scrollTop > 240);
    scrollEl.addEventListener("scroll", handleScroll);
    return () => scrollEl.removeEventListener("scroll", handleScroll);
  }, []);

  // Debounce search
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 400);
    return () => clearTimeout(t);
  }, [q]);

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data, isLoading } = useQuery({
    queryKey: ["admin", "users", debouncedQ, roleFilter],
    queryFn: () => fetchUsers({
      limit: 200,
      ...(debouncedQ ? { search: debouncedQ } : {}),
      ...(roleFilter !== "all" ? { role: roleFilter } : {}),
    }),
  });
  const list: AccountUser[] = data?.items ?? [];

  const { data: directionsData } = useQuery({
    queryKey: ["directions", "all"],
    queryFn: () => fetchDirections({ status: "all" }),
  });
  const directions: Direction[] = useMemo(() => directionsData ?? [], [directionsData]);
  const activeDirections = useMemo(
    () => directions.filter((direction) => direction.status),
    [directions],
  );

  const { data: allDepartmentsData } = useQuery({
    queryKey: ["departments", "all"],
    queryFn: () => fetchDepartments({ status: "all" }),
  });
  const allDepartments: Department[] = useMemo(() => allDepartmentsData ?? [], [allDepartmentsData]);

  const { data: departmentsData } = useQuery({
    queryKey: ["departments", "direction", form.direction_id],
    queryFn: () => fetchDepartments({ directionId: form.direction_id, status: "active" }),
    enabled: !!form.direction_id,
  });
  const departments: Department[] = useMemo(() => departmentsData ?? [], [departmentsData]);

  // Toutes les unités — pour dériver la direction depuis unit_id dans le tableau
  const { data: allUnitsData } = useQuery({
    queryKey: ["units", "all"],
    queryFn: () => fetchUnits({ status: "all" }),
  });
  const allUnits: Unit[] = useMemo(() => allUnitsData ?? [], [allUnitsData]);

  // Unités filtrées par département pour le formulaire d'édition/création
  const { data: unitsData } = useQuery({
    queryKey: ["units", "department", form.department_id],
    queryFn: () => fetchUnits({ departmentId: form.department_id, status: "active" }),
    enabled: !!form.department_id,
  });
  const units: Unit[] = useMemo(() => unitsData ?? [], [unitsData]);

  const directionsById = useMemo(
    () => new Map(directions.map((direction) => [direction.id, direction])),
    [directions],
  );
  const departmentsById = useMemo(
    () => new Map(allDepartments.map((department) => [department.id, department])),
    [allDepartments],
  );
  const unitsById = useMemo(
    () => new Map(allUnits.map((unit) => [unit.id, unit])),
    [allUnits],
  );

  // ── Mutations ──────────────────────────────────────────────────────────────
  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "users"], exact: false });

  const createMut = useMutation({
    mutationFn: async ({ data, password }: { data: Parameters<typeof createUser>[0]; password: string }) => {
      const newUser = await createUser(data);
      await resetUserPassword(newUser.id, password);
      return newUser;
    },
    onSuccess: () => { invalidate(); setCreateOpen(false); toast.success("Compte créé avec succès."); },
    onError: () => toast.error("Erreur lors de la création du compte."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateUser>[1] }) =>
      updateUser(id, data),
    onSuccess: () => { invalidate(); setEditUser(null); toast.success("Compte mis à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const activateMut = useMutation({
    mutationFn: (id: string) => activateUser(id),
    onSuccess: () => { invalidate(); toast.success("Compte activé."); },
    onError: () => toast.error("Erreur lors de l'activation."),
  });

  const deactivateMut = useMutation({
    mutationFn: (id: string) => deactivateUser(id),
    onSuccess: () => { invalidate(); toast.success("Compte désactivé."); },
    onError: () => toast.error("Erreur lors de la désactivation."),
  });

  const resetMut = useMutation({
    mutationFn: ({ id, pwd }: { id: string; pwd: string }) =>
      resetUserPassword(id, pwd),
    onSuccess: () => { setResetUser(null); setNewPassword(""); toast.success("Mot de passe réinitialisé."); },
    onError: () => toast.error("Erreur lors de la réinitialisation."),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => { invalidate(); setDeleteTarget(null); toast.success("Compte supprimé."); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  // ── Filtering ──────────────────────────────────────────────────────────────
  // search + role are handled server-side; only status remains client-side
  const filtered = list.filter((u) =>
    statusFilter === "all" || u.account_status === statusFilter
  );

  const { paged, page, setPage, totalPages, total, pageSize, setPageSize } =
    usePagination(filtered, 12);

  // ── Helpers ────────────────────────────────────────────────────────────────
  function resolveAssignment(unityId?: string, fallbackDirectionId?: string) {
    if (unityId) {
      const unit = unitsById.get(unityId);
      if (unit) {
        return {
          kind: "unit" as const,
          direction_id: unit.direction_id ?? fallbackDirectionId ?? "",
          department_id: unit.department_id ?? "",
          unit_id: unit.id,
        };
      }

      const department = departmentsById.get(unityId);
      if (department) {
        return {
          kind: "department" as const,
          direction_id: department.direction_id ?? fallbackDirectionId ?? "",
          department_id: department.id,
          unit_id: "",
        };
      }

      const direction = directionsById.get(unityId);
      if (direction) {
        return {
          kind: "direction" as const,
          direction_id: direction.id,
          department_id: "",
          unit_id: "",
        };
      }
    }

    return {
      kind: "none" as const,
      direction_id: fallbackDirectionId ?? "",
      department_id: "",
      unit_id: "",
    };
  }

  function buildOrgPayload(current: FormData) {
    const target = orgTargetForRole(current.role);
    if (target === "direction") {
      return {
        direction_id: current.direction_id || undefined,
        department_id: undefined,
        unit_id: undefined,
      };
    }
    if (target === "department") {
      return {
        direction_id: current.direction_id || undefined,
        department_id: current.department_id || undefined,
        unit_id: undefined,
      };
    }
    return {
      direction_id: current.direction_id || undefined,
      department_id: current.department_id || undefined,
      unit_id: current.unit_id || undefined,
    };
  }

  function validationMessage(current: FormData, requirePassword: boolean) {
    if (!current.name.trim()) return "Le nom de famille est obligatoire.";
    if (requirePassword && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(current.email.trim())) {
      return "L'adresse email est obligatoire et doit être valide.";
    }
    if (requirePassword && current.password.length < 8) {
      return "Le mot de passe doit contenir au moins 8 caractères.";
    }

    const target = orgTargetForRole(current.role);
    if (!current.direction_id) return "La direction est obligatoire pour ce rôle.";
    if ((target === "department" || target === "unit") && !current.department_id) {
      return "Le département est obligatoire pour ce rôle.";
    }
    if (target === "unit" && !current.unit_id) {
      return "Le service ou l'unité est obligatoire pour ce rôle.";
    }
    return null;
  }

  function openCreate() {
    setForm(emptyForm());
    setCreateOpen(true);
  }

  function openEdit(u: AccountUser) {
    const assignment = resolveAssignment(u.unit_id, u.direction_id);
    setForm({
      name: u.name,
      firstname: u.firstname ?? "",
      email: u.email,
      role: u.role as Role,
      matricule: u.matricule ?? "",
      job: u.job ?? "",
      direction_id: assignment.direction_id,
      department_id: assignment.department_id,
      unit_id: assignment.unit_id,
      password: "",
      is_edg_employee: true,
    });
    setEditUser(u);
  }

  const createValidation = validationMessage(form, true);
  const editValidation = validationMessage(form, false);
  const isCreateValid = !createValidation;

  function submitCreate() {
    const error = validationMessage(form, true);
    if (error) {
      toast.error(error);
      return;
    }
    if (createMut.isPending) return;
    createMut.mutate({
      data: {
        name: form.name.trim(),
        firstname: form.firstname.trim() || undefined,
        email: form.email.trim(),
        role: form.role,
        matricule: form.matricule || undefined,
        job: form.job || undefined,
        ...buildOrgPayload(form),
        is_edg_employee: form.is_edg_employee,
      },
      password: form.password,
    });
  }

  function submitEdit() {
    if (!editUser) return;
    const error = validationMessage(form, false);
    if (error) {
      toast.error(error);
      return;
    }
    updateMut.mutate({
      id: editUser.id,
      data: {
        name: form.name.trim() || undefined,
        firstname: form.firstname.trim() || undefined,
        role: form.role,
        matricule: form.matricule || undefined,
        job: form.job || undefined,
        ...buildOrgPayload(form),
      },
    });
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div ref={pageRef} className="mx-auto max-w-7xl space-y-6">
      {/* Header */}
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Shield className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Utilisateurs & Rôles
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gérez les comptes, rôles, directions et statuts des utilisateurs EDG Support.
          </p>
        </div>
        {isAdmin && (
          <Button className="gradient-primary rounded-full" onClick={openCreate}>
            <UserPlus className="mr-2 h-4 w-4" /> Nouvel utilisateur
          </Button>
        )}
      </header>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "Total", value: list.length },
          { label: "Actifs", value: list.filter((u) => u.account_status === "active").length },
          { label: "Agents", value: list.filter((u) => u.role === "agent-support").length },
          { label: "Admins", value: list.filter((u) => u.role === "admin").length },
        ].map((s) => (
          <GlassCard key={s.label} className="py-4">
            <div className="text-sm text-muted-foreground">{s.label}</div>
            <div className="mt-1 text-2xl font-bold">{s.value}</div>
          </GlassCard>
        ))}
      </div>

      {/* Filters */}
      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Nom, email, matricule…"
            className="h-10 rounded-full pl-9"
          />
        </div>
        <Select value={roleFilter} onValueChange={setRoleFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-44">
            <SelectValue placeholder="Tous les rôles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les rôles</SelectItem>
            {ROLES.map((r) => (
              <SelectItem key={r} value={r}>{roleLabels[r]}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-40">
            <SelectValue placeholder="Tous les statuts" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            <SelectItem value="active">Actif</SelectItem>
            <SelectItem value="inactive">Inactif</SelectItem>
            <SelectItem value="suspended">Suspendu</SelectItem>
          </SelectContent>
        </Select>
      </GlassCard>

      {/* Table */}
      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Utilisateur</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction / Service</th>
                  <th className="px-5 py-3 text-left font-semibold">Rôle</th>
                  <th className="px-5 py-3 text-left font-semibold">Statut</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {paged.map((u) => {
                  const assignment = resolveAssignment(u.unit_id, u.direction_id);
                  const dir = directionsById.get(assignment.direction_id);
                  const department = departmentsById.get(assignment.department_id);
                  const unit = unitsById.get(assignment.unit_id);
                  return (
                    <tr key={u.id} className="border-t border-border/40 transition hover:bg-background/50">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full gradient-accent text-xs font-semibold text-white">
                            {initials(fullName(u))}
                          </span>
                          <div>
                            <div className="font-medium">{fullName(u)}</div>
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                            {u.matricule && (
                              <div className="text-xs text-muted-foreground font-mono">{u.matricule}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-muted-foreground">
                        <div>{dir?.name ?? "—"}</div>
                        {department && (
                          <div className="text-xs">{department.name}</div>
                        )}
                        {unit && (
                          <div className="text-xs">{unit.name}</div>
                        )}
                        {u.job && <div className="text-xs opacity-70">{u.job}</div>}
                      </td>
                      <td className="px-5 py-3.5">
                        <span className="inline-flex h-8 w-40 items-center justify-center rounded-full bg-muted px-3 text-xs font-medium text-muted-foreground">
                          {roleLabels[u.role as Role] ?? u.role}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={cn(
                          "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
                          statusBadge[u.account_status] ?? "bg-muted text-muted-foreground",
                        )}>
                          {statusLabel[u.account_status] ?? u.account_status}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center justify-end gap-1">
                          <Button
                            size="icon"
                            variant="ghost"
                            title="Modifier"
                            className="h-8 w-8"
                            onClick={() => openEdit(u)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            size="icon"
                            variant="ghost"
                            title="Réinitialiser MDP"
                            className="h-8 w-8"
                            onClick={() => { setResetUser(u); setNewPassword(""); }}
                          >
                            <KeyRound className="h-3.5 w-3.5" />
                          </Button>
                          {u.account_status === "active" ? (
                            <Button
                              size="icon"
                              variant="ghost"
                              title="Désactiver"
                              className="h-8 w-8 text-amber-500 hover:text-amber-400"
                              onClick={() => deactivateMut.mutate(u.id)}
                              disabled={deactivateMut.isPending}
                            >
                              <UserX className="h-3.5 w-3.5" />
                            </Button>
                          ) : (
                            <Button
                              size="icon"
                              variant="ghost"
                              title="Activer"
                              className="h-8 w-8 text-success hover:text-success"
                              onClick={() => activateMut.mutate(u.id)}
                              disabled={activateMut.isPending}
                            >
                              <UserCheck className="h-3.5 w-3.5" />
                            </Button>
                          )}
                          {isAdmin && (
                            <Button
                              size="icon"
                              variant="ghost"
                              title="Supprimer"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              onClick={() => setDeleteTarget(u)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {paged.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                      Aucun utilisateur trouvé.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      <PaginationBar
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
        onChange={setPage}
        onPageSizeChange={setPageSize}
      />

      {/* ── Dialog Créer ─────────────────────────────────────────────────────── */}
      <Dialog open={createOpen} onOpenChange={(o) => !o && setCreateOpen(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Créer un utilisateur</DialogTitle>
          </DialogHeader>
          <UserForm
            form={form}
            setForm={setForm}
            directions={activeDirections}
            departments={departments}
            units={units}
            showEmail
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              onClick={submitCreate}
              disabled={!isCreateValid || createMut.isPending}
              title={createValidation ?? undefined}
            >
              {createMut.isPending ? "Création…" : "Créer le compte"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog Modifier ───────────────────────────────────────────────────── */}
      <Dialog open={!!editUser} onOpenChange={(o) => !o && setEditUser(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Modifier — {fullName(editUser)}</DialogTitle>
          </DialogHeader>
          <UserForm
            form={form}
            setForm={setForm}
            directions={activeDirections}
            departments={departments}
            units={units}
            showEmail={false}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditUser(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              onClick={submitEdit}
              disabled={!!editValidation || updateMut.isPending}
              title={editValidation ?? undefined}
            >
              {updateMut.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog Reset MDP ─────────────────────────────────────────────────── */}
      <Dialog open={!!resetUser} onOpenChange={(o) => !o && setResetUser(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Réinitialiser le mot de passe</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Définir un nouveau mot de passe pour <strong>{fullName(resetUser)}</strong>.
          </p>
          <div className="space-y-2">
            <Label>Nouveau mot de passe</Label>
            <Input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              placeholder="Minimum 8 caractères"
              autoComplete="new-password"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResetUser(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={newPassword.length < 8 || resetMut.isPending}
              onClick={() => resetUser && resetMut.mutate({ id: resetUser.id, pwd: newPassword })}
            >
              {resetMut.isPending ? "Réinitialisation…" : "Confirmer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Confirm Suppression ───────────────────────────────────────────────── */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce compte ?</AlertDialogTitle>
            <AlertDialogDescription>
              L'action est irréversible. Le compte de <strong>{fullName(deleteTarget)}</strong> sera
              définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Suppression…" : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* ── Action rapide flottante : Nouvel utilisateur (visible apres scroll) ── */}
      <AnimatePresence>
        {isAdmin && showQuickCreate && (
          <motion.button
            className="fixed bottom-36 right-5 z-40 md:bottom-24 md:right-6 grid h-11 w-11 place-items-center rounded-full gradient-primary text-primary-foreground shadow-lg shadow-primary/40 hover:scale-110 transition-transform duration-150"
            initial={{ opacity: 0, scale: 0.3, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.3, y: 24 }}
            transition={{ type: "spring", stiffness: 380, damping: 18 }}
            onClick={openCreate}
            title="Nouvel utilisateur"
            aria-label="Nouvel utilisateur"
          >
            <Plus className="h-5 w-5" />
          </motion.button>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Sous-composant formulaire ─────────────────────────────────────────────────

function UserForm({
  form,
  setForm,
  directions,
  departments,
  units,
  showEmail,
}: {
  form: FormData;
  setForm: (f: FormData) => void;
  directions: Direction[];
  departments: Department[];
  units: Unit[];
  showEmail: boolean;
}) {
  const target = orgTargetForRole(form.role);
  const requiresDepartment = target === "department" || target === "unit";
  const requiresUnit = target === "unit";

  function field(key: keyof FormData, value: string | boolean) {
    setForm({ ...form, [key]: value });
  }

  function onRoleChange(value: string) {
    const role = value as Role;
    const nextTarget = orgTargetForRole(role);
    setForm({
      ...form,
      role,
      department_id: nextTarget === "department" || nextTarget === "unit" ? form.department_id : "",
      unit_id: nextTarget === "unit" ? form.unit_id : "",
    });
  }

  function onDirectionChange(value: string) {
    setForm({
      ...form,
      direction_id: value === "__none__" ? "" : value,
      department_id: "",
      unit_id: "",
    });
  }

  function onDepartmentChange(value: string) {
    setForm({
      ...form,
      department_id: value === "__none__" ? "" : value,
      unit_id: "",
    });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Prénom</Label>
          <Input value={form.firstname} onChange={(e) => field("firstname", e.target.value)} placeholder="Prénom" />
        </div>
        <div className="space-y-1.5">
          <Label>Nom de famille <span className="text-destructive">*</span></Label>
          <Input value={form.name} onChange={(e) => field("name", e.target.value)} placeholder="Nom" />
        </div>
        {showEmail && (
          <div className="space-y-1.5">
            <Label>Email <span className="text-destructive">*</span></Label>
            <Input type="email" value={form.email} onChange={(e) => field("email", e.target.value)} placeholder="adresse@edg.gn" />
          </div>
        )}
        {showEmail && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Mot de passe <span className="text-destructive">*</span></Label>
            <Input
              type="password"
              value={form.password}
              onChange={(e) => field("password", e.target.value)}
              placeholder="Min. 8 caractères"
              autoComplete="new-password"
            />
            {form.password.length > 0 && form.password.length < 8 ? (
              <p className="text-[11px] text-destructive">
                Le mot de passe doit contenir au moins 8 caractères.
              </p>
            ) : (
              <p className="text-[11px] text-muted-foreground">
                L'utilisateur pourra le modifier après sa première connexion.
              </p>
            )}
          </div>
        )}
        <div className="space-y-1.5">
          <Label>Matricule</Label>
          <Input value={form.matricule} onChange={(e) => field("matricule", e.target.value)} placeholder="EDG-0000" />
        </div>
        <div className="space-y-1.5">
          <Label>Poste / Fonction</Label>
          <Input value={form.job} onChange={(e) => field("job", e.target.value)} placeholder="Ex. Technicien réseau" />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Rôle <span className="text-destructive">*</span></Label>
          <Select value={form.role} onValueChange={onRoleChange}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {USER_FORM_ROLE_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Direction <span className="text-destructive">*</span></Label>
          <Select
            value={form.direction_id || "__none__"}
            onValueChange={onDirectionChange}
          >
            <SelectTrigger><SelectValue placeholder="Sélectionner une direction" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">Sélectionner une direction</SelectItem>
              {directions.map((d) => (
                <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          {!form.direction_id && (
            <p className="text-[11px] text-muted-foreground">
              Obligatoire pour le rôle sélectionné.
            </p>
          )}
        </div>
        {requiresDepartment && (
          <div className="space-y-1.5">
            <Label>Département <span className="text-destructive">*</span></Label>
            <Select
              value={form.department_id || "__none__"}
              onValueChange={onDepartmentChange}
              disabled={!form.direction_id}
            >
              <SelectTrigger>
                <SelectValue placeholder={form.direction_id ? "Sélectionner un département" : "Choisissez d'abord une direction"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Sélectionner un département</SelectItem>
                {departments.map((department) => (
                  <SelectItem key={department.id} value={department.id}>{department.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.direction_id && !form.department_id && (
              <p className="text-[11px] text-muted-foreground">
                Le département doit appartenir à la direction sélectionnée.
              </p>
            )}
          </div>
        )}
        {requiresUnit && (
          <div className="space-y-1.5">
            <Label>Service / Unité <span className="text-destructive">*</span></Label>
            <Select
              value={form.unit_id || "__none__"}
              onValueChange={(v) => field("unit_id", v === "__none__" ? "" : v)}
              disabled={!form.department_id}
            >
              <SelectTrigger>
                <SelectValue placeholder={form.department_id ? "Sélectionner un service ou une unité" : "Choisissez d'abord un département"} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">Sélectionner un service ou une unité</SelectItem>
                {units.map((u) => (
                  <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.department_id && !form.unit_id && (
              <p className="text-[11px] text-muted-foreground">
                Le service ou l'unité doit appartenir au département sélectionné.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
