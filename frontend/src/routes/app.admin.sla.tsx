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
import { priorityLabels } from "@/lib/mock-data";
import type { SLAPolicy, Priority } from "@/lib/mock-data";
import { useState } from "react";
import { toast } from "sonner";
import { Plus, Timer, Trash2, Edit3, AlertTriangle, Clock, CheckCircle2, BarChart2, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSlaPolicies,
  createSlaPolicy,
  updateSlaPolicy,
  toggleSlaPolicy,
  deleteSlaPolicy,
  fetchRefTable,
} from "@/lib/api/admin-config";

export const Route = createFileRoute("/app/admin/sla")({
  head: () => ({ meta: [{ title: "SLA & Priorités — Admin EDG" }] }),
  component: SLAAdminPage,
});

const priorities: Priority[] = ["low", "medium", "high", "critical"];

const priorityTone: Record<Priority, string> = {
  low:      "bg-muted text-muted-foreground",
  medium:   "bg-info/15 text-info",
  high:     "bg-warning/20 text-warning-foreground dark:text-warning",
  critical: "bg-destructive/15 text-destructive",
};

const priorityDot: Record<Priority, string> = {
  low:      "bg-slate-400",
  medium:   "bg-info",
  high:     "bg-orange-500",
  critical: "bg-red-500",
};

function emptyPolicy(defaultCategory = ""): SLAPolicy {
  return {
    id: "new",
    category: defaultCategory,
    priority: "medium",
    responseH: 4,
    resolutionH: 24,
    escalateAfterH: 16,
    active: true,
  };
}

function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold", priorityTone[priority])}>
      <span className={cn("h-1.5 w-1.5 rounded-full", priorityDot[priority])} />
      {priorityLabels[priority]}
    </span>
  );
}

function SLACard({
  p,
  onEdit,
  onRemove,
  onToggle,
}: {
  p: SLAPolicy;
  onEdit: (p: SLAPolicy) => void;
  onRemove: (id: string) => void;
  onToggle: (id: string) => void;
}) {
  return (
    <GlassCard className={cn("group flex flex-col gap-4 transition hover:-translate-y-0.5 hover:shadow-lg", !p.active && "opacity-55")}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold leading-tight">{p.category}</div>
          <div className="mt-1.5">
            <PriorityBadge priority={p.priority} />
          </div>
        </div>
        <Switch checked={p.active} onCheckedChange={() => onToggle(p.id)} />
      </div>

      <div className="grid grid-cols-3 gap-1 rounded-2xl bg-background/40 p-2 sm:gap-2 sm:p-3">
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-[9px] font-medium uppercase tracking-wide text-muted-foreground sm:text-[10px]">
            <Clock className="h-2.5 w-2.5 sm:h-3 sm:w-3" /> Réponse
          </div>
          <div className="mt-1 text-base font-bold sm:text-xl">{p.responseH}h</div>
        </div>
        <div className="border-x border-border/40 text-center">
          <div className="flex items-center justify-center gap-1 text-[9px] font-medium uppercase tracking-wide text-muted-foreground sm:text-[10px]">
            <CheckCircle2 className="h-2.5 w-2.5 sm:h-3 sm:w-3" /> Résolution
          </div>
          <div className="mt-1 text-base font-bold text-primary sm:text-xl">{p.resolutionH}h</div>
        </div>
        <div className="text-center">
          <div className="flex items-center justify-center gap-1 text-[9px] font-medium uppercase tracking-wide text-warning-foreground dark:text-warning sm:text-[10px]">
            <AlertTriangle className="h-2.5 w-2.5 sm:h-3 sm:w-3" /> Escalade
          </div>
          <div className="mt-1 text-base font-bold text-warning-foreground dark:text-warning sm:text-xl">{p.escalateAfterH}h</div>
        </div>
      </div>

      <div className="flex justify-end gap-1.5 border-t border-border/30 pt-1">
        <Button size="sm" variant="ghost" className="rounded-full" onClick={() => onEdit(p)}>
          <Edit3 className="h-3.5 w-3.5" />
        </Button>
        <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => onRemove(p.id)}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </GlassCard>
  );
}

function SLAAdminPage() {
  const qc = useQueryClient();
  const [editing, setEditing] = useState<SLAPolicy | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);

  const { data: list = [], isLoading } = useQuery({
    queryKey: ["admin", "sla"],
    queryFn: fetchSlaPolicies,
  });

  const { data: categoryItems = [] } = useQuery({
    queryKey: ["admin-ref", "request_categories"],
    queryFn: () => fetchRefTable("request_categories"),
    staleTime: 300_000,
  });

  const categories = categoryItems.filter((c) => c.status).map((c) => c.label);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "sla"] });

  const createMut = useMutation({
    mutationFn: (p: SLAPolicy) => createSlaPolicy(p),
    onSuccess: () => { invalidate(); toast.success("Politique SLA créée"); },
    onError: () => toast.error("Erreur lors de la création"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, p }: { id: string; p: SLAPolicy }) =>
      updateSlaPolicy(id, { responseH: p.responseH, resolutionH: p.resolutionH, escalateAfterH: p.escalateAfterH, active: p.active }),
    onSuccess: () => { invalidate(); toast.success("Politique SLA mise à jour"); },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });

  const toggleMut = useMutation({
    mutationFn: (id: string) => toggleSlaPolicy(id),
    onSuccess: () => invalidate(),
    onError: () => toast.error("Erreur lors du basculement"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteSlaPolicy(id),
    onSuccess: () => { invalidate(); toast.success("Politique supprimée"); },
    onError: () => toast.error("Erreur lors de la suppression"),
  });

  const openCreate = () => { setEditing(emptyPolicy(categories[0] ?? "")); setDialogOpen(true); };
  const openEdit   = (p: SLAPolicy) => { setEditing({ ...p }); setDialogOpen(true); };

  const save = () => {
    if (!editing) return;
    if (editing.id === "new") {
      createMut.mutate(editing, {
        onSuccess: () => { setDialogOpen(false); setEditing(null); },
      });
    } else {
      updateMut.mutate({ id: editing.id, p: editing }, {
        onSuccess: () => { setDialogOpen(false); setEditing(null); },
      });
    }
  };

  const saving = createMut.isPending || updateMut.isPending;

  const avgResolution = Math.round(
    list.reduce((s, p) => s + p.resolutionH, 0) / Math.max(list.length, 1),
  );

  return (
    <div className="mx-auto max-w-7xl space-y-6">

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Timer className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Politiques SLA & priorités
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Définissez les délais de réponse, résolution et seuils d'escalade par catégorie.
          </p>
        </div>
        <Button onClick={openCreate} className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30">
          <Plus className="mr-1 h-4 w-4" /> Nouvelle politique
        </Button>
      </header>

      <div className="grid gap-4 sm:grid-cols-3">
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-success/15 text-success">
            <CheckCircle2 className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{list.filter((p) => p.active).length}</div>
            <div className="text-xs text-muted-foreground">Politiques actives</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl gradient-primary text-background">
            <BarChart2 className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{avgResolution}h</div>
            <div className="text-xs text-muted-foreground">Délai moyen résolution</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-4">
          <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-info/15 text-info">
            <Timer className="h-5 w-5" />
          </div>
          <div>
            <div className="text-2xl font-bold">{new Set(list.map((p) => p.category)).size}</div>
            <div className="text-xs text-muted-foreground">Catégories couvertes</div>
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
                  <th className="px-5 py-3 text-left font-semibold">Catégorie</th>
                  <th className="px-5 py-3 text-left font-semibold">Priorité</th>
                  <th className="px-5 py-3 text-right font-semibold">Réponse</th>
                  <th className="px-5 py-3 text-right font-semibold">Résolution</th>
                  <th className="px-5 py-3 text-right font-semibold">Escalade auto</th>
                  <th className="px-5 py-3 text-center font-semibold">Active</th>
                  <th className="px-5 py-3 text-right font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody>
                {list.map((p) => (
                  <tr key={p.id} className={cn("border-t border-border/40 transition hover:bg-card/40", !p.active && "opacity-55")}>
                    <td className="px-5 py-3.5 font-medium">{p.category}</td>
                    <td className="px-5 py-3.5">
                      <PriorityBadge priority={p.priority} />
                    </td>
                    <td className="px-5 py-3.5 text-right text-muted-foreground">{p.responseH}h</td>
                    <td className="px-5 py-3.5 text-right font-semibold">{p.resolutionH}h</td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="inline-flex items-center gap-1 text-warning-foreground dark:text-warning">
                        <AlertTriangle className="h-3.5 w-3.5" /> {p.escalateAfterH}h
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <Switch checked={p.active} onCheckedChange={() => toggleMut.mutate(p.id)} />
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <div className="flex justify-end gap-1.5">
                        <Button size="sm" variant="ghost" className="rounded-full" onClick={() => openEdit(p)}>
                          <Edit3 className="h-3.5 w-3.5" />
                        </Button>
                        <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => deleteMut.mutate(p.id)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>
              {editing?.id === "new" ? "Nouvelle politique SLA" : "Modifier la politique"}
            </DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-4 py-2">
              <div className="grid gap-2">
                <Label>Catégorie</Label>
                <Select value={editing.category} onValueChange={(v) => setEditing({ ...editing, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Priorité</Label>
                <Select value={editing.priority} onValueChange={(v) => setEditing({ ...editing, priority: v as Priority })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {priorities.map((p) => (
                      <SelectItem key={p} value={p}>
                        <span className="flex items-center gap-2">
                          <span className={cn("h-2 w-2 rounded-full", priorityDot[p])} />
                          {priorityLabels[p]}
                        </span>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="grid gap-2">
                  <Label>Réponse (h)</Label>
                  <Input type="number" min={0} placeholder="Ex. 4" value={editing.responseH}
                    onChange={(e) => setEditing({ ...editing, responseH: Number(e.target.value) })} />
                </div>
                <div className="grid gap-2">
                  <Label>Résolution (h)</Label>
                  <Input type="number" min={0} placeholder="Ex. 24" value={editing.resolutionH}
                    onChange={(e) => setEditing({ ...editing, resolutionH: Number(e.target.value) })} />
                </div>
                <div className="grid gap-2">
                  <Label>Escalade (h)</Label>
                  <Input type="number" min={0} placeholder="Ex. 16" value={editing.escalateAfterH}
                    onChange={(e) => setEditing({ ...editing, escalateAfterH: Number(e.target.value) })} />
                </div>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-card/60 p-3">
                <div>
                  <Label className="m-0">Politique active</Label>
                  <p className="text-xs text-muted-foreground">Appliquée aux nouveaux tickets</p>
                </div>
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
