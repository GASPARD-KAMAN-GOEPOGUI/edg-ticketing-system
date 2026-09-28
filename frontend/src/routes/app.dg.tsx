import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useUser } from "@/lib/session";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge } from "@/components/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { statusLabels } from "@/lib/mock-data";
import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRequests } from "@/lib/api/requests";
import { fetchDirections } from "@/lib/api/directions-units";
import { fetchCsatByDirection } from "@/lib/api/csat";
import { downloadReport, type ExportFormat } from "@/lib/api/reports";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import {
  Info,
  AlertTriangle,
  Loader2,
  ArrowUpRight,
  CheckCircle2,
  Star,
  XCircle,
  Send,
  Building2,
  Download,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { apiFetch } from "@/lib/api/client";

export const Route = createFileRoute("/app/dg")({
  beforeLoad: () => requireRole("admin"),
  head: () => ({ meta: [{ title: "Vue globale — EDG Support" }] }),
  component: GlobalView,
});

const PIE_COLORS = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
];

const ACTIVE_STATUSES = new Set([
  "new", "qualifying", "assigned", "in_progress", "reopened",
]);

const ALL_DIRECTIONS_VALUE = "all";

const STATUS_BUCKETS = [
  { key: "new", label: "Nouveaux", hint: "Créés hors qualification", tone: "border-info/30 bg-info/10 text-info" },
  { key: "qualifying", label: "À qualifier", hint: "Dans la file d'orientation", tone: "border-warning/40 bg-warning/15 text-warning-foreground dark:text-warning" },
  { key: "assigned", label: "Affectés", hint: "Orientés ou assignés", tone: "border-primary/30 bg-primary/10 text-primary" },
  { key: "inProgress", label: "En traitement", hint: "Traitement actif ou rouvert", tone: "border-accent/30 bg-accent/10 text-accent-foreground" },
  { key: "resolved", label: "Résolus", hint: "Résolution proposée", tone: "border-success/30 bg-success/10 text-success" },
  { key: "closed", label: "Fermés", hint: "Clôture confirmée", tone: "border-success/40 bg-success/15 text-success" },
] as const;

function GlobalView() {
  const qc = useQueryClient();
  const sessionUser = useUser();

  const [selectedDirectionId, setSelectedDirectionId] = useState(ALL_DIRECTIONS_VALUE);
  const [reportFormat, setReportFormat] = useState<ExportFormat>("excel");
  const [isExporting, setIsExporting] = useState(false);

  const directionFilter =
    selectedDirectionId === ALL_DIRECTIONS_VALUE ? undefined : selectedDirectionId;

  // ── Queries ───────────────────────────────────────────────────────────────────
  const { data: reqData, isLoading: loadReq } = useQuery({
    queryKey: ["global-requests", directionFilter ?? ALL_DIRECTIONS_VALUE],
    queryFn: () => fetchRequests({ limit: 1000, direction_id: directionFilter }),
    staleTime: 30_000,
  });
  const items = reqData?.items ?? [];
  const total = reqData?.total ?? items.length;

  const { data: directionsData = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });
  const directionLookup = Object.fromEntries(directionsData.map((d) => [d.id, d.name]));
  const selectedDirection = directionsData.find((d) => d.id === selectedDirectionId);
  const scopeLabel = directionFilter
    ? selectedDirection?.name ?? "Direction sélectionnée"
    : "Toutes les directions";
  const scopeDetail = directionFilter
    ? "Données limitées à la direction sélectionnée"
    : "Vue consolidée de toutes les directions EDG";

  const { data: csatByDir } = useQuery({
    queryKey: ["csat-by-direction"],
    queryFn: fetchCsatByDirection,
    staleTime: 300_000,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["global-requests"] });
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };

  // ── KPIs ─────────────────────────────────────────────────────────────────────
  const resolvedCount = items.filter((r) => ["resolved", "closed"].includes(r.status)).length;
  const overdue = items.filter((r) => r.slaElapsed > r.slaHours).length;
  const criticalOverdue = items.filter((r) => r.slaElapsed > r.slaHours && r.priority === "critical").length;
  const slaActive = items.filter((r) => ACTIVE_STATUSES.has(r.status));
  const slaGlobal =
    slaActive.length > 0
      ? Math.round((slaActive.filter((r) => r.slaElapsed <= r.slaHours).length / slaActive.length) * 100)
      : 100;
  const statusSummary = useMemo(() => {
    const summary = {
      total,
      new: 0,
      qualifying: 0,
      assigned: 0,
      inProgress: 0,
      resolved: 0,
      closed: 0,
    };

    items.forEach((r) => {
      if (r.status === "closed") summary.closed += 1;
      else if (r.status === "resolved") summary.resolved += 1;
      else if (r.status === "in_progress" || r.status === "reopened") summary.inProgress += 1;
      else if (r.status === "assigned") summary.assigned += 1;
      else if (r.inTriage || r.status === "qualifying") summary.qualifying += 1;
      else if (r.status === "new") summary.new += 1;
    });

    return summary;
  }, [items, total]);

  const statusChartData = STATUS_BUCKETS.map((bucket) => ({
    name: bucket.label,
    value: statusSummary[bucket.key],
  }));

  // ── Stats par direction (computed from real requests) ─────────────────────────
  const dirStats = useMemo(() => {
    const map = new Map<string, { open: number; resolved: number; total: number; overdue: number; slaOk: number }>();
    items.forEach((r) => {
      const did = r.directionId ?? "unknown";
      const entry = map.get(did) ?? { open: 0, resolved: 0, total: 0, overdue: 0, slaOk: 0 };
      entry.total += 1;
      if (ACTIVE_STATUSES.has(r.status)) {
        entry.open += 1;
        if (r.slaElapsed <= r.slaHours) entry.slaOk += 1;
      }
      if (["resolved", "closed"].includes(r.status)) entry.resolved += 1;
      if (r.slaElapsed > r.slaHours) entry.overdue += 1;
      map.set(did, entry);
    });
    return [...map.entries()].map(([id, s]) => ({
      id,
      open: s.open,
      resolved: s.resolved,
      total: s.total,
      overdue: s.overdue,
      slaRespect: s.open > 0 ? Math.round((s.slaOk / s.open) * 100) : 100,
    }));
  }, [items]);

  const directionIds = dirStats.map((s) => s.id);

  const barData = dirStats.map((s) => ({
    name: (directionLookup[s.id] ?? s.id).substring(0, 12),
    Ouvertes: s.open,
    Résolues: s.resolved,
  }));

  const scopedCsatByDir = useMemo(() => {
    if (!csatByDir) return [];
    if (!directionFilter) return csatByDir;
    return csatByDir.filter(
      (c) =>
        String(c.entity_id) === directionFilter ||
        c.label === selectedDirection?.name ||
        c.label === selectedDirection?.code,
    );
  }, [csatByDir, directionFilter, selectedDirection]);

  const handleDirectionReportExport = async () => {
    setIsExporting(true);
    try {
      await downloadReport(
        "by-unity",
        reportFormat,
        directionFilter ? { direction_id: directionFilter } : {},
      );
      toast.success(
        directionFilter
          ? `Rapport généré pour ${scopeLabel}.`
          : "Rapport consolidé généré pour toutes les directions.",
      );
    } catch {
      toast.error("Impossible de générer le rapport demandé.");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6 animate-fade-in">
      {/* Bandeau supervision */}
      <div className="flex items-start gap-3 rounded-2xl border border-info/30 bg-info/10 px-5 py-3.5">
        <Info className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <p className="text-sm">
          <span className="font-semibold text-info">Mode supervision</span>
          <span className="text-muted-foreground">
            {" "}— Vue globale en lecture seule.
          </span>
        </p>
      </div>

      <header>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Vue globale</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tableau de bord global —{" "}
          {loadReq ? "chargement…" : `${total} tickets · ${scopeLabel}`}.
        </p>
      </header>

      {/* Périmètre de pilotage administratif */}
      <GlassCard className="p-4">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold">Périmètre supervisé</span>
            </div>
            <p className="max-w-2xl text-xs text-muted-foreground">
              {scopeDetail}. Ce filtre pilote les tickets, les statuts visibles et le rapport.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <div className="min-w-[240px] space-y-1.5">
              <Label className="text-xs">Direction</Label>
              <Select value={selectedDirectionId} onValueChange={setSelectedDirectionId}>
                <SelectTrigger className="rounded-xl">
                  <SelectValue placeholder="Toutes les directions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL_DIRECTIONS_VALUE}>Toutes les directions</SelectItem>
                  {directionsData
                    .filter((direction) => direction.status)
                    .map((direction) => (
                      <SelectItem key={direction.id} value={direction.id}>
                        {direction.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex gap-2">
              <div className="w-[130px] space-y-1.5">
                <Label className="text-xs">Format</Label>
                <Select value={reportFormat} onValueChange={(v) => setReportFormat(v as ExportFormat)}>
                  <SelectTrigger className="rounded-xl">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="excel">Excel</SelectItem>
                    <SelectItem value="csv">CSV</SelectItem>
                    <SelectItem value="pdf">PDF</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <Button
                  variant="outline"
                  className="rounded-xl"
                  disabled={isExporting}
                  onClick={handleDirectionReportExport}
                >
                  {isExporting ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Download className="mr-2 h-4 w-4" />
                  )}
                  Rapport
                </Button>
              </div>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 stagger">
        <GlassCard className="space-y-1">
          <div className="text-sm text-muted-foreground">Total tickets</div>
          {loadReq ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" /> : (
            <div className="text-3xl font-bold">{total}</div>
          )}
        </GlassCard>
        <GlassCard className="space-y-1">
          <div className="text-sm text-muted-foreground">Résolues / Clôturées</div>
          {loadReq ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" /> : (
            <>
              <div className="text-3xl font-bold text-success">{resolvedCount}</div>
              <div className="text-xs text-muted-foreground">
                {total > 0 ? Math.round((resolvedCount / total) * 100) : 0}% du total
              </div>
            </>
          )}
        </GlassCard>
        <GlassCard className="space-y-1">
          <div className="text-sm text-muted-foreground">Respect délai global</div>
          {loadReq ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" /> : (
            <div
              className={cn(
                "text-3xl font-bold",
                slaGlobal >= 90 ? "text-success" : slaGlobal >= 75 ? "text-warning" : "text-destructive",
              )}
            >
              {slaGlobal}%
            </div>
          )}
        </GlassCard>
        <GlassCard className="space-y-1">
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <AlertTriangle className="h-3.5 w-3.5 text-destructive" /> Hors délai
          </div>
          {loadReq ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" /> : (
            <>
              <div className="text-3xl font-bold text-destructive">{overdue}</div>
              <div className="text-xs text-muted-foreground">
                dont {criticalOverdue} critique{criticalOverdue !== 1 ? "s" : ""}
              </div>
            </>
          )}
        </GlassCard>
      </div>

      {/* Tickets regroupés par statut */}
      <GlassCard className="space-y-5 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Tickets par statut</h2>
            <p className="text-xs text-muted-foreground">
              {loadReq ? "Chargement…" : `${statusSummary.total} ticket${statusSummary.total !== 1 ? "s" : ""} · ${scopeLabel}`}
            </p>
          </div>
          <Badge variant="outline" className="rounded-full px-3 py-1 text-xs">
            {scopeLabel}
          </Badge>
        </div>

        {loadReq ? (
          <div className="flex h-28 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
          </div>
        ) : (
          <>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {STATUS_BUCKETS.map((bucket) => (
                <div
                  key={bucket.key}
                  className={cn("rounded-2xl border px-4 py-3", bucket.tone)}
                >
                  <div className="text-[11px] font-semibold uppercase tracking-wide opacity-80">
                    {bucket.label}
                  </div>
                  <div className="mt-1 text-2xl font-bold">{statusSummary[bucket.key]}</div>
                  <div className="mt-0.5 text-[11px] opacity-75">{bucket.hint}</div>
                </div>
              ))}
            </div>
            <ResponsiveContainer width="100%" height={230}>
              <BarChart data={statusChartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="value" name="Tickets" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </>
        )}
      </GlassCard>

      {/* CSAT par direction */}
      {scopedCsatByDir.length > 0 && (
        <GlassCard>
          <h2 className="mb-4 font-semibold">CSAT par direction</h2>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {scopedCsatByDir.map((c) => (
              <div
                key={c.entity_id}
                className="rounded-2xl border border-border/40 bg-card/50 px-4 py-3"
              >
                <div className="flex items-center gap-1.5">
                  <Star className="h-3.5 w-3.5 text-warning" />
                  <div className="truncate text-xs font-medium text-muted-foreground">
                    {c.label || c.entity_id.toUpperCase()}
                  </div>
                </div>
                <div className="mt-1 text-2xl font-bold">
                  {c.avg > 0 ? c.avg.toFixed(1) : "—"}
                  <span className="text-sm font-normal text-muted-foreground">/5</span>
                </div>
                <div className="text-[11px] text-muted-foreground">{c.count} avis</div>
              </div>
            ))}
          </div>
        </GlassCard>
      )}

      {/* BarChart comparatif */}
      {barData.length > 0 && (
        <GlassCard>
          <h2 className="mb-4 font-semibold">Comparatif ouvertes / résolues par direction</h2>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={barData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" className="opacity-20" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="Ouvertes" fill="var(--color-chart-3)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Résolues" fill="var(--color-chart-1)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </GlassCard>
      )}

      {/* Tabs par direction */}
      {directionIds.length > 0 && (
        <GlassCard className="overflow-hidden p-0">
          <div className="p-5 pb-0">
            <h2 className="font-semibold">Vue détaillée par direction</h2>
          </div>
          <Tabs key={directionIds.join("|")} defaultValue={directionIds[0]} className="p-5 pt-4">
            <TabsList className="h-auto flex-wrap gap-1 bg-transparent">
              {directionIds.map((did) => (
                <TabsTrigger key={did} value={did} className="rounded-full text-xs">
                  {directionLookup[did] ?? did}
                </TabsTrigger>
              ))}
            </TabsList>

            {directionIds.map((did) => {
              const dirReqs = items.filter((r) => r.directionId === did);
              const grouped = Object.entries(
                dirReqs.reduce<Record<string, number>>((acc, r) => {
                  acc[r.status] = (acc[r.status] || 0) + 1;
                  return acc;
                }, {}),
              ).map(([k, v]) => ({
                name: statusLabels[k as keyof typeof statusLabels] ?? k,
                value: v,
              }));

              return (
                <TabsContent key={did} value={did} className="mt-4 space-y-4">
                  <div className="grid gap-4 lg:grid-cols-2">
                    {/* Pie chart */}
                    <div>
                      <h3 className="mb-3 text-sm font-semibold">Répartition par statut</h3>
                      {dirReqs.length > 0 ? (
                        <ResponsiveContainer width="100%" height={200}>
                          <PieChart>
                            <Pie
                              data={grouped}
                              cx="50%"
                              cy="50%"
                              innerRadius={48}
                              outerRadius={76}
                              paddingAngle={3}
                              dataKey="value"
                            >
                              {grouped.map((_, i) => (
                                <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                              ))}
                            </Pie>
                            <Tooltip contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                            <Legend wrapperStyle={{ fontSize: 11 }} />
                          </PieChart>
                        </ResponsiveContainer>
                      ) : (
                        <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
                          Aucun ticket pour cette direction.
                        </div>
                      )}
                    </div>

                    {/* Liste demandes cliquables */}
                    <div>
                      <h3 className="mb-3 text-sm font-semibold">
                        Tickets récents ({dirReqs.length})
                      </h3>
                      <div className="max-h-[200px] space-y-2 overflow-y-auto">
                        {dirReqs.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Aucun ticket.</p>
                        ) : (
                          dirReqs.slice(0, 8).map((r) => (
                            <Link
                              key={r.id}
                              to="/app/dg/tickets/$id"
                              params={{ id: r.id }}
                              className="flex items-center gap-3 rounded-xl border border-border/40 bg-background/40 p-2.5 text-sm transition hover:border-primary/40 hover:bg-primary/5"
                            >
                              <StatusBadge status={r.status} />
                              <span className="min-w-0 flex-1 truncate font-medium">{r.title}</span>
                              <span className="shrink-0 text-xs text-muted-foreground">
                                {formatDistanceToNow(new Date(r.createdAt), {
                                  addSuffix: true,
                                  locale: fr,
                                })}
                              </span>
                            </Link>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </TabsContent>
              );
            })}
          </Tabs>
        </GlassCard>
      )}

    </div>
  );
}
