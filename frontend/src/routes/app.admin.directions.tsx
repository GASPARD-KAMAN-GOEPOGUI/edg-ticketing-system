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
  createDirection,
  updateDirection,
  deleteDirection,
} from "@/lib/api/directions-units";
import type { Direction } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { Network, Plus, Pencil, Trash2, Search } from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/directions")({
  head: () => ({ meta: [{ title: "Directions — Admin EDG" }] }),
  component: AdminDirections,
});

type FormData = { name: string; code: string; description: string; parent_direction_id: string };
const emptyForm = (): FormData => ({ name: "", code: "", description: "", parent_direction_id: "" });

function AdminDirections() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Direction | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Direction | null>(null);
  const [form, setForm] = useState<FormData>(emptyForm());

  const { data: directions = [], isLoading } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
  });

  const invalidate = () => qc.invalidateQueries({ queryKey: ["directions"] });

  const createMut = useMutation({
    mutationFn: createDirection,
    onSuccess: () => { invalidate(); setCreateOpen(false); toast.success("Direction créée."); },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FormData> }) =>
      updateDirection(id, data),
    onSuccess: () => { invalidate(); setEditTarget(null); toast.success("Direction mise à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const deleteMut = useMutation({
    mutationFn: deleteDirection,
    onSuccess: () => { invalidate(); setDeleteTarget(null); toast.success("Direction supprimée."); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  const filtered = directions.filter((d) =>
    `${d.name} ${d.code ?? ""}`.toLowerCase().includes(q.toLowerCase()),
  );

  const { page, setPage, totalPages, paged: pagedItems, total, pageSize, setPageSize } = usePagination(filtered, 10);
  useEffect(() => { setPage(1); }, [q]);

  function openCreate() { setForm(emptyForm()); setCreateOpen(true); }
  function openEdit(d: Direction) { setForm({ name: d.name, code: d.code ?? "", description: d.description ?? "", parent_direction_id: d.parent_direction_id ?? "" }); setEditTarget(d); }

  function validate() {
    if (!form.name.trim()) { toast.error("Le nom est requis."); return false; }
    if (!form.code.trim()) { toast.error("Le code est requis."); return false; }
    return true;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Network className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Directions</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Gérez les directions et départements de l'organisation EDG.
          </p>
        </div>
        <Button className="gradient-primary rounded-full" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> Nouvelle direction
        </Button>
      </header>

      <GlassCard className="flex items-center gap-3 p-4">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher une direction…"
            className="h-10 rounded-full pl-9"
          />
        </div>
        <span className="text-sm text-muted-foreground">{total} direction{total !== 1 ? "s" : ""}</span>
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        {isLoading ? (
          <div className="py-16 text-center text-sm text-muted-foreground">Chargement…</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Direction</th>
                  <th className="px-5 py-3 text-left font-semibold">Direction parente</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((d) => {
                  const parent = d.parent_direction_id
                    ? directions.find((p) => p.id === d.parent_direction_id)
                    : null;
                  return (
                  <tr key={d.id} className="border-t border-border/40 transition hover:bg-background/50">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-3">
                        <span className={cn(
                          "grid h-9 w-9 shrink-0 place-items-center rounded-lg gradient-primary text-xs font-bold text-white",
                        )}>
                          {d.name.slice(0, 2).toUpperCase()}
                        </span>
                        <span className="font-medium">{d.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      {parent ? (
                        <span className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary">
                          {parent.name}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-5 py-4 font-mono text-muted-foreground">{d.code ?? "—"}</td>
                    <td className="px-5 py-4">
                      <div className="flex justify-end gap-1">
                        <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(d)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-8 w-8 text-destructive hover:text-destructive"
                          onClick={() => setDeleteTarget(d)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                  );
                })}
                {pagedItems.length === 0 && (
                  <tr>
                    <td colSpan={4} className="py-12 text-center text-sm text-muted-foreground">
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

      {/* Create */}
      <Dialog open={createOpen} onOpenChange={(o) => !o && setCreateOpen(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader><DialogTitle>Nouvelle direction</DialogTitle></DialogHeader>
          <DirectionForm form={form} setForm={setForm} directions={directions} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={createMut.isPending}
              onClick={() => validate() && createMut.mutate({ name: form.name.trim(), code: form.code.trim(), description: form.description.trim() || undefined, parent_direction_id: form.parent_direction_id || undefined })}
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
          <DirectionForm form={form} setForm={setForm} directions={directions} currentId={editTarget?.id} />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditTarget(null)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={updateMut.isPending}
              onClick={() => editTarget && validate() && updateMut.mutate({ id: editTarget.id, data: { name: form.name.trim(), code: form.code.trim(), description: form.description.trim() || undefined, parent_direction_id: form.parent_direction_id || null } })}
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
            <AlertDialogTitle>Supprimer cette direction ?</AlertDialogTitle>
            <AlertDialogDescription>
              La direction <strong>{deleteTarget?.name}</strong> sera définitivement supprimée.
              Les utilisateurs rattachés n'auront plus de direction assignée.
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
            <SelectValue placeholder="— Aucune (direction racine) —" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="__none__">— Aucune (direction racine) —</SelectItem>
            {directions
              .filter((d) => d.id !== currentId)
              .map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.name}
                  {d.code ? ` (${d.code})` : ""}
                </SelectItem>
              ))}
          </SelectContent>
        </Select>
        <p className="text-[11px] text-muted-foreground">
          Optionnel — rattache cette direction à une direction supérieure (ex : DSI → DG)
        </p>
      </div>
    </div>
  );
}
