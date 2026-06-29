import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
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
import { Label } from "@/components/ui/label";
import type { RoutingRule } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Unit } from "@/lib/api/directions-units";
import { useState } from "react";
import { toast } from "sonner";
import {
  Route as RouteIcon,
  Plus,
  Trash2,
  Edit3,
  ArrowDown,
  ArrowUp,
  Zap,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LayoutToggle, LayoutMode } from "@/components/layout-toggle";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRoutingRules,
  createRoutingRule,
  updateRoutingRule,
  toggleRoutingRule,
  reorderRoutingRules,
  deleteRoutingRule,
} from "@/lib/api/admin-config";

export const Route = createFileRoute("/app/admin/routing")({
  head: () => ({ meta: [{ title: "Règles de routage — Admin EDG" }] }),
  component: RoutingAdminPage,
});

const fields: RoutingRule["conditionField"][] = ["category", "priority", "source", "keyword"];
const fieldLabels: Record<RoutingRule["conditionField"], string> = {
  category: "Catégorie",
  priority: "Priorité",
  source: "Canal source",
  keyword: "Mots-clés",
};

function emptyRule(order: number, defaultDirection = ""): RoutingRule {
  return {
    id: "new",
    name: "",
    conditionField: "category",
    conditionValue: "",
    targetDirection: defaultDirection,
    targetService: "",
    autoAssign: false,
    active: true,
    order,
  };
}

function RoutingAdminPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<RoutingRule | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [layout, setLayout] = useState<LayoutMode>("list");

  const { data: list = [], isLoading, isError } = useQuery({
    queryKey: ["admin", "routing"],
    queryFn: fetchRoutingRules,
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 300_000,
  });

  const { data: allUnits = [] } = useQuery<Unit[]>({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
    staleTime: 300_000,
  });

  const filteredUnits = editing?.targetDirection
    ? allUnits.filter((u) => u.direction_id === editing.targetDirection)
    : allUnits;

  const sorted = [...list].sort((a, b) => a.order - b.order);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "routing"] });

  const createMut = useMutation({
    mutationFn: (r: RoutingRule) => createRoutingRule(r),
    onSuccess: () => { invalidate(); toast.success("Règle créée"); },
    onError: () => toast.error("Erreur lors de la création"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, r }: { id: string; r: Partial<RoutingRule> }) => updateRoutingRule(id, r),
    onSuccess: () => { invalidate(); toast.success("Règle mise à jour"); },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });

  const toggleMut = useMutation({
    mutationFn: (id: string) => toggleRoutingRule(id),
    onSuccess: () => invalidate(),
    onError: () => toast.error("Erreur lors du basculement"),
  });

  const reorderMut = useMutation({
    mutationFn: (ids: string[]) => reorderRoutingRules(ids),
    onSuccess: () => invalidate(),
    onError: () => toast.error("Erreur lors du réordonnancement"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteRoutingRule(id),
    onSuccess: () => { invalidate(); toast.success("Règle supprimée"); },
    onError: () => toast.error("Erreur lors de la suppression"),
  });

  const openCreate = () => {
    setEditing(emptyRule(list.length + 1, directions[0]?.id ?? ""));
    setDialogOpen(true);
  };
  const openEdit = (r: RoutingRule) => {
    const unit = allUnits.find((u) => (u.code ?? String(u.id)) === r.targetService);
    setEditing({ ...r, targetDirection: unit?.direction_id ?? r.targetDirection ?? "" });
    setDialogOpen(true);
  };
  const save = () => {
    if (!editing) return;
    if (!editing.name.trim()) {
      toast.error("Le nom de la règle est requis");
      return;
    }
    if (editing.id === "new") {
      createMut.mutate(editing, {
        onSuccess: () => { setDialogOpen(false); setEditing(null); },
      });
    } else {
      updateMut.mutate({ id: editing.id, r: editing }, {
        onSuccess: () => { setDialogOpen(false); setEditing(null); },
      });
    }
  };
  const move = (id: string, dir: -1 | 1) => {
    const idx = sorted.findIndex((r) => r.id === id);
    const swap = sorted[idx + dir];
    if (!swap) return;
    const newOrder = [...sorted];
    [newOrder[idx], newOrder[idx + dir]] = [newOrder[idx + dir], newOrder[idx]];
    reorderMut.mutate(newOrder.map((r) => r.id));
  };
  const saving = createMut.isPending || updateMut.isPending;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <RouteIcon className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Règles de routage
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Affectez automatiquement chaque demande à la bonne direction et au bon service.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <LayoutToggle layout={layout} onChange={setLayout} />
          <Button onClick={openCreate} className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30">
            <Plus className="mr-1 h-4 w-4" /> Nouvelle règle
          </Button>
        </div>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <GlassCard>
          <div className="text-sm text-muted-foreground">Règles actives</div>
          <div className="mt-2 text-3xl font-bold">{list.filter((r) => r.active).length}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Auto-assignation</div>
          <div className="mt-2 text-3xl font-bold">{list.filter((r) => r.autoAssign).length}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Directions ciblées</div>
          <div className="mt-2 text-3xl font-bold">{new Set(list.map((r) => r.targetDirection)).size}</div>
        </GlassCard>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-destructive/30 bg-destructive/5 py-12 text-center">
          <AlertTriangle className="h-8 w-8 text-destructive" />
          <p className="text-sm font-medium text-destructive">Impossible de charger les règles de routage.</p>
          <p className="text-xs text-muted-foreground">Vérifiez que le serveur backend est démarré et réessayez.</p>
        </div>
      ) : layout === "list" ? (
        <GlassCard className="space-y-2 p-3">
          <div className="px-3 pt-2 pb-1 text-xs text-muted-foreground">
            Les règles sont évaluées dans l'ordre. La première règle correspondante est appliquée.
          </div>
          {sorted.map((r, i) => (
            <div
              key={r.id}
              className={cn(
                "flex flex-wrap items-center gap-3 rounded-2xl border border-border/40 bg-card/40 p-3 transition hover:border-primary/40",
                !r.active && "opacity-55",
              )}
            >
              <div className="flex flex-col">
                <button
                  disabled={i === 0}
                  onClick={() => move(r.id, -1)}
                  className="rounded p-0.5 hover:bg-foreground/5 disabled:opacity-30"
                  aria-label="Monter"
                >
                  <ArrowUp className="h-3.5 w-3.5" />
                </button>
                <button
                  disabled={i === sorted.length - 1}
                  onClick={() => move(r.id, 1)}
                  className="rounded p-0.5 hover:bg-foreground/5 disabled:opacity-30"
                  aria-label="Descendre"
                >
                  <ArrowDown className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="grid h-9 w-9 place-items-center rounded-xl bg-primary/10 font-mono text-xs font-bold text-primary">
                {String(i + 1).padStart(2, "0")}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{r.name}</span>
                  {r.autoAssign && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-medium text-accent-foreground dark:text-accent">
                      <Zap className="h-2.5 w-2.5" /> Auto-assign
                    </span>
                  )}
                </div>
                <div className="mt-0.5 text-xs text-muted-foreground">
                  Si <span className="font-semibold text-foreground/80">{fieldLabels[r.conditionField]}</span> = <span className="font-mono">{r.conditionValue}</span>
                  <span className="mx-1.5">→</span>
                  <span className="font-semibold text-foreground/80">{r.targetServiceLabel || r.targetService || "—"}</span>
                </div>
              </div>
              <Switch checked={r.active} onCheckedChange={() => toggleMut.mutate(r.id)} />
              <Button size="sm" variant="ghost" className="rounded-full" onClick={() => openEdit(r)}>
                <Edit3 className="h-3.5 w-3.5" />
              </Button>
              <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => deleteMut.mutate(r.id)}>
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          ))}
        </GlassCard>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {sorted.map((r, i) => (
            <GlassCard
              key={r.id}
              className={cn(
                "flex flex-col gap-3 p-4",
                !r.active && "opacity-55",
              )}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-primary/10 font-mono text-xs font-bold text-primary">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <span className="font-medium">{r.name}</span>
                {r.autoAssign && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-medium text-accent-foreground dark:text-accent">
                    <Zap className="h-2.5 w-2.5" /> Auto-assign
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                Si <span className="font-semibold text-foreground/80">{fieldLabels[r.conditionField]}</span> = <span className="font-mono">{r.conditionValue}</span>
                <span className="mx-1.5">→</span>
                <span className="font-semibold text-foreground/80">{r.targetDirection}</span> · {r.targetService}
              </div>
              <div className="mt-auto flex items-center justify-between pt-1">
                <Switch checked={r.active} onCheckedChange={() => toggleMut.mutate(r.id)} />
                <div className="flex items-center gap-1">
                  <Button size="sm" variant="ghost" className="rounded-full" onClick={() => openEdit(r)}>
                    <Edit3 className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => deleteMut.mutate(r.id)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editing?.id === "new" ? "Nouvelle règle de routage" : "Modifier la règle"}
            </DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-4 py-2">
              <div className="grid gap-2">
                <Label>Nom de la règle</Label>
                <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} placeholder="Ex. Pannes critiques → Réseau" />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label>Champ</Label>
                  <Select value={editing.conditionField} onValueChange={(v) => setEditing({ ...editing, conditionField: v as RoutingRule["conditionField"] })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {fields.map((f) => <SelectItem key={f} value={f}>{fieldLabels[f]}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Valeur</Label>
                  <Input placeholder="Ex. Panne réseau" value={editing.conditionValue} onChange={(e) => setEditing({ ...editing, conditionValue: e.target.value })} />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="grid gap-2">
                  <Label>Direction (filtre)</Label>
                  <Select value={editing.targetDirection} onValueChange={(v) => setEditing({ ...editing, targetDirection: v, targetService: "" })}>
                    <SelectTrigger><SelectValue placeholder="Toutes" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">Toutes les directions</SelectItem>
                      {directions.map((d) => <SelectItem key={d.id} value={d.id}>{d.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Unité cible</Label>
                  <Select value={editing.targetService} onValueChange={(v) => setEditing({ ...editing, targetService: v })}>
                    <SelectTrigger><SelectValue placeholder="Choisir une unité" /></SelectTrigger>
                    <SelectContent>
                      {filteredUnits.map((u) => (
                        <SelectItem key={u.id} value={u.code ?? u.id}>{u.name}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-card/60 p-3">
                <div>
                  <Label className="m-0">Auto-assignation</Label>
                  <p className="text-xs text-muted-foreground">Affecter automatiquement à un agent disponible</p>
                </div>
                <Switch checked={editing.autoAssign} onCheckedChange={(v) => setEditing({ ...editing, autoAssign: v })} />
              </div>
              <div className="flex items-center justify-between rounded-xl bg-card/60 p-3">
                <Label className="m-0">Règle active</Label>
                <Switch checked={editing.active} onCheckedChange={(v) => setEditing({ ...editing, active: v })} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button className="gradient-primary text-background" onClick={save} disabled={saving}>
              {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
