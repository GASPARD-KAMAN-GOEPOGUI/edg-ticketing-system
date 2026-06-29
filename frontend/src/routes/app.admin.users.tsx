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
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchUsers,
  createUser,
  updateUser,
  setUserRole,
  activateUser,
  deactivateUser,
  resetUserPassword,
  deleteUser,
} from "@/lib/api/accounts";
import type { AccountUser } from "@/lib/api/accounts";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Direction, Unit } from "@/lib/api/directions-units";
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
  ChevronDown,
} from "lucide-react";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/users")({
  head: () => ({ meta: [{ title: "Utilisateurs & Rôles — Admin EDG" }] }),
  component: AdminUsers,
});

const ROLES: Role[] = ["user", "agent", "chief", "director", "dg", "admin"];

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
  email: string;
  role: string;
  matricule: string;
  job: string;
  direction_id: string;
  unit_id: string;
  is_edg_employee: boolean;
  password: string;
};

const emptyForm = (): FormData => ({
  name: "",
  email: "",
  role: "user",
  matricule: "",
  job: "",
  direction_id: "",
  unit_id: "",
  is_edg_employee: true,
  password: "",
});

function initials(name: string) {
  return name.split(" ").map((p) => p[0]).join("").slice(0, 2).toUpperCase();
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
    queryKey: ["directions"],
    queryFn: fetchDirections,
  });
  const directions: Direction[] = directionsData ?? [];

  // Toutes les unités — pour dériver la direction depuis unit_id dans le tableau
  const { data: allUnitsData } = useQuery({
    queryKey: ["units", "all"],
    queryFn: () => fetchUnits(),
  });
  const allUnits: Unit[] = allUnitsData ?? [];

  // Unités filtrées par direction pour le formulaire d'édition/création
  const { data: unitsData } = useQuery({
    queryKey: ["units", form.direction_id || editUser?.direction_id],
    queryFn: () => fetchUnits(form.direction_id || editUser?.direction_id),
    enabled: !!(form.direction_id || editUser?.direction_id),
  });
  const units: Unit[] = unitsData ?? [];

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

  const roleMut = useMutation({
    mutationFn: ({ id, role }: { id: string; role: string }) => setUserRole(id, role),
    onSuccess: (_u, { role }) => {
      invalidate();
      toast.success(`Rôle mis à jour : ${roleLabels[role as Role] ?? role}`);
    },
    onError: () => toast.error("Impossible de mettre à jour le rôle."),
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
  function openCreate() {
    setForm(emptyForm());
    setCreateOpen(true);
  }

  function openEdit(u: AccountUser) {
    const userUnit = allUnits.find((un) => un.id === u.unit_id);
    const derivedDirId = userUnit?.direction_id ?? u.direction_id ?? "";
    setForm({
      name: u.name,
      email: u.email,
      role: u.role,
      matricule: u.matricule ?? "",
      job: u.job ?? "",
      direction_id: derivedDirId,
      unit_id: u.unit_id ?? "",
      password: "",
      is_edg_employee: true,
    });
    setEditUser(u);
  }

  function submitCreate() {
    if (!form.name.trim() || !form.email.trim()) {
      toast.error("Nom et email sont requis.");
      return;
    }
    if (!form.password || form.password.length < 8) {
      toast.error("Le mot de passe doit contenir au moins 8 caractères.");
      return;
    }
    createMut.mutate({
      data: {
        name: form.name.trim(),
        email: form.email.trim(),
        role: form.role,
        matricule: form.matricule || undefined,
        job: form.job || undefined,
        direction_id: form.direction_id || undefined,
        unit_id: form.unit_id || undefined,
        is_edg_employee: form.is_edg_employee,
      },
      password: form.password,
    });
  }

  function submitEdit() {
    if (!editUser) return;
    updateMut.mutate({
      id: editUser.id,
      data: {
        name: form.name.trim() || undefined,
        matricule: form.matricule || undefined,
        job: form.job || undefined,
        direction_id: form.direction_id || undefined,
        unit_id: form.unit_id || undefined,
      },
    });
    if (form.role && form.role !== editUser.role) {
      roleMut.mutate({ id: editUser.id, role: form.role });
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="mx-auto max-w-7xl space-y-6">
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
          { label: "Agents", value: list.filter((u) => u.role === "agent").length },
          { label: "Admins", value: list.filter((u) => u.role === "admin" || u.role === "dg").length },
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
                  const userUnit = allUnits.find((un) => un.id === u.unit_id);
                  const derivedDirId = userUnit?.direction_id ?? u.direction_id;
                  const dir = directions.find((d) => d.id === derivedDirId);
                  return (
                    <tr key={u.id} className="border-t border-border/40 transition hover:bg-background/50">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full gradient-accent text-xs font-semibold text-white">
                            {initials(u.name)}
                          </span>
                          <div>
                            <div className="font-medium">{u.name}</div>
                            <div className="text-xs text-muted-foreground">{u.email}</div>
                            {u.matricule && (
                              <div className="text-xs text-muted-foreground font-mono">{u.matricule}</div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5 text-sm text-muted-foreground">
                        <div>{dir?.name ?? "—"}</div>
                        {userUnit && dir && userUnit.id !== dir.id && (
                          <div className="text-xs">{userUnit.name}</div>
                        )}
                        {u.job && <div className="text-xs opacity-70">{u.job}</div>}
                      </td>
                      <td className="px-5 py-3.5">
                        <Select
                          value={u.role}
                          onValueChange={(v) => roleMut.mutate({ id: u.id, role: v })}
                          disabled={!isAdmin || roleMut.isPending}
                        >
                          <SelectTrigger className="h-8 w-40 rounded-full text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {ROLES.map((r) => (
                              <SelectItem key={r} value={r}>{roleLabels[r]}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
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
            directions={directions}
            units={units}
            showEmail
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              onClick={submitCreate}
              disabled={createMut.isPending}
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
            <DialogTitle>Modifier — {editUser?.name}</DialogTitle>
          </DialogHeader>
          <UserForm
            form={form}
            setForm={setForm}
            directions={directions}
            units={units}
            showEmail={false}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditUser(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              onClick={submitEdit}
              disabled={updateMut.isPending}
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
            Définir un nouveau mot de passe pour <strong>{resetUser?.name}</strong>.
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
              L'action est irréversible. Le compte de <strong>{deleteTarget?.name}</strong> sera
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
    </div>
  );
}

// ── Sous-composant formulaire ─────────────────────────────────────────────────

function UserForm({
  form,
  setForm,
  directions,
  units,
  showEmail,
}: {
  form: FormData;
  setForm: (f: FormData) => void;
  directions: Direction[];
  units: Unit[];
  showEmail: boolean;
}) {
  function field(key: keyof FormData, value: string | boolean) {
    setForm({ ...form, [key]: value });
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label>Nom complet <span className="text-destructive">*</span></Label>
          <Input value={form.name} onChange={(e) => field("name", e.target.value)} placeholder="Prénom Nom" />
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
            <p className="text-[11px] text-muted-foreground">
              L'utilisateur pourra le modifier après sa première connexion.
            </p>
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
          <Label>Rôle</Label>
          <Select value={form.role} onValueChange={(v) => field("role", v)}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {(["user", "agent", "chief", "director", "dg", "admin"] as Role[]).map((r) => (
                <SelectItem key={r} value={r}>{roleLabels[r]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <Label>Direction</Label>
          <Select
            value={form.direction_id || "__none__"}
            onValueChange={(v) => setForm({ ...form, direction_id: v === "__none__" ? "" : v, unit_id: "" })}
          >
            <SelectTrigger><SelectValue placeholder="Aucune" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="__none__">— Aucune —</SelectItem>
              {directions.map((d) => (
                <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {form.direction_id && (
          <div className="space-y-1.5 sm:col-span-2">
            <Label>Service / Unité</Label>
            <Select value={form.unit_id || "__none__"} onValueChange={(v) => field("unit_id", v === "__none__" ? "" : v)}>
              <SelectTrigger><SelectValue placeholder="Aucun" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none__">— Aucun —</SelectItem>
                {units.map((u) => (
                  <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
      </div>
    </div>
  );
}

// silence unused import warning
const _ChevronDown = ChevronDown;
