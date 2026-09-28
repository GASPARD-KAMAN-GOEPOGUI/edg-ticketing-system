import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { toast } from "sonner";
import {
  Plus,
  Edit3,
  Trash2,
  RotateCcw,
  Shield,
  Database,
  Loader2,
  CheckCircle2,
  Archive,
  Eye,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchRefTable,
  createRefItem,
  updateRefItem,
  deleteRefItem,
  restoreRefItem,
  REF_TABLES,
  REF_TABLE_LABELS,
  type RefTableName,
  type RawRefItem,
} from "@/lib/api/admin-config";

export const Route = createFileRoute("/app/admin/references")({
  head: () => ({ meta: [{ title: "Référentiels — Admin EDG" }] }),
  component: ReferencesAdminPage,
});

// ── Types ─────────────────────────────────────────────────────────────────────

type DialogMode = "create" | "edit";

interface FormState {
  code: string;
  label: string;
  sort_order: number;
  status: boolean;
}

function emptyForm(): FormState {
  return { code: "", label: "", sort_order: 0, status: true };
}

function formFromItem(item: RawRefItem): FormState {
  return {
    code: item.code,
    label: item.label,
    sort_order: item.sort_order,
    status: item.status,
  };
}

// ── Sub-components ────────────────────────────────────────────────────────────

function StatusBadge({ active, deleted }: { active: boolean; deleted?: boolean }) {
  if (deleted) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-zinc-500/15 px-2 py-0.5 text-[11px] font-medium text-zinc-500">
        <Archive className="h-3 w-3" />
        Archivé
      </span>
    );
  }
  return active ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
      <CheckCircle2 className="h-3 w-3" />
      Actif
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
      Inactif
    </span>
  );
}

// ── Table panel ───────────────────────────────────────────────────────────────

function TablePanel({ table }: { table: RefTableName }) {
  const qc = useQueryClient();
  const [showArchived, setShowArchived] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMode, setDialogMode] = useState<DialogMode>("create");
  const [editItem, setEditItem] = useState<RawRefItem | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [deleteTarget, setDeleteTarget] = useState<RawRefItem | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const { data: items = [], isLoading } = useQuery({
    queryKey: ["admin-ref", table],
    queryFn: () => fetchRefTable(table),
  });

  const visibleItems = showArchived
    ? items
    : items.filter((i) => !i.deleted_at);

  const createMut = useMutation({
    mutationFn: (data: FormState) =>
      createRefItem(table, {
        code: data.code,
        label: data.label,
        sort_order: data.sort_order,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-ref", table] });
      toast.success("Entrée créée avec succès");
      setDialogOpen(false);
    },
    onError: () => toast.error("Erreur lors de la création"),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<FormState> }) =>
      updateRefItem(table, id, {
        label: data.label,
        sort_order: data.sort_order,
        status: data.status,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-ref", table] });
      toast.success("Entrée mise à jour");
      setDialogOpen(false);
    },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteRefItem(table, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-ref", table] });
      toast.success("Entrée archivée");
      setConfirmOpen(false);
      setDeleteTarget(null);
    },
    // Le backend explique POURQUOI : combien de tickets utilisent la valeur, et
    // que la désactivation reste possible. Écraser ce message par un générique
    // laisserait l'administrateur sans solution.
    onError: (err) => {
      setConfirmOpen(false);
      toast.error(
        err instanceof Error && err.message
          ? err.message
          : "Impossible d'archiver cette entrée",
      );
    },
  });

  const restoreMut = useMutation({
    mutationFn: (id: string) => restoreRefItem(table, id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-ref", table] });
      toast.success("Entrée restaurée");
    },
    onError: () => toast.error("Erreur lors de la restauration"),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, status }: { id: string; status: boolean }) =>
      updateRefItem(table, id, { status }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-ref", table] }),
    onError: () => toast.error("Erreur lors du changement de statut"),
  });

  function openCreate() {
    setDialogMode("create");
    setEditItem(null);
    setForm(emptyForm());
    setDialogOpen(true);
  }

  function openEdit(item: RawRefItem) {
    setDialogMode("edit");
    setEditItem(item);
    setForm(formFromItem(item));
    setDialogOpen(true);
  }

  function handleSubmit() {
    if (!form.code.trim() || !form.label.trim()) {
      toast.error("Code et libellé sont obligatoires");
      return;
    }
    if (dialogMode === "create") {
      createMut.mutate(form);
    } else if (editItem) {
      // Sur une valeur intégrée, le code n'est pas envoyé : le backend le
      // refuserait, et il n'a de toute façon pas pu être modifié.
      const { code, ...rest } = form;
      updateMut.mutate({
        id: String(editItem.id),
        data: editItem.is_builtin ? rest : form,
      });
    }
  }

  // Le code n'est verrouille que sur une valeur INTEGREE : le fonctionnement de
  // l'application s'y refere (litteraux de statut, appariement des politiques
  // SLA par le texte du code). Sur une valeur creee ici, il reste libre.
  const codeLocked = dialogMode === "edit" && Boolean(editItem?.is_builtin);

  const isBusy = createMut.isPending || updateMut.isPending;
  const archivedCount = items.filter((i) => i.deleted_at).length;

  return (
    <div className="flex flex-col gap-4">
      {/* toolbar */}
      <div className="flex items-center justify-between gap-2 flex-wrap">
        <div className="flex items-center gap-2">
          {archivedCount > 0 && (
            <button
              onClick={() => setShowArchived((v) => !v)}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                showArchived
                  ? "bg-zinc-500/20 text-zinc-700 dark:text-zinc-300"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {showArchived ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              {showArchived ? "Masquer archivés" : `Voir archivés (${archivedCount})`}
            </button>
          )}
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4 mr-1.5" />
          Ajouter
        </Button>
      </div>

      {/* list */}
      {isLoading ? (
        <div className="flex items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin mr-2" />
          Chargement…
        </div>
      ) : visibleItems.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 py-10 text-center text-sm text-muted-foreground">
          Aucune entrée{showArchived ? "" : " active"}
        </div>
      ) : (
        <div className="divide-y divide-border/40 rounded-lg border border-border/60 overflow-hidden">
          {visibleItems.map((item) => {
            const isDeleted = !!item.deleted_at;
            return (
              <div
                key={item.id}
                className={cn(
                  "flex flex-col gap-2 px-4 py-3 text-sm transition-colors sm:flex-row sm:items-center sm:gap-3",
                  isDeleted
                    ? "bg-muted/30 opacity-60"
                    : "bg-background/50 hover:bg-muted/30",
                )}
              >
                {/* Identity: sort + code + label */}
                <div className="flex min-w-0 flex-1 items-center gap-2">
                  <span className="hidden w-7 shrink-0 text-right text-[11px] tabular-nums text-muted-foreground sm:inline-block">
                    {item.sort_order}
                  </span>
                  <code className="shrink-0 rounded bg-muted px-1.5 py-0.5 text-[11px] font-mono text-muted-foreground">
                    {item.code}
                  </code>
                  <span className="min-w-0 flex-1 truncate font-medium">{item.label}</span>
                </div>

                {/* Badges + actions */}
                <div className="flex flex-wrap items-center gap-1.5">
                  {item.is_builtin && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                      <Shield className="h-3 w-3" />
                      Intégré
                    </span>
                  )}
                  <StatusBadge active={item.status} deleted={isDeleted} />
                  <div className="ml-auto flex shrink-0 items-center gap-1">
                    {isDeleted ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-emerald-600"
                        title="Restaurer"
                        onClick={() => restoreMut.mutate(String(item.id))}
                        disabled={restoreMut.isPending}
                      >
                        <RotateCcw className="h-3.5 w-3.5" />
                      </Button>
                    ) : (
                      <>
                        <Switch
                          checked={item.status}
                          onCheckedChange={(v) =>
                            toggleMut.mutate({ id: String(item.id), status: v })
                          }
                          className="scale-75"
                        />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          title="Modifier"
                          onClick={() => openEdit(item)}
                        >
                          <Edit3 className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          title="Archiver"
                          onClick={() => {
                            setDeleteTarget(item);
                            setConfirmOpen(true);
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* create / edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {dialogMode === "create" ? "Nouvelle entrée" : "Modifier l'entrée"}
            </DialogTitle>
          </DialogHeader>

          <div className="grid gap-4 py-2">
            <div className="grid gap-1.5">
              <Label htmlFor="ref-code">Code *</Label>
              <Input
                id="ref-code"
                placeholder="ex: web, branchement…"
                value={form.code}
                onChange={(e) => setForm((f) => ({ ...f, code: e.target.value }))}
                disabled={codeLocked}
              />
              {codeLocked && (
                <p className="text-xs text-muted-foreground">
                  Cette valeur est intégrée au fonctionnement de l'application, qui
                  se réfère à son code : il ne peut pas être modifié. Le libellé,
                  lui, reste modifiable.
                </p>
              )}
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="ref-label">Libellé *</Label>
              <Input
                id="ref-label"
                placeholder="Libellé affiché"
                value={form.label}
                onChange={(e) => setForm((f) => ({ ...f, label: e.target.value }))}
              />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="ref-order">Ordre d'affichage</Label>
              <Input
                id="ref-order"
                type="number"
                min={0}
                value={form.sort_order}
                onChange={(e) =>
                  setForm((f) => ({ ...f, sort_order: parseInt(e.target.value) || 0 }))
                }
              />
            </div>

            {dialogMode === "edit" && (
              <div className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2.5">
                <Label htmlFor="ref-status" className="cursor-pointer">
                  Actif
                </Label>
                <Switch
                  id="ref-status"
                  checked={form.status}
                  onCheckedChange={(v) => setForm((f) => ({ ...f, status: v }))}
                />
              </div>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSubmit} disabled={isBusy}>
              {isBusy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              {dialogMode === "create" ? "Créer" : "Enregistrer"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* confirm delete dialog */}
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Archiver cette entrée ?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            L'entrée{" "}
            <span className="font-semibold text-foreground">
              {deleteTarget?.label}
            </span>{" "}
            sera archivée (soft-delete). Elle pourra être restaurée ultérieurement.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmOpen(false)}>
              Annuler
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteTarget && deleteMut.mutate(String(deleteTarget.id))}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Archiver
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

function ReferencesAdminPage() {
  const [activeTable, setActiveTable] = useState<RefTableName>(REF_TABLES[0]);

  return (
    <div className="flex flex-col gap-6 p-4 md:p-6">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10">
          <Database className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h1 className="text-xl font-bold">Référentiels</h1>
          <p className="text-sm text-muted-foreground">
            Gestion des valeurs de référence du système
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-4 lg:flex-row lg:gap-6">
        {/* sidebar — table selector */}
        <aside className="shrink-0 lg:w-56">
          {/* Mobile: horizontal scroll pills */}
          <div className="flex gap-1.5 overflow-x-auto pb-1 lg:hidden">
            {REF_TABLES.map((t) => (
              <button
                key={t}
                onClick={() => setActiveTable(t)}
                className={cn(
                  "shrink-0 whitespace-nowrap rounded-full px-3 py-1.5 text-xs font-medium transition-colors",
                  activeTable === t
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted/60 text-muted-foreground hover:text-foreground",
                )}
              >
                {REF_TABLE_LABELS[t]}
              </button>
            ))}
          </div>
          {/* Desktop: vertical nav */}
          <GlassCard className="hidden p-2 lg:block">
            <nav className="flex flex-col gap-0.5">
              {REF_TABLES.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTable(t)}
                  className={cn(
                    "w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors",
                    activeTable === t
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground",
                  )}
                >
                  {REF_TABLE_LABELS[t]}
                </button>
              ))}
            </nav>
          </GlassCard>
        </aside>

        {/* main panel */}
        <div className="flex-1 min-w-0">
          <GlassCard className="p-5">
            <div className="mb-4 flex items-center gap-2">
              <h2 className="text-base font-semibold">{REF_TABLE_LABELS[activeTable]}</h2>
              <Badge variant="outline" className="text-[11px]">
                {activeTable}
              </Badge>
            </div>
            <TablePanel key={activeTable} table={activeTable} />
          </GlassCard>
        </div>
      </div>
    </div>
  );
}
