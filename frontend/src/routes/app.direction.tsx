import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useState, useMemo, useCallback } from "react";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { statusLabels } from "@/lib/mock-data";
import { useUser } from "@/lib/session";
import { fetchRequests, updateRequest } from "@/lib/api/requests";
import {
  fetchEscalations,
  reviewEscalation,
  resolveEscalation,
  escalateRequest,
} from "@/lib/api/escalations";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { apiFetch } from "@/lib/api/client";
import type { RoutingRule } from "@/lib/mock-data";
import { mapRoutingRule, type RawRoutingRule } from "@/lib/api/admin-config";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  AlertTriangle,
  CheckCircle2,
  Building2,
  Loader2,
  ArrowUpRight,
  ArrowRight,
  Clock,
  Inbox,
  Eye,
  RotateCcw,
  Route as RouteIcon,
  Plus,
  Trash2,
  Pencil,
  ToggleLeft,
  ToggleRight,
} from "lucide-react";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";

export const Route = createFileRoute("/app/direction")({
  beforeLoad: () => requireRole("director", "admin"),
  head: () => ({ meta: [{ title: "Demandes direction — EDG Support" }] }),
  component: DirectionView,
});

const ACTIVE_STATUSES = new Set([
  "new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened",
]);

function DirectionView() {
  const sessionUser = useUser();
  const qc = useQueryClient();
  const directionId = sessionUser?.direction_id;

  const [escalatingId, setEscalatingId] = useState<string | null>(null);
  const [escalateReason, setEscalateReason] = useState("");

  /* ── Queries ─────────────────────────────────────────────────────────── */

  const { data: reqData, isLoading } = useQuery({
    queryKey: ["director-dir-requests", directionId],
    queryFn: () => fetchRequests({ direction_id: directionId, limit: 200 }),
    enabled: !!directionId,
    staleTime: 30_000,
  });

  const { data: escData, isLoading: loadEsc } = useQuery({
    queryKey: ["director-l3-escalations"],
    queryFn: () => fetchEscalations({ level: "L3", limit: 100 }),
    staleTime: 30_000,
  });

  const { data: chiefsData } = useQuery({
    queryKey: ["director-chiefs", directionId],
    queryFn: () => fetchUsers({ role: "chief", direction_id: directionId, limit: 50 }),
    enabled: !!directionId,
    staleTime: 60_000,
  });

  const { data: directionsData = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: unitsData = [] } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });

  const directionName = directionsData.find((d) => d.id === directionId)?.name ?? directionId ?? "—";
  const unitLookup = Object.fromEntries(unitsData.map((u) => [u.id, u.name]));

  const allItems = reqData?.items ?? [];
  const total = reqData?.total ?? 0;
  const escalations = escData?.items ?? [];
  const chiefs = chiefsData?.items ?? [];

  const { paged: pagedItems, page: reqPage, setPage: setReqPage, totalPages: reqTotalPages, total: reqTableTotal, pageSize: reqPageSize } = usePagination(allItems, 20);

  /* ── KPIs ─────────────────────────────────────────────────────────────── */

  const open         = allItems.filter((r) => ACTIVE_STATUSES.has(r.status)).length;
  const inProgress   = allItems.filter((r) => r.status === "in_progress").length;
  const pendingCount = allItems.filter((r) => r.status === "pending").length;
  const escalated    = allItems.filter((r) => r.status === "escalated").length;
  const slaBreached  = allItems.filter((r) => r.slaElapsed > r.slaHours && ACTIVE_STATUSES.has(r.status)).length;
  const critical     = allItems.filter((r) => r.priority === "critical" && ACTIVE_STATUSES.has(r.status)).length;
  const resolved     = allItems.filter((r) => ["resolved", "closed"].includes(r.status)).length;

  /* ── Computed charts ──────────────────────────────────────────────────── */

  const statusBreakdownData = useMemo(() => {
    const acc: Record<string, number> = {};
    allItems.forEach((r) => { acc[r.status] = (acc[r.status] ?? 0) + 1; });
    return Object.entries(acc)
      .map(([s, v]) => ({
        status: s,
        label: statusLabels[s as keyof typeof statusLabels] ?? s,
        value: v,
      }))
      .sort((a, b) => b.value - a.value);
  }, [allItems]);

  const serviceData = useMemo(() => {
    const map: Record<string, { open: number; resolved: number; slaBreached: number }> = {};
    allItems.forEach((r) => {
      const s = r.serviceId ?? "unknown";
      if (!map[s]) map[s] = { open: 0, resolved: 0, slaBreached: 0 };
      if (ACTIVE_STATUSES.has(r.status)) map[s].open++;
      if (["resolved", "closed"].includes(r.status)) map[s].resolved++;
      if (r.slaElapsed > r.slaHours && ACTIVE_STATUSES.has(r.status)) map[s].slaBreached++;
    });
    return Object.entries(map).map(([id, st]) => ({
      name: (unitLookup[id] ?? id).substring(0, 14),
      Ouvertes: st.open,
      Résolues: st.resolved,
      "Hors délai": st.slaBreached,
    }));
  }, [allItems, unitLookup]);

  /* ── Chef performance (C9) ────────────────────────────────────────────── */

  const chiefStats = useMemo(() =>
    chiefs.map((c) => {
      const reqs = allItems.filter((r) => r.serviceId === c.unit_id);
      const cOpen     = reqs.filter((r) => ACTIVE_STATUSES.has(r.status)).length;
      const cResolved = reqs.filter((r) => ["resolved", "closed"].includes(r.status)).length;
      const cSla      = reqs.filter((r) => r.slaElapsed > r.slaHours && ACTIVE_STATUSES.has(r.status)).length;
      return { chief: c, open: cOpen, resolved: cResolved, slaBreached: cSla, total: reqs.length };
    }),
  [chiefs, allItems]);

  /* ── Mutations (C3) ───────────────────────────────────────────────────── */

  const reviewMut = useMutation({
    mutationFn: (id: string) => reviewEscalation(id),
    onSuccess: () => {
      toast.success("Escalade prise en revue.");
      qc.invalidateQueries({ queryKey: ["director-l3-escalations"] });
      qc.invalidateQueries({ queryKey: ["escalations"] });
      qc.invalidateQueries({ queryKey: ["requests"] });
    },
    onError: () => toast.error("Erreur lors de la prise en revue."),
  });

  const returnToChiefMut = useMutation({
    mutationFn: async ({ escId, requestId }: { escId: string; requestId?: string }) => {
      await resolveEscalation(escId);
      if (requestId) await updateRequest(requestId, { request_status: "in_progress" });
    },
    onSuccess: () => {
      toast.success("Renvoyé au chef de service.");
      qc.invalidateQueries({ queryKey: ["director-l3-escalations"] });
      qc.invalidateQueries({ queryKey: ["director-dir-requests", directionId] });
      qc.invalidateQueries({ queryKey: ["escalations"] });
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["queue"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: () => toast.error("Erreur lors du renvoi."),
  });

  const escalateToDGMut = useMutation({
    mutationFn: async ({ escId, requestId, reason }: { escId: string; requestId: string; reason: string }) => {
      await escalateRequest(requestId, {
        level: "DG",
        reason,
        from_agent_name: sessionUser?.name ?? "Directeur",
        to_agent_name: "Direction Générale",
      });
      await resolveEscalation(escId);
    },
    onSuccess: () => {
      toast.success("Escalade transmise à la Direction Générale.");
      qc.invalidateQueries({ queryKey: ["director-l3-escalations"] });
      qc.invalidateQueries({ queryKey: ["escalations"] });
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
      setEscalatingId(null);
      setEscalateReason("");
    },
    onError: () => toast.error("Erreur lors de l'escalade DG."),
  });

  /* ── Règles de routage de la direction ──────────────────────────────── */

  const { data: routingRules = [], refetch: refetchRules } = useQuery<RoutingRule[]>({
    queryKey: ["admin", "routing", "direction", directionId],
    queryFn: async () => {
      if (!directionId) return [];
      const res = await apiFetch<{ items: RawRoutingRule[] }>("/admin/routing");
      const directionUnitCodes = new Set(unitsData.map((u) => u.code ?? u.id));
      return res.items
        .map(mapRoutingRule)
        .filter((r) => !r.targetService || directionUnitCodes.has(r.targetService));
    },
    enabled: !!directionId && unitsData.length > 0,
    staleTime: 60_000,
  });

  const [ruleDialog, setRuleDialog] = useState(false);
  const [editingRule, setEditingRule] = useState<RoutingRule | null>(null);
  const [ruleForm, setRuleForm] = useState({ name: "", conditionField: "category" as RoutingRule["conditionField"], conditionValue: "", targetService: "", autoAssign: false });

  const { data: myUnits = [] } = useQuery({
    queryKey: ["units", "direction", directionId],
    queryFn: () => fetchUnits(directionId),
    enabled: !!directionId,
    staleTime: 300_000,
  });

  const saveRuleMut = useMutation({
    mutationFn: async () => {
      const body = {
        name: ruleForm.name.trim(),
        condition_field: ruleForm.conditionField,
        condition_value: ruleForm.conditionValue.trim(),
        target_unity_codename: ruleForm.targetService || undefined,
        auto_assign: ruleForm.autoAssign,
        sort_order: editingRule?.order ?? routingRules.length + 1,
        status: true,
      };
      if (editingRule && editingRule.id !== "new") {
        return apiFetch(`/admin/routing/${editingRule.id}`, { method: "PATCH", body: JSON.stringify(body) });
      }
      return apiFetch("/admin/routing", { method: "POST", body: JSON.stringify(body) });
    },
    onSuccess: () => { toast.success(editingRule ? "Règle mise à jour." : "Règle créée."); setRuleDialog(false); refetchRules(); },
    onError: () => toast.error("Erreur lors de la sauvegarde."),
  });

  const deleteRuleMut = useMutation({
    mutationFn: (id: string) => apiFetch(`/admin/routing/${id}`, { method: "DELETE" }),
    onSuccess: () => { toast.success("Règle supprimée."); refetchRules(); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  const toggleRuleMut = useMutation({
    mutationFn: ({ id }: { id: string; active: boolean }) =>
      apiFetch(`/admin/routing/${id}/toggle`, { method: "PATCH", body: "{}" }),
    onSuccess: () => refetchRules(),
  });

  function openCreateRule() {
    setEditingRule(null);
    setRuleForm({ name: "", conditionField: "category", conditionValue: "", targetService: "", autoAssign: false });
    setRuleDialog(true);
  }
  function openEditRule(r: RoutingRule) {
    setEditingRule(r);
    setRuleForm({ name: r.name, conditionField: r.conditionField, conditionValue: r.conditionValue, targetService: r.targetService ?? "", autoAssign: r.autoAssign });
    setRuleDialog(true);
  }

  /* ── Render ───────────────────────────────────────────────────────────── */

  if (!sessionUser) {
    return (
      <div className="flex h-40 items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
      </div>
    );
  }

  if (!directionId) {
    return (
      <div className="mx-auto max-w-2xl py-16 text-center">
        <div className="mb-4 grid h-14 w-14 mx-auto place-items-center rounded-2xl bg-warning/15">
          <AlertTriangle className="h-7 w-7 text-warning" />
        </div>
        <h2 className="text-xl font-bold tracking-tight">Aucune direction assignée</h2>
        <p className="mt-3 text-sm text-muted-foreground max-w-sm mx-auto">
          Votre compte directeur n'est pas encore rattaché à une direction.
          Contactez un administrateur pour qu'il associe votre compte à la direction dont vous êtes responsable.
        </p>
      </div>
    );
  }


  return (
    <div className="mx-auto max-w-7xl space-y-6 animate-fade-in">

      {/* Header */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Building2 className="h-3 w-3" />
            {directionName}
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Demandes de la direction
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Vue consolidée multi-services · {sessionUser?.name}
          </p>
        </div>
        <Button asChild variant="outline" className="rounded-full">
          <Link to="/app/requests">
            Toutes les demandes <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Link>
        </Button>
      </header>

      {/* KPIs Row 1 */}
      {isLoading ? (
        <div className="flex h-20 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 stagger">
            <GlassCard className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Total direction</span>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-primary/10 text-primary">
                  <Inbox className="h-4 w-4" />
                </span>
              </div>
              <div className="text-3xl font-bold tracking-tight">{total}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Ouvertes</span>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-accent/15 text-accent">
                  <Clock className="h-4 w-4" />
                </span>
              </div>
              <div className="text-3xl font-bold tracking-tight text-primary">{open}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Résolues</span>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-success/15 text-success">
                  <CheckCircle2 className="h-4 w-4" />
                </span>
              </div>
              <div className="text-3xl font-bold tracking-tight text-success">{resolved}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Hors délai SLA</span>
                <span className="grid h-9 w-9 place-items-center rounded-xl bg-destructive/15 text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                </span>
              </div>
              <div className="text-3xl font-bold tracking-tight text-destructive">{slaBreached}</div>
            </GlassCard>
          </div>

          {/* KPIs Row 2 */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
            <GlassCard className="flex flex-col gap-3">
              <span className="text-sm text-muted-foreground">En cours</span>
              <div className="text-3xl font-bold tracking-tight">{inProgress}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <span className="text-sm text-muted-foreground">En attente</span>
              <div className="text-3xl font-bold tracking-tight text-warning">{pendingCount}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <span className="text-sm text-muted-foreground">Escaladées (L3)</span>
              <div className="text-3xl font-bold tracking-tight text-warning">{escalated}</div>
            </GlassCard>
            <GlassCard className="flex flex-col gap-3">
              <span className="text-sm text-muted-foreground">Critiques actives</span>
              <div className="text-3xl font-bold tracking-tight text-destructive">{critical}</div>
            </GlassCard>
          </div>
        </>
      )}

      {/* Charts */}
      <div className="grid gap-4 lg:grid-cols-2">
        {serviceData.length > 0 && (
          <GlassCard>
            <h2 className="mb-4 font-semibold">Performance par service</h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={serviceData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="Ouvertes" fill="var(--color-chart-3)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Résolues" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Hors délai" fill="var(--color-destructive)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </GlassCard>
        )}

        {statusBreakdownData.length > 0 && (
          <GlassCard>
            <h2 className="mb-4 font-semibold">Répartition par statut</h2>
            <div className="space-y-2.5">
              {statusBreakdownData.map((item) => (
                <div key={item.status} className="flex items-center gap-3">
                  <div className="w-36 shrink-0 truncate text-xs text-muted-foreground">{item.label}</div>
                  <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-muted/50">
                    <div
                      className="h-full rounded-full bg-primary/70 transition-all duration-500"
                      style={{
                        width: allItems.length ? `${Math.round((item.value / allItems.length) * 100)}%` : "0%",
                      }}
                    />
                  </div>
                  <span className="w-6 shrink-0 text-right text-xs font-semibold">{item.value}</span>
                </div>
              ))}
            </div>
          </GlassCard>
        )}
      </div>

      {/* L3 Escalations — C3 */}
      <GlassCard>
        <div className="mb-4 flex items-center gap-3">
          <h2 className="font-semibold">Escalades L3 — Arbitrage Direction</h2>
          {loadEsc ? (
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground/40" />
          ) : (
            <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">
              {escalations.filter((e) => e.status !== "resolved").length} actives
            </span>
          )}
        </div>

        {escalations.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Aucune escalade L3 en attente.
          </p>
        ) : (
          <div className="space-y-3">
            {[...escalations].sort((a, b) => b.slaOverHours - a.slaOverHours).map((esc) => (
              <div key={esc.id} className="rounded-2xl border border-border/40 bg-background/50 p-4 space-y-3">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      {esc.requestId ? (
                        <Link
                          to="/app/requests/$id"
                          params={{ id: esc.requestId }}
                          className="font-mono text-xs font-medium text-primary hover:underline"
                        >
                          {esc.requestRef}
                        </Link>
                      ) : (
                        <span className="font-mono text-xs font-medium">{esc.requestRef}</span>
                      )}
                      <span className="rounded-full bg-destructive/10 px-2 py-0.5 text-[10px] font-semibold text-destructive">
                        +{esc.slaOverHours}h SLA
                      </span>
                      <span className={cn(
                        "rounded-full px-2 py-0.5 text-[10px] font-semibold",
                        esc.status === "open"
                          ? "bg-warning/15 text-warning"
                          : esc.status === "in_review"
                            ? "bg-info/15 text-info"
                            : "bg-success/15 text-success",
                      )}>
                        {esc.status === "open" ? "Ouvert" : esc.status === "in_review" ? "En revue" : "Résolu"}
                      </span>
                    </div>
                    <p className="text-sm font-medium">{esc.title}</p>
                    <p className="line-clamp-2 text-xs text-muted-foreground">{esc.reason}</p>
                    <p className="text-xs text-muted-foreground">
                      De {esc.fromAgent} → {esc.toAgent}
                    </p>
                  </div>

                  {esc.status !== "resolved" && (
                    <div className="flex flex-wrap gap-2">
                      {esc.status === "open" && (
                        <Button
                          size="sm" variant="outline" className="h-8 rounded-full text-xs"
                          disabled={reviewMut.isPending}
                          onClick={() => reviewMut.mutate(esc.id)}
                        >
                          <Eye className="mr-1 h-3 w-3" /> Prendre en revue
                        </Button>
                      )}
                      <Button
                        size="sm" variant="outline" className="h-8 rounded-full text-xs"
                        disabled={returnToChiefMut.isPending}
                        onClick={() => returnToChiefMut.mutate({ escId: esc.id, requestId: esc.requestId })}
                      >
                        <RotateCcw className="mr-1 h-3 w-3" /> Renvoyer Chef
                      </Button>
                      {esc.requestId && (
                        <Button
                          size="sm" variant="outline"
                          className="h-8 rounded-full text-xs border-warning/40 text-warning hover:bg-warning/10"
                          disabled={escalateToDGMut.isPending}
                          onClick={() => setEscalatingId(esc.id)}
                        >
                          <ArrowUpRight className="mr-1 h-3 w-3" /> Escalader DG
                        </Button>
                      )}
                    </div>
                  )}
                </div>

                {/* DG escalation form */}
                {escalatingId === esc.id && esc.requestId && (
                  <div className="space-y-2 border-t border-border/30 pt-3">
                    <textarea
                      value={escalateReason}
                      onChange={(e) => setEscalateReason(e.target.value)}
                      placeholder="Motif de l'escalade à la Direction Générale…"
                      rows={2}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-warning/40"
                    />
                    <div className="flex justify-end gap-2">
                      <Button size="sm" variant="ghost" className="rounded-full"
                        onClick={() => { setEscalatingId(null); setEscalateReason(""); }}>
                        Annuler
                      </Button>
                      <Button
                        size="sm"
                        className="rounded-full bg-warning text-warning-foreground hover:bg-warning/90"
                        disabled={!escalateReason.trim() || escalateToDGMut.isPending}
                        onClick={() => escalateToDGMut.mutate({
                          escId: esc.id,
                          requestId: esc.requestId!,
                          reason: escalateReason,
                        })}
                      >
                        {escalateToDGMut.isPending
                          ? <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                          : <ArrowUpRight className="mr-1 h-3 w-3" />}
                        Confirmer escalade DG
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Chef de Service performance — C9 */}
      {chiefStats.length > 0 && (
        <GlassCard>
          <h2 className="mb-4 font-semibold">Performance Chefs de Service</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="pb-2.5 text-left font-semibold">Chef de Service</th>
                  <th className="pb-2.5 text-center font-semibold">Ouvertes</th>
                  <th className="pb-2.5 text-center font-semibold">Résolues</th>
                  <th className="pb-2.5 text-center font-semibold">SLA dépassé</th>
                  <th className="hidden pb-2.5 text-center font-semibold sm:table-cell">Taux résolution</th>
                </tr>
              </thead>
              <tbody>
                {chiefStats.map(({ chief, open: cOpen, resolved: cRes, slaBreached: cSla, total: cTotal }) => {
                  const rate = cTotal > 0 ? Math.round((cRes / cTotal) * 100) : 0;
                  const slaClass = cSla > 2 ? "text-destructive" : cSla > 0 ? "text-warning" : "text-success";
                  return (
                    <tr key={chief.id} className="border-t border-border/40">
                      <td className="py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                            {chief.name.slice(0, 2).toUpperCase()}
                          </span>
                          <span className="font-medium">{chief.name}</span>
                        </div>
                      </td>
                      <td className="py-2.5 text-center font-semibold">{cOpen}</td>
                      <td className="py-2.5 text-center font-semibold text-success">{cRes}</td>
                      <td className={cn("py-2.5 text-center font-semibold", slaClass)}>{cSla}</td>
                      <td className="hidden py-2.5 text-center sm:table-cell">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-semibold",
                          rate >= 70 ? "bg-success/15 text-success" : rate >= 40 ? "bg-warning/15 text-warning" : "bg-destructive/10 text-destructive",
                        )}>
                          {rate}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      )}

      {/* Ticket list — C6 */}
      <GlassCard>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-semibold">Demandes de la direction ({total})</h2>
        </div>
        {isLoading ? (
          <div className="flex h-20 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
          </div>
        ) : allItems.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune demande pour cette direction.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="pb-2.5 text-left font-semibold">Référence</th>
                  <th className="pb-2.5 text-left font-semibold">Sujet</th>
                  <th className="hidden pb-2.5 text-left font-semibold sm:table-cell">Service</th>
                  <th className="pb-2.5 text-left font-semibold">Statut</th>
                  <th className="hidden pb-2.5 text-left font-semibold sm:table-cell">Priorité</th>
                </tr>
              </thead>
              <tbody>
                {pagedItems.map((r) => (
                  <tr key={r.id} className="border-t border-border/40 transition hover:bg-foreground/[0.02]">
                    <td className="py-2.5">
                      <Link
                        to="/app/requests/$id"
                        params={{ id: r.id }}
                        className="font-mono text-xs font-medium text-primary hover:underline"
                      >
                        {r.ref}
                      </Link>
                    </td>
                    <td className="max-w-xs truncate py-2.5 font-medium">{r.title}</td>
                    <td className="hidden py-2.5 text-xs text-muted-foreground sm:table-cell">
                      {r.serviceId ? (unitLookup[r.serviceId] ?? r.serviceId) : "—"}
                    </td>
                    <td className="py-2.5">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="hidden py-2.5 sm:table-cell">
                      <PriorityBadge priority={r.priority} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {reqTotalPages > 1 && (
          <div className="mt-4">
            <PaginationBar
              page={reqPage}
              totalPages={reqTotalPages}
              total={reqTableTotal}
              pageSize={reqPageSize}
              onChange={setReqPage}
            />
          </div>
        )}
      </GlassCard>

      {/* ── Règles de routage de ma direction ── */}
      <GlassCard>
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RouteIcon className="h-4 w-4 text-primary" />
            <h2 className="font-semibold">Règles de routage de ma direction</h2>
          </div>
          <Button size="sm" className="gradient-primary rounded-full" onClick={openCreateRule}>
            <Plus className="mr-1 h-3.5 w-3.5" /> Nouvelle règle
          </Button>
        </div>
        {routingRules.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune règle de routage définie pour cette direction.</p>
        ) : (
          <div className="divide-y divide-border/40">
            {routingRules.map((r) => (
              <div key={r.id} className="flex items-center justify-between gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{r.name}</p>
                  <p className="text-xs text-muted-foreground">
                    Si <span className="font-mono">{r.conditionField}</span> = <span className="font-mono">{r.conditionValue}</span>
                    {r.targetService && <> → <span className="text-primary">{r.targetService}</span></>}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1">
                  <button
                    onClick={() => toggleRuleMut.mutate({ id: r.id, active: r.active })}
                    className="text-muted-foreground hover:text-foreground"
                    title={r.active ? "Désactiver" : "Activer"}
                  >
                    {r.active ? <ToggleRight className="h-5 w-5 text-primary" /> : <ToggleLeft className="h-5 w-5" />}
                  </button>
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEditRule(r)}>
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    className="h-7 w-7 text-destructive hover:text-destructive"
                    onClick={() => deleteRuleMut.mutate(r.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </GlassCard>

      {/* Dialog créer/modifier règle */}
      <Dialog open={ruleDialog} onOpenChange={(o) => !o && setRuleDialog(false)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{editingRule ? "Modifier la règle" : "Nouvelle règle de routage"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Nom de la règle <span className="text-destructive">*</span></Label>
              <Input value={ruleForm.name} onChange={(e) => setRuleForm(f => ({ ...f, name: e.target.value }))} placeholder="Ex. Pannes critiques → Exploitation" />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Champ</Label>
                <Select value={ruleForm.conditionField} onValueChange={(v) => setRuleForm(f => ({ ...f, conditionField: v as RoutingRule["conditionField"] }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="category">Catégorie</SelectItem>
                    <SelectItem value="priority">Priorité</SelectItem>
                    <SelectItem value="source">Canal source</SelectItem>
                    <SelectItem value="keyword">Mot-clé</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Valeur</Label>
                <Input value={ruleForm.conditionValue} onChange={(e) => setRuleForm(f => ({ ...f, conditionValue: e.target.value }))} placeholder="Ex. panne, critical…" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Service cible</Label>
              <Select value={ruleForm.targetService || "__none__"} onValueChange={(v) => setRuleForm(f => ({ ...f, targetService: v === "__none__" ? "" : v }))}>
                <SelectTrigger><SelectValue placeholder="Choisir un service" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">— Aucun service spécifique —</SelectItem>
                  {myUnits.map((u) => <SelectItem key={u.id} value={u.code ?? u.id}>{u.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={ruleForm.autoAssign} onCheckedChange={(v) => setRuleForm(f => ({ ...f, autoAssign: v }))} />
              <Label>Assignation automatique à un agent</Label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRuleDialog(false)}>Annuler</Button>
            <Button
              className="gradient-primary"
              disabled={!ruleForm.name.trim() || !ruleForm.conditionValue.trim() || saveRuleMut.isPending}
              onClick={() => saveRuleMut.mutate()}
            >
              {saveRuleMut.isPending ? "Enregistrement…" : (editingRule ? "Mettre à jour" : "Créer")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
