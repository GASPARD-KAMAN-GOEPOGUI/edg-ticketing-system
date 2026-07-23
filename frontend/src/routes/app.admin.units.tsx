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
import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import {
  activateUnit,
  createUnit,
  deactivateUnit,
  fetchDepartments,
  fetchDirections,
  fetchUnits,
  updateUnit,
} from "@/lib/api/directions-units";
import type { Department, Direction, OrgStatusFilter, Unit } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { CheckCircle2, Eye, Layers, Pencil, Plus, Power, RotateCcw, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/units")({
  head: () => ({ meta: [{ title: "Services & Unités - Admin EDG" }] }),
  component: AdminUnits,
});

type FormData = { name: string; code: string; direction_id: string; department_id: string; description: string };
type StatusFilter = OrgStatusFilter;

const emptyForm = (): FormData => ({ name: "", code: "", direction_id: "", department_id: "", description: "" });

function AdminUnits() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [dirFilter, setDirFilter] = useState("all");
  const [departmentFilter, setDepartmentFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Unit | null>(null);
  const [viewTarget, setViewTarget] = useState<Unit | null>(null);
  const [statusTarget, setStatusTarget] = useState<Unit | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm());

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections({ status: "all" }),
  });

  const { data: departments = [] } = useQuery({
    queryKey: ["departments"],
    queryFn: () => fetchDepartments({ status: "all" }),
  });

  const { data: units = [], isLoading } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits({ status: "all" }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["units"] });

  const createMut = useMutation({
    mutationFn: createUnit,
    onSuccess: () => { invalidate(); setCreateOpen(false); toast.success("Service créé."); },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateUnit>[1] }) =>
      updateUnit(id, data),
    onSuccess: () => { invalidate(); setEditTarget(null); toast.success("Service mis à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const deactivateMut = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) => deactivateUnit(id, force),
    onSuccess: () => { invalidate(); setStatusTarget(null); toast.success("Service désactivé."); },
    onError: () => toast.error("Erreur lors de la désactivation."),
  });

  const activateMut = useMutation({
    mutationFn: activateUnit,
    onSuccess: () => { invalidate(); toast.success("Service activé."); },
    onError: () => toast.error("Erreur lors de l'activation."),
  });

  const directionMap = Object.fromEntries(directions.map((direction) => [direction.id, direction.name]));
  const departmentMap = Object.fromEntries(departments.map((department) => [department.id, department.name]));

  const departmentsForFilter = useMemo(() => {
    if (dirFilter === "all") return departments;
    return departments.filter((department) => department.direction_id === dirFilter);
  }, [departments, dirFilter]);

  const filtered = units.filter((unit) => {
    const matchQ = !q || `${unit.name} ${unit.code ?? ""}`.toLowerCase().includes(q.toLowerCase());
    const matchDir = dirFilter === "all" || unit.direction_id === dirFilter;
    const matchDepartment = departmentFilter === "all" || unit.department_id === departmentFilter;
    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "active" ? unit.status : !unit.status);
    return matchQ && matchDir && matchDepartment && matchStatus;
  });

  const { page, setPage, totalPages, paged: pagedItems, total, pageSize, setPageSize } = usePagination(filtered, 10);
  useEffect(() => { setPage(1); }, [departmentFilter, dirFilter, q, setPage, statusFilter]);

  function openCreate() { setForm(emptyForm()); setCreateOpen(true); }
  function openEdit(unit: Unit) {
    setForm({
      name: unit.name,
      code: unit.code ?? "",
      direction_id: unit.direction_id ?? "",
      department_id: unit.department_id ?? "",
      description: unit.description ?? "",
    });
    setEditTarget(unit);
  }
  function validate() {
    if (!form.name.trim()) { toast.error("Le nom est requis."); return false; }
    if (!form.code.trim()) { toast.error("Le code est requis."); return false; }
    if (!form.department_id) { toast.error("Le département est obligatoire."); return false; }
    return true;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Layers className="h-3 w-3" /> Organisation
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Services & Unités</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gérez les services et unités rattachés obligatoirement à un département.
          </p>
        </div>
        <Button className="gradient-primary rounded-full" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> Nouveau service
        </Button>
      </header>

      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(event) => setQ(event.target.value)}
            placeholder="Rechercher un service..."
            className="h-10 rounded-full pl-9"
          />
        </div>
        <Select
          value={dirFilter}
          onValueChange={(value) => { setDirFilter(value); setDepartmentFilter("all"); }}
        >
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
        <Select value={departmentFilter} onValueChange={setDepartmentFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-56">
            <SelectValue placeholder="Tous les départements" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Tous les départements</SelectItem>
            {departmentsForFilter.map((department) => (
              <SelectItem key={department.id} value={department.id}>{department.name}</SelectItem>
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
        <span className="text-sm text-muted-foreground">{total} service{total !== 1 ? "s" : ""}</span>
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Service / Unité</th>
                  <th className="px-5 py-3 text-left font-semibold">Département</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-left font-semibold">Statut</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((unit) => (
                  <tr key={unit.id} className={cn("border-t border-border/40 transition hover:bg-background/50", !unit.status && "opacity-70")}>
                    <td className="px-5 py-4">
                      <span className="font-medium">{unit.name}</span>
                      {unit.description && (
                        <div className="text-xs text-muted-foreground">{unit.description}</div>
                      )}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {unit.department_id ? departmentMap[unit.department_id] ?? unit.department_name ?? "-" : "Rattachement direct historique"}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {unit.direction_id ? directionMap[unit.direction_id] ?? unit.direction_name ?? "-" : "-"}
                    </td>
                    <td className="px-5 py-4 font-mono text-muted-foreground">{unit.code ?? "-"}</td>
                    <td className="px-5 py-4"><StatusBadge active={unit.status} /></td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => setViewTarget(unit)} aria-label="Voir">
                          <Eye className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(unit)} aria-label="Modifier">
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        {unit.status ? (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-amber-500 hover:text-amber-500"
                            onClick={() => setStatusTarget(unit)}
                            aria-label="Désactiver"
                          >
                            <Power className="h-3.5 w-3.5" />
                          </Button>
                        ) : (
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-8 w-8 text-emerald-500 hover:text-emerald-500"
                            onClick={() => activateMut.mutate(unit.id)}
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
                    <td colSpan={6} className="py-12 text-center text-sm text-muted-foreground">
                      Aucun service trouvé.
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
          <DialogHeader><DialogTitle>Nouveau service</DialogTitle></DialogHeader>
          <UnitForm
            form={form}
            setForm={setForm}
            directions={directions.filter((d) => d.status)}
            departments={departments.filter((d) => d.status)}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={createMut.isPending}
              onClick={() => validate() && createMut.mutate({
                name: form.name.trim(),
                code: form.code.trim(),
                department_id: form.department_id,
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
          <UnitForm
            form={form}
            setForm={setForm}
            directions={directions.filter((d) => d.status)}
            departments={departments.filter((d) => d.status)}
          />
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
                  department_id: form.department_id,
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
            <InfoLine label="Type" value="Service / Unité" />
            <InfoLine label="Direction" value={viewTarget?.direction_name ?? (viewTarget?.direction_id ? directionMap[viewTarget.direction_id] : undefined)} />
            <InfoLine label="Département" value={viewTarget?.department_name ?? (viewTarget?.department_id ? departmentMap[viewTarget.department_id] : "Rattachement direct historique")} />
            <InfoLine label="Code" value={viewTarget?.code} />
            <InfoLine label="Statut" value={viewTarget?.status ? "Actif" : "Inactif"} />
            <InfoLine label="Description" value={viewTarget?.description} />
          </div>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!statusTarget} onOpenChange={(open) => !open && setStatusTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver ce service ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le service <strong>{statusTarget?.name}</strong> restera visible avec le statut Inactif et pourra être réactivé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-amber-500 text-white hover:bg-amber-600"
              onClick={() => statusTarget && deactivateMut.mutate({ id: statusTarget.id, force: false })}
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

function UnitForm({
  form,
  setForm,
  directions,
  departments,
}: {
  form: FormData;
  setForm: (form: FormData) => void;
  directions: Direction[];
  departments: Department[];
}) {
  const departmentsForDirection = form.direction_id
    ? departments.filter((department) => department.direction_id === form.direction_id)
    : departments;

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Nom <span className="text-destructive">*</span></Label>
        <Input
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          placeholder="Ex. Service Réseau"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Code <span className="text-destructive">*</span></Label>
        <Input
          value={form.code}
          onChange={(event) => setForm({ ...form, code: event.target.value.toUpperCase() })}
          placeholder="Ex. SRC"
          className="uppercase"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Direction</Label>
        <Select
          value={form.direction_id || "__none__"}
          onValueChange={(value) => setForm({
            ...form,
            direction_id: value === "__none__" ? "" : value,
            department_id: "",
          })}
        >
          <SelectTrigger><SelectValue placeholder="Filtrer par direction" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">Choisir après par département</SelectItem>
            {directions.map((direction) => (
              <SelectItem key={direction.id} value={direction.id}>
                {direction.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <div className="space-y-1.5">
        <Label>Département <span className="text-destructive">*</span></Label>
        <Select
          value={form.department_id || "__none__"}
          onValueChange={(value) => {
            const department = departments.find((item) => item.id === value);
            setForm({
              ...form,
              department_id: value === "__none__" ? "" : value,
              direction_id: department?.direction_id ?? form.direction_id,
            });
          }}
        >
          <SelectTrigger><SelectValue placeholder="Sélectionner un département" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">Sélectionner un département</SelectItem>
            {departmentsForDirection.map((department) => (
              <SelectItem key={department.id} value={department.id}>
                {department.name}
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
