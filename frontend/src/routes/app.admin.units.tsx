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
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePagination, PaginationBar } from "@/components/pagination-bar";
import {
  fetchDirections,
  fetchUnits,
  createUnit,
  updateUnit,
  deleteUnit,
} from "@/lib/api/directions-units";
import type { Unit, Direction } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { Layers, Plus, Pencil, Trash2, Search } from "lucide-react";

export const Route = createFileRoute("/app/admin/units")({
  head: () => ({ meta: [{ title: "Services & Unités — Admin EDG" }] }),
  component: AdminUnits,
});

type FormData = { name: string; code: string; direction_id: string; description: string };
const emptyForm = (): FormData => ({ name: "", code: "", direction_id: "", description: "" });

function AdminUnits() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [dirFilter, setDirFilter] = useState("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Unit | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Unit | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm());

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
  });

  const { data: units = [], isLoading } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
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

  const deleteMut = useMutation({
    mutationFn: deleteUnit,
    onSuccess: () => { invalidate(); setDeleteTarget(null); toast.success("Service supprimé."); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  const filtered = units.filter((u) => {
    const matchQ = !q || `${u.name} ${u.code ?? ""}`.toLowerCase().includes(q.toLowerCase());
    const matchDir = dirFilter === "all" || u.direction_id === dirFilter;
    return matchQ && matchDir;
  });

  const { page, setPage, totalPages, paged: pagedItems, total, pageSize, setPageSize } = usePagination(filtered, 10);
  useEffect(() => { setPage(1); }, [q, dirFilter]);

  function openCreate() { setForm(emptyForm()); setCreateOpen(true); }
  function openEdit(u: Unit) {
    setForm({ name: u.name, code: u.code ?? "", direction_id: u.direction_id ?? "", description: u.description ?? "" });
    setEditTarget(u);
  }
  function validate() {
    if (!form.name.trim()) { toast.error("Le nom est requis."); return false; }
    return true;
  }

  const dirMap = Object.fromEntries(directions.map((d) => [d.id, d.name]));

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Layers className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Services & Unités</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gérez les services et unités rattachés aux directions EDG.
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
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher un service…"
            className="h-10 rounded-full pl-9"
          />
        </div>
        <Select value={dirFilter} onValueChange={setDirFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-56">
            <SelectValue placeholder="Toutes les directions" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes les directions</SelectItem>
            {directions.map((d) => (
              <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-sm text-muted-foreground">{total} service{total !== 1 ? "s" : ""}</span>
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[580px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Service / Unité</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((u) => (
                  <tr key={u.id} className="border-t border-border/40 transition hover:bg-background/50">
                    <td className="px-5 py-4">
                      <span className="font-medium">{u.name}</span>
                      {u.description && (
                        <div className="text-xs text-muted-foreground">{u.description}</div>
                      )}
                    </td>
                    <td className="px-5 py-4 text-muted-foreground">
                      {u.direction_id ? dirMap[u.direction_id] ?? "—" : "—"}
                    </td>
                    <td className="px-5 py-4 font-mono text-muted-foreground">{u.code ?? "—"}</td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(u)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => setDeleteTarget(u)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
                {pagedItems.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-sm text-muted-foreground">
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

      {/* Create */}
      <Dialog open={createOpen} onOpenChange={(o) => !o && setCreateOpen(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Nouveau service</DialogTitle></DialogHeader>
          <UnitForm form={form} setForm={setForm} directions={directions} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={createMut.isPending}
              onClick={() => validate() && createMut.mutate({
                name: form.name.trim(),
                code: form.code.trim() || undefined,
                direction_id: form.direction_id || undefined,
                description: form.description.trim() || undefined,
              })}
            >
              {createMut.isPending ? "Création…" : "Créer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit */}
      <Dialog open={!!editTarget} onOpenChange={(o) => !o && setEditTarget(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Modifier — {editTarget?.name}</DialogTitle></DialogHeader>
          <UnitForm form={form} setForm={setForm} directions={directions} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={updateMut.isPending}
              onClick={() => editTarget && validate() && updateMut.mutate({
                id: editTarget.id,
                data: {
                  name: form.name.trim(),
                  code: form.code.trim() || undefined,
                  direction_id: form.direction_id || undefined,
                  description: form.description.trim() || undefined,
                },
              })}
            >
              {updateMut.isPending ? "Enregistrement…" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer ce service ?</AlertDialogTitle>
            <AlertDialogDescription>
              Le service <strong>{deleteTarget?.name}</strong> sera définitivement supprimé.
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

function UnitForm({
  form,
  setForm,
  directions,
}: {
  form: FormData;
  setForm: (f: FormData) => void;
  directions: Direction[];
}) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <Label>Nom <span className="text-destructive">*</span></Label>
        <Input
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
          placeholder="Ex. Service Réseau"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Code</Label>
        <Input
          value={form.code}
          onChange={(e) => setForm({ ...form, code: e.target.value.toUpperCase() })}
          placeholder="Ex. SR"
          className="uppercase"
        />
      </div>
      <div className="space-y-1.5">
        <Label>Direction</Label>
        <Select
          value={form.direction_id || "__none__"}
          onValueChange={(v) => setForm({ ...form, direction_id: v === "__none__" ? "" : v })}
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
      <div className="space-y-1.5">
        <Label>Description</Label>
        <Input
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          placeholder="Description optionnelle"
        />
      </div>
    </div>
  );
}
