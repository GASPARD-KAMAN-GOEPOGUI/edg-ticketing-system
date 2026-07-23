import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import {
  activateDepartment,
  createDepartment,
  deactivateDepartment,
  fetchDepartments,
  fetchDirections,
  updateDepartment,
} from "@/lib/api/directions-units";
import type { Department, Direction, OrgStatusFilter } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { CheckCircle2, Eye, GitBranch, Pencil, Plus, Power, RotateCcw, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/departments")({
  head: () => ({ meta: [{ title: "Départements - Admin EDG" }] }),
  component: AdminDepartments,
});

type FormData = { name: string; code: string; direction_id: string; description: string };
type StatusFilter = OrgStatusFilter;

const emptyForm = (): FormData => ({ name: "", code: "", direction_id: "", description: "" });

function AdminDepartments() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [dirFilter, setDirFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Department | null>(null);
  const [viewTarget, setViewTarget] = useState<Department | null>(null);
  const [statusTarget, setStatusTarget] = useState<Department | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm());

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections({ status: "all" }),
  });

  const { data: departments = [], isLoading } = useQuery({
    queryKey: ["departments"],
    queryFn: () => fetchDepartments({ status: "all" }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["departments"] });

  const createMut = useMutation({
    mutationFn: createDepartment,
    onSuccess: () => { invalidate(); setCreateOpen(false); toast.success("Département créé."); },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateDepartment>[1] }) =>
      updateDepartment(id, data),
    onSuccess: () => { invalidate(); setEditTarget(null); toast.success("Département mis à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const deactivateMut = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) => deactivateDepartment(id, force),
    onSuccess: () => { invalidate(); setStatusTarget(null); toast.success("Département désactivé."); },
    onError: () => toast.error("Erreur lors de la désactivation."),
  });

  const activateMut = useMutation({
    mutationFn: activateDepartment,
    onSuccess: () => { invalidate(); toast.success("Département activé."); },
    onError: () => toast.error("Erreur lors de l'activation."),
  });

  const directionMap = Object.fromEntries(directions.map((d) => [d.id, d.name]));

  const filtered = departments.filter((department) => {
    const matchQ = !q || `${department.name} ${department.code ?? ""}`.toLowerCase().includes(q.toLowerCase());
    const matchDir = dirFilter === "all" || department.direction_id === dirFilter;
    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "active" ? department.status : !department.status);
    return matchQ && matchDir && matchStatus;
  });

  const { page, setPage, totalPages, paged: pagedItems, total, pageSize, setPageSize } = usePagination(filtered, 10);
  useEffect(() => { setPage(1); }, [q, dirFilter, setPage, statusFilter]);

  function openCreate() { setForm(emptyForm()); setCreateOpen(true); }
  function openEdit(department: Department) {
    setForm({
      name: department.name,
      code: department.code ?? "",
      direction_id: department.direction_id ?? "",
      description: department.description ?? "",
    });
    setEditTarget(department);
  }
  function validate() {
    if (!form.name.trim()) { toast.error("Le nom est requis."); return false; }
    if (!form.code.trim()) { toast.error("Le code est requis."); return false; }
    if (!form.direction_id) { toast.error("La direction est obligatoire."); return false; }
    return true;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <GitBranch className="h-3 w-3" /> Organisation
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Départements</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Structure intermédiaire entre une direction et ses services ou unités.
          </p>
        </div>
        <Button className="gradient-primary rounded-full" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> Nouveau département
        </Button>
      </header>

      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Rechercher un département..."
            className="h-10 rounded-full pl-9"
          />
        </div>
        <Select value={dirFilter} onValueChange={setDirFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-56">
            <SelectValue placeholder="Toutes les directions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes les directions</SelectItem>
            {directions.map((direction) => (
              <SelectItem key={direction.id} value={direction.id}>{direction.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value as StatusFilter)}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-44">
            <SelectValue placeholder="Statut" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les statuts</SelectItem>
            <SelectItem value="active">Actifs</SelectItem>
            <SelectItem value="inactive">Inactifs</SelectItem>
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{total} département{total !== 1 ? "s" : ""}</span>
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Département</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-left font-semibold">Statut</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((department) => (
                  <tr key={department.id} className={cn("border-t border-border/40 transition hover:bg-background/50", !department.status && "opacity-70")}>
                    <td className="px-5 py-4">
                      <div className="font-medium">{department.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {department.active_children_count ?? 0} service{(department.active_children_count ?? 0) > 1 ? "s" : ""} actif{(department.active_children_count ?? 0) > 1 ? "s" : ""}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {department.direction_id ? directionMap[department.direction_id] ?? department.direction_name ?? "-" : "-"}
                    </td>
                    <td className="px-5 py-4 font-mono text-muted-foreground">{department.code ?? "-"}</td>
                    <td className="px-5 py-4"><StatusBadge active={department.status} /></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setViewTarget(department)} aria-label="Voir">
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(department)} aria-label="Modifier">
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        {department.status ? (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-amber-500 hover:text-amber-500"
                            onClick={() => setStatusTarget(department)}
                            aria-label="Désactiver"
                          >
                            <Power className="h-3.5 w-3.5" />
                          </Button>
                        ) : (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-emerald-500 hover:text-emerald-500"
                            onClick={() => activateMut.mutate(department.id)}
                            disabled={activateMut.isPending}
                            aria-label="Activer"
                          >
                            <RotateCcw className="h-3.5 w-3.5" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
                {pagedItems.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                      Aucun département trouvé.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </GlassCard>

      <Dialog open={createOpen} onOpenChange={(open) => !open && setCreateOpen(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Nouveau département</DialogTitle></DialogHeader>
          <DepartmentForm form={form} setForm={setForm} directions={directions.filter((d) => d.status)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={createMut.isPending}
              onClick={() => validate() && createMut.mutate({
                name: form.name.trim(),
                code: form.code.trim(),
                direction_id: form.direction_id,
                description: form.description.trim() || undefined,
              })}
            >
              {createMut.isPending ? "Création..." : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editTarget} onOpenChange={(open) => !open && setEditTarget(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Modifier - {editTarget?.name}</DialogTitle></DialogHeader>
          <DepartmentForm form={form} setForm={setForm} directions={directions.filter((d) => d.status)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={updateMut.isPending}
              onClick={() => editTarget && validate() && updateMut.mutate({
                id: editTarget.id,
                data: {
                  name: form.name.trim(),
                  code: form.code.trim(),
                  direction_id: form.direction_id,
                  description: form.description.trim() || undefined,
                },
              })}
            >
              {updateMut.isPending ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!viewTarget} onOpenChange={(open) => !open && setViewTarget(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>{viewTarget?.name}</DialogTitle></DialogHeader>
          <div className="space-y-3 text-sm">
            <InfoLine label="Type" value="Département" />
            <InfoLine label="Direction" value={viewTarget?.direction_name ?? (viewTarget?.direction_id ? directionMap[viewTarget.direction_id] : undefined)} />
            <InfoLine label="Code" value={viewTarget?.code} />
            <InfoLine label="Statut" value={viewTarget?.status ? "Actif" : "Inactif"} />
            <InfoLine label="Services actifs" value={String(viewTarget?.active_children_count ?? 0)} />
            <InfoLine label="Description" value={viewTarget?.description} />
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!statusTarget} onOpenChange={(open) => !open && setStatusTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver ce département ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le département <strong>{statusTarget?.name}</strong> restera visible avec le statut Inactif.
              {(statusTarget?.active_children_count ?? 0) > 0 && (
                <> Ses services actifs seront également désactivés après confirmation.</>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-amber-500 text-white hover:bg-amber-600"
              onClick={() => statusTarget && deactivateMut.mutate({
                id: statusTarget.id,
                force: (statusTarget.active_children_count ?? 0) > 0,
              })}
              disabled={deactivateMut.isPending}
            >
              {deactivateMut.isPending ? "Désactivation..." : "Désactiver"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

function DepartmentForm({
  form,
  setForm,
  directions,
}: {
  form: FormData;
  setForm: (form: FormData) => void;
  directions: Direction[];
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Nom <span className="text-destructive">*</span></Label>
        <Input
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Ex. Département Exploitation"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Code <span className="text-destructive">*</span></Label>
        <Input
          value={form.code}
          onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          placeholder="Ex. DEX"
          className="uppercase"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Direction <span className="text-destructive">*</span></Label>
        <Select
          value={form.direction_id || "__none__"}
          onValueChange={(value) => setForm({ ...form, direction_id: value === "__none__" ? "" : value })}
        >
          <SelectTrigger><SelectValue placeholder="Sélectionner une direction" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">Sélectionner une direction</SelectItem>
            {directions.map((direction) => (
              <SelectItem key={direction.id} value={direction.id}>
                {direction.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Description</Label>
        <Input
          value={form.description}
          onChange={(event) => setForm({ ...form, description: event.target.value })}
          placeholder="Description optionnelle"
        />
      </div>
    </div>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium",
      active ? "bg-emerald-500/15 text-emerald-500" : "bg-muted text-muted-foreground",
    )}>
      <CheckCircle2 className="h-3 w-3" />
      {active ? "Actif" : "Inactif"}
    </span>
  );
}

function InfoLine({ label, value }: { label: string; value?: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-border/30 pb-2">
      <span className="text-muted-foreground">{label}</span>
      <span className="text-right font-medium">{value || "-"}</span>
    </div>
  );
}
