import { createFileRoute, Link, Outlet, useLocation } from "@tanstack/react-router";
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
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePagination, PaginationBar } from "@/components/pagination-bar";
import {
  fetchDirections,
  createDirection,
  updateDirection,
  deactivateDirection,
  activateDirection,
} from "@/lib/api/directions-units";
import type { Direction, OrgStatusFilter } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { CheckCircle2, Eye, Network, Pencil, Power, RotateCcw, Search, Plus } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/directions")({
  head: () => ({ meta: [{ title: "Directions - Admin EDG" }] }),
  component: AdminDirections,
});

type FormData = { name: string; code: string; description: string; parent_direction_id: string };
type StatusFilter = OrgStatusFilter;

const emptyForm = (): FormData => ({ name: "", code: "", description: "", parent_direction_id: "" });

function AdminDirections() {
  const location = useLocation();
  const pathname = location.pathname.replace(/\/$/, "");

  if (pathname !== "/app/admin/directions") {
    return <Outlet />;
  }

  return <AdminDirectionsList />;
}

function AdminDirectionsList() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Direction | null>(null);
  const [statusTarget, setStatusTarget] = useState<Direction | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm());

  const { data: directions = [], isLoading } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections({ status: "all" }),
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["directions"] });

  const createMut = useMutation({
    mutationFn: createDirection,
    onSuccess: () => { invalidate(); setCreateOpen(false); toast.success("Direction créée."); },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Parameters<typeof updateDirection>[1] }) =>
      updateDirection(id, data),
    onSuccess: () => { invalidate(); setEditTarget(null); toast.success("Direction mise à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const deactivateMut = useMutation({
    mutationFn: ({ id, force }: { id: string; force: boolean }) => deactivateDirection(id, force),
    onSuccess: () => { invalidate(); setStatusTarget(null); toast.success("Direction désactivée."); },
    onError: () => toast.error("Erreur lors de la désactivation."),
  });

  const activateMut = useMutation({
    mutationFn: activateDirection,
    onSuccess: () => { invalidate(); toast.success("Direction activée."); },
    onError: () => toast.error("Erreur lors de l'activation."),
  });

  const filtered = directions.filter((d) => {
    const matchStatus =
      statusFilter === "all" ||
      (statusFilter === "active" ? d.status : !d.status);
    const matchQ = `${d.name} ${d.code ?? ""}`.toLowerCase().includes(q.toLowerCase());
    return matchStatus && matchQ;
  });

  const { page, setPage, totalPages, paged: pagedItems, total, pageSize, setPageSize } = usePagination(filtered, 10);
  useEffect(() => { setPage(1); }, [q, setPage, statusFilter]);

  function openCreate() { setForm(emptyForm()); setCreateOpen(true); }
  function openEdit(d: Direction) {
    setForm({
      name: d.name,
      code: d.code ?? "",
      description: d.description ?? "",
      parent_direction_id: d.parent_direction_id ?? "",
    });
    setEditTarget(d);
  }

  function validate() {
    if (!form.name.trim()) { toast.error("Le nom est requis."); return false; }
    if (!form.code.trim()) { toast.error("Le code est requis."); return false; }
    if (editTarget && form.parent_direction_id === editTarget.id) {
      toast.error("Une direction ne peut pas être son propre parent.");
      return false;
    }
    return true;
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Network className="h-3 w-3" /> Organisation
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Directions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gérez les directions EDG, leurs rattachements et leur statut.
          </p>
        </div>
        <Button className="gradient-primary rounded-full" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> Nouvelle direction
        </Button>
      </header>

      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher une direction..."
            className="h-10 rounded-full pl-9"
          />
        </div>
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
        <span className="text-sm text-muted-foreground">{total} direction{total !== 1 ? "s" : ""}</span>
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Direction</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction parente</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-left font-semibold">Statut</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((d) => {
                  const parent = d.parent_direction_id
                    ? directions.find((p) => p.id === d.parent_direction_id)
                    : null;
                  return (
                    <tr key={d.id} className={cn("border-t border-border/40 transition hover:bg-background/50", !d.status && "opacity-70")}>
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-3">
                          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg gradient-primary text-xs font-bold text-white">
                            {d.name.slice(0, 2).toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <span className="block truncate font-medium">{d.name}</span>
                            <span className="text-xs text-muted-foreground">
                              {d.active_children_count ?? 0} enfant{(d.active_children_count ?? 0) > 1 ? "s" : ""} actif{(d.active_children_count ?? 0) > 1 ? "s" : ""}
                            </span>
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-4">
                        {parent ? (
                          <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                            {parent.name}
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground">Racine</span>
                        )}
                      </td>
                      <td className="px-5 py-4 font-mono text-muted-foreground">{d.code ?? "-"}</td>
                      <td className="px-5 py-4">
                        <StatusBadge active={d.status} />
                      </td>
                      <td className="px-5 py-4">
                        <div className="flex justify-end gap-1">
                          <Button asChild size="icon" variant="ghost" className="h-8 w-8" aria-label="Voir">
                            <Link to={`/app/admin/directions/${d.id}` as never}>
                              <Eye className="h-3.5 w-3.5" />
                            </Link>
                          </Button>
                          <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(d)} aria-label="Modifier">
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          {d.status ? (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-amber-500 hover:text-amber-500"
                              onClick={() => setStatusTarget(d)}
                              aria-label="Désactiver"
                            >
                              <Power className="h-3.5 w-3.5" />
                            </Button>
                          ) : (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-emerald-500 hover:text-emerald-500"
                              onClick={() => activateMut.mutate(d.id)}
                              disabled={activateMut.isPending}
                              aria-label="Activer"
                            >
                              <RotateCcw className="h-3.5 w-3.5" />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
                {pagedItems.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-12 text-center text-sm text-muted-foreground">
                      Aucune direction trouvée.
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

      <Dialog open={createOpen} onOpenChange={(o) => !o && setCreateOpen(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Nouvelle direction</DialogTitle></DialogHeader>
          <DirectionForm form={form} setForm={setForm} directions={directions.filter((d) => d.status)} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={createMut.isPending}
              onClick={() => validate() && createMut.mutate({
                name: form.name.trim(),
                code: form.code.trim(),
                description: form.description.trim() || undefined,
                parent_direction_id: form.parent_direction_id || undefined,
              })}
            >
              {createMut.isPending ? "Création..." : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Modifier - {editTarget?.name}</DialogTitle></DialogHeader>
          <DirectionForm
            form={form}
            setForm={setForm}
            directions={directions.filter((d) => d.status)}
            currentId={editTarget?.id}
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
                  description: form.description.trim() || undefined,
                  parent_direction_id: form.parent_direction_id || null,
                },
              })}
            >
              {updateMut.isPending ? "Enregistrement..." : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!statusTarget} onOpenChange={(o) => !o && setStatusTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Désactiver cette direction ?</AlertDialogTitle>
            <AlertDialogDescription>
              La direction <strong>{statusTarget?.name}</strong> restera visible avec le statut Inactif.
              {(statusTarget?.active_children_count ?? 0) > 0 && (
                <> Elle possède {statusTarget?.active_children_count} enfant(s) actif(s), qui seront également désactivés après confirmation.</>
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

function DirectionForm({
  form,
  setForm,
  directions,
  currentId,
}: {
  form: FormData;
  setForm: (f: FormData) => void;
  directions: Direction[];
  currentId?: string;
}) {
  const allowedParents = directions.filter((d) => d.id !== currentId);

  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Nom <span className="text-destructive">*</span></Label>
        <Input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Ex. Direction Technique"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Code <span className="text-destructive">*</span></Label>
        <Input
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
          placeholder="Ex. DT"
          className="uppercase"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Description</Label>
        <Input
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="Description optionnelle"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Direction parente</Label>
        <Select
          value={form.parent_direction_id || "__none__"}
          onValueChange={(v) => setForm({ ...form, parent_direction_id: v === "__none__" ? "" : v })}
        >
          <SelectTrigger>
            <SelectValue placeholder="Aucune direction parente" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">Aucune direction parente</SelectItem>
            {allowedParents.map((d) => (
              <SelectItem key={d.id} value={d.id}>
                {d.name}
                {d.code ? ` (${d.code})` : ""}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  );
}
