import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  priorityColorMap,
} from "@/lib/mock-data";
import type { PriorityDefinition, PriorityColor } from "@/lib/mock-data";
import { toast } from "sonner";
import {
  Flag,
  Plus,
  Edit3,
  Trash2,
  GripVertical,
  ShieldAlert,
  CheckCircle2,
  ChevronUp,
  ChevronDown,
  Loader2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchPriorityDefs,
  createPriorityDef,
  updatePriorityDef,
  reorderPriorityDefs,
  deletePriorityDef,
} from "@/lib/api/admin-config";

export const Route = createFileRoute("/app/admin/priorities")({
  head: () => ({ meta: [{ title: "Niveaux de priorité — Admin EDG" }] }),
  component: PrioritiesAdminPage,
});

const COLOR_OPTIONS: PriorityColor[] = [
  "slate",
  "blue",
  "teal",
  "amber",
  "orange",
  "red",
  "purple",
];

function emptyPriority(): PriorityDefinition {
  return {
    id: "new",
    slug: "",
    label: "",
    description: "",
    color: "blue",
    order: 99,
    active: true,
    isBuiltin: false,
  };
}

function PriorityBadge({ def }: { def: PriorityDefinition }) {
  const tone = priorityColorMap[def.color];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
        tone.badge,
      )}
    >
      <span className={cn("h-1.5 w-1.5 rounded-full", tone.dot)} />
      {def.label}
    </span>
  );
}

function PrioritiesAdminPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<PriorityDefinition | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<PriorityDefinition | null>(null);
  const [slugError, setSlugError] = useState("");

  const { data: rawList = [], isLoading } = useQuery({
    queryKey: ["admin", "priorities"],
    queryFn: fetchPriorityDefs,
  });

  const list = [...rawList].sort((a, b) => a.order - b.order);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "priorities"] });

  const createMut = useMutation({
    mutationFn: (p: PriorityDefinition) => createPriorityDef(p),
    onSuccess: () => { invalidate(); },
    onError: () => toast.error("Erreur lors de la création"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, p }: { id: string; p: Partial<PriorityDefinition> }) =>
      updatePriorityDef(id, p),
    onSuccess: () => { invalidate(); },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });

  const reorderMut = useMutation({
    mutationFn: (ids: string[]) => reorderPriorityDefs(ids),
    onSuccess: () => invalidate(),
    onError: () => toast.error("Erreur lors du réordonnancement"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deletePriorityDef(id),
    onSuccess: () => { invalidate(); },
    onError: (err: Error) => toast.error(err.message || "Erreur lors de la suppression"),
  });

  const moveUp = (id: string) => {
    const idx = list.findIndex((p) => p.id === id);
    if (idx <= 0) return;
    const newOrder = [...list];
    [newOrder[idx - 1], newOrder[idx]] = [newOrder[idx], newOrder[idx - 1]];
    reorderMut.mutate(newOrder.map((p) => p.id));
  };

  const moveDown = (id: string) => {
    const idx = list.findIndex((p) => p.id === id);
    if (idx >= list.length - 1) return;
    const newOrder = [...list];
    [newOrder[idx], newOrder[idx + 1]] = [newOrder[idx + 1], newOrder[idx]];
    reorderMut.mutate(newOrder.map((p) => p.id));
  };

  const openCreate = () => {
    setEditing(emptyPriority());
    setSlugError("");
    setDialogOpen(true);
  };
  const openEdit = (p: PriorityDefinition) => {
    setEditing({ ...p });
    setSlugError("");
    setDialogOpen(true);
  };

  const validate = (e: PriorityDefinition): boolean => {
    if (!e.label.trim()) {
      toast.error("Le libellé est requis");
      return false;
    }
    if (!e.slug.trim()) {
      setSlugError("L'identifiant est requis");
      return false;
    }
    if (!/^[a-z0-9_-]+$/.test(e.slug)) {
      setSlugError("Minuscules, chiffres, tirets uniquement");
      return false;
    }
    const duplicate = list.find((p) => p.slug === e.slug && p.id !== e.id);
    if (duplicate) {
      setSlugError("Cet identifiant est déjà utilisé");
      return false;
    }
    return true;
  };

  const save = () => {
    if (!editing) return;
    if (!validate(editing)) return;

    if (editing.id === "new") {
      createMut.mutate(editing, {
        onSuccess: () => {
          toast.success(`Priorité « ${editing.label} » créée`);
          setDialogOpen(false);
          setEditing(null);
        },
      });
    } else {
      updateMut.mutate(
        { id: editing.id, p: { label: editing.label, description: editing.description, color: editing.color, order: editing.order, active: editing.active } },
        {
          onSuccess: () => {
            toast.success(`Priorité « ${editing.label} » mise à jour`);
            setDialogOpen(false);
            setEditing(null);
          },
        },
      );
    }
  };

  const toggle = (p: PriorityDefinition) => {
    updateMut.mutate({ id: p.id, p: { active: !p.active } });
  };

  const confirmDelete = (p: PriorityDefinition) => {
    if (p.isBuiltin) {
      toast.error("Les priorités intégrées ne peuvent pas être supprimées");
      return;
    }
    setDeleteTarget(p);
  };

  const remove = () => {
    if (!deleteTarget) return;
    deleteMut.mutate(deleteTarget.id, {
      onSuccess: () => {
        toast.success(`Priorité « ${deleteTarget.label} » supprimée`);
        setDeleteTarget(null);
      },
    });
  };

  const saving = createMut.isPending || updateMut.isPending;
  const activeCount = list.filter((p) => p.active).length;
  const customCount = list.filter((p) => !p.isBuiltin).length;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Flag className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Niveaux de priorité
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Créez, modifiez et organisez les niveaux de priorité applicables aux demandes.
          </p>
        </div>
        <Button
          onClick={openCreate}
          className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30"
        >
          <Plus className="mr-1 h-4 w-4" /> Nouveau niveau
        </Button>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl gradient-primary text-background">
            <Flag className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{list.length}</div>
            <div className="text-xs text-muted-foreground">Niveaux définis</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-success/15 text-success">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{activeCount}</div>
            <div className="text-xs text-muted-foreground">Actifs</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-info/15 text-info">
            <ShieldAlert className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{customCount}</div>
            <div className="text-xs text-muted-foreground">Personnalisés</div>
          </div>
        </GlassCard>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <GlassCard className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-center font-semibold">Rang</th>
                  <th className="px-5 py-3 text-left font-semibold">Priorité</th>
                  <th className="px-5 py-3 text-left font-semibold">Identifiant</th>
                  <th className="px-5 py-3 text-left font-semibold">Description</th>
                  <th className="px-5 py-3 text-center font-semibold">Active</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.map((p, idx) => (
                  <tr
                    key={p.id}
                    className={cn(
                      "border-t border-border/40 transition hover:bg-card/40",
                      !p.active && "opacity-50",
                    )}
                  >
                    <td className="px-4 py-3">
                      <div className="flex flex-col items-center gap-0.5">
                        <button
                          onClick={() => moveUp(p.id)}
                          disabled={idx === 0}
                          className="rounded p-0.5 text-muted-foreground transition hover:text-foreground disabled:opacity-20"
                          title="Monter"
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </button>
                        <span className="w-6 text-center text-xs font-mono font-bold text-muted-foreground">
                          {p.order}
                        </span>
                        <button
                          onClick={() => moveDown(p.id)}
                          disabled={idx === list.length - 1}
                          className="rounded p-0.5 text-muted-foreground transition hover:text-foreground disabled:opacity-20"
                          title="Descendre"
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>

                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <PriorityBadge def={p} />
                        {p.isBuiltin && (
                          <span className="rounded-full bg-muted px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground">
                            INTÉGRÉ
                          </span>
                        )}
                      </div>
                    </td>

                    <td className="px-5 py-3.5">
                      <code className="rounded bg-muted/60 px-1.5 py-0.5 font-mono text-xs">
                        {p.slug}
                      </code>
                    </td>

                    <td className="max-w-[260px] px-5 py-3.5 text-muted-foreground">
                      <span className="line-clamp-2 text-xs">{p.description || "—"}</span>
                    </td>

                    <td className="px-5 py-3.5 text-center">
                      <Switch checked={p.active} onCheckedChange={() => toggle(p)} />
                    </td>

                    <td className="px-5 py-3.5 text-right">
                      <div className="flex justify-end gap-1.5">
                        <Button
                          size="sm"
                          variant="ghost"
                          className="rounded-full"
                          onClick={() => openEdit(p)}
                          title="Modifier"
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className={cn(
                            "rounded-full",
                            p.isBuiltin
                              ? "cursor-not-allowed opacity-30"
                              : "text-destructive hover:bg-destructive/10",
                          )}
                          onClick={() => confirmDelete(p)}
                          title={
                            p.isBuiltin
                              ? "Priorité intégrée — non supprimable"
                              : "Supprimer"
                          }
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex items-center gap-2 border-t border-border/30 px-5 py-3 text-xs text-muted-foreground">
            <GripVertical className="h-3.5 w-3.5 shrink-0" />
            Utilisez les flèches pour réordonner les niveaux — l'ordre définit la gravité croissante.
          </div>
        </GlassCard>
      )}

      <Dialog open={dialogOpen} onOpenChange={(o) => { if (!o) { setDialogOpen(false); setEditing(null); } }}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Flag className="h-4 w-4 text-primary" />
              {editing?.id === "new" ? "Nouveau niveau de priorité" : "Modifier le niveau"}
            </DialogTitle>
          </DialogHeader>

          {editing && (
            <div className="space-y-4 py-2">
              <div className="grid gap-2">
                <Label>
                  Libellé <span className="text-destructive">*</span>
                </Label>
                <Input
                  value={editing.label}
                  onChange={(e) => setEditing({ ...editing, label: e.target.value })}
                  placeholder="Ex. Urgent"
                />
              </div>

              <div className="grid gap-2">
                <Label>
                  Identifiant technique <span className="text-destructive">*</span>
                  <span className="ml-1.5 font-normal text-muted-foreground">
                    (minuscules, chiffres, tirets)
                  </span>
                </Label>
                <Input
                  value={editing.slug}
                  disabled={editing.isBuiltin}
                  onChange={(e) => {
                    setSlugError("");
                    setEditing({ ...editing, slug: e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, "") });
                  }}
                  placeholder="Ex. urgent"
                  className={cn(slugError && "border-destructive focus-visible:ring-destructive")}
                />
                {slugError && (
                  <p className="text-xs text-destructive">{slugError}</p>
                )}
                {editing.isBuiltin && (
                  <p className="text-xs text-muted-foreground">
                    L'identifiant d'une priorité intégrée ne peut pas être modifié.
                  </p>
                )}
              </div>

              <div className="grid gap-2">
                <Label>Couleur</Label>
                <div className="flex flex-wrap gap-2">
                  {COLOR_OPTIONS.map((c) => {
                    const tone = priorityColorMap[c];
                    return (
                      <button
                        key={c}
                        type="button"
                        onClick={() => setEditing({ ...editing, color: c })}
                        className={cn(
                          "flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ring-2 transition",
                          tone.badge,
                          editing.color === c
                            ? "ring-primary"
                            : "ring-transparent hover:ring-border",
                        )}
                      >
                        <span className={cn("h-2 w-2 rounded-full", tone.dot)} />
                        {tone.label}
                      </button>
                    );
                  })}
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                  Aperçu :
                  <PriorityBadge
                    def={{ ...editing, label: editing.label || "Aperçu" }}
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label>Description</Label>
                <Textarea
                  rows={2}
                  value={editing.description}
                  onChange={(e) =>
                    setEditing({ ...editing, description: e.target.value })
                  }
                  placeholder="Expliquez brièvement quand utiliser ce niveau"
                />
              </div>

              <div className="flex items-center justify-between rounded-xl bg-card/60 p-3">
                <div>
                  <Label className="m-0">Actif</Label>
                  <p className="text-xs text-muted-foreground">
                    Disponible dans les formulaires de demande
                  </p>
                </div>
                <Switch
                  checked={editing.active}
                  onCheckedChange={(v) => setEditing({ ...editing, active: v })}
                />
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Annuler
            </Button>
            <Button className="gradient-primary text-background" onClick={save} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(o) => { if (!o) setDeleteTarget(null); }}
      >
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Supprimer ce niveau ?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Le niveau{" "}
            <strong>« {deleteTarget?.label} »</strong>{" "}
            <code className="rounded bg-muted/60 px-1 font-mono text-xs">
              {deleteTarget?.slug}
            </code>{" "}
            sera définitivement supprimé. Les demandes déjà enregistrées ne seront pas
            modifiées.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Annuler
            </Button>
            <Button variant="destructive" onClick={remove} disabled={deleteMut.isPending}>
              {deleteMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Supprimer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
