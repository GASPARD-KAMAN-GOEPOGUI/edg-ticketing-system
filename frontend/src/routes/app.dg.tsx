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
import type { EscalationItem } from "@/lib/mock-data";
import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchRequests } from "@/lib/api/requests";
import { fetchDirections } from "@/lib/api/directions-units";
import { fetchEscalations, reviewEscalation, resolveEscalation } from "@/lib/api/escalations";
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
  Megaphone,
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
  "new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened",
]);

const ALL_DIRECTIONS_VALUE = "all";

const STATUS_BUCKETS = [
  { key: "new", label: "Nouveaux", hint: "Créés hors qualification", tone: "border-info/30 bg-info/10 text-info" },
  { key: "qualifying", label: "À qualifier", hint: "Dans la file d'orientation", tone: "border-warning/40 bg-warning/15 text-warning-foreground dark:text-warning" },
  { key: "assigned", label: "Affectés", hint: "Orientés ou assignés", tone: "border-primary/30 bg-primary/10 text-primary" },
  { key: "inProgress", label: "En traitement", hint: "Traitement actif ou rouvert", tone: "border-accent/30 bg-accent/10 text-accent-foreground" },
  { key: "pending", label: "En validation", hint: "Attente de validation", tone: "border-muted-foreground/30 bg-muted/20 text-muted-foreground" },
  { key: "resolved", label: "Résolus", hint: "Résolution proposée", tone: "border-success/30 bg-success/10 text-success" },
  { key: "closed", label: "Fermés", hint: "Clôture confirmée", tone: "border-success/40 bg-success/15 text-success" },
  { key: "escalated", label: "Escaladés", hint: "Escalade active", tone: "border-destructive/30 bg-destructive/10 text-destructive" },
] as const;

const levelTone: Record<EscalationItem["level"], string> = {
  L1: "bg-info/15 text-info",
  L2: "bg-warning/20 text-warning-foreground dark:text-warning",
  L3: "bg-destructive/15 text-destructive",
};

function slaColorClass(pct: number) {
  if (pct >= 90) return "border-success/30 bg-success/15 text-success";
  if (pct >= 75) return "border-warning/40 bg-warning/20 text-warning-foreground dark:text-warning";
  return "border-destructive/30 bg-destructive/15 text-destructive";
}

function GlobalView() {
  const qc = useQueryClient();
  const sessionUser = useUser();

  // ── État annonce globale ───────────────────────────────────────────────────────
  const [annTitle, setAnnTitle] = useState("");
  const [annBody, setAnnBody] = useState("");
  const [annPriority, setAnnPriority] = useState<"low" | "medium" | "high" | "critical">("medium");
  const [annCategory, setAnnCategory] = useState<"general" | "maintenance" | "incident" | "information" | "urgence">("general");

  const annMut = useMutation({
    mutationFn: () =>
      apiFetch("/announcements", {
        method: "POST",
        body: JSON.stringify({
          title: annTitle.trim(),
          description: annBody.trim(),
          announcement_category: annCategory,
          announcement_priority: annPriority,
          announcement_status: "published",
          audience: "all",
          author_id: sessionUser?.id ?? "",
          channel_names: ["in_app"],
          role_names: [],
          direction_ids: [],
        }),
      }),
    onSuccess: () => {
      toast.success("Annonce publiée sur toute la plateforme.");
      setAnnTitle("");
      setAnnBody("");
      setAnnPriority("medium");
      setAnnCategory("general");
    },
    onError: () => toast.error("Erreur lors de la publication de l'annonce."),
  });

  const [arbitrageOpen, setArbitrageOpen] = useState(false);
  const [arbitrageEsc, setArbitrageEsc] = useState<EscalationItem | null>(null);
  const [arbitrageComment, setArbitrageComment] = useState("");
  const [arbitrageAction, setArbitrageAction] = useState<"resolve" | "reject">("resolve");
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

  const { data: escData, isLoading: loadEsc } = useQuery({
    queryKey: ["global-escalations"],
    queryFn: () => fetchEscalations({ limit: 100 }),
    staleTime: 30_000,
  });
  const escalations: EscalationItem[] = escData?.items ?? [];

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
    qc.invalidateQueries({ queryKey: ["global-escalations"] });
    qc.invalidateQueries({ queryKey: ["global-requests"] });
    qc.invalidateQueries({ queryKey: ["escalations"] });
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };

  const requestIdsInScope = useMemo(() => new Set(items.map((r) => r.id)), [items]);
  const scopedEscalations = useMemo(
    () =>
      directionFilter
        ? escalations.filter((e) => e.requestId && requestIdsInScope.has(e.requestId))
        : escalations,
    [directionFilter, escalations, requestIdsInScope],
  );

  // ── KPIs ─────────────────────────────────────────────────────────────────────
  const resolvedCount = items.filter((r) => ["resolved", "closed"].includes(r.status)).length;
  const overdue = items.filter((r) => r.slaElapsed > r.slaHours).length;
  const criticalOverdue = items.filter((r) => r.slaElapsed > r.slaHours && r.priority === "critical").length;
  const slaActive = items.filter((r) => ACTIVE_STATUSES.has(r.status));
  const slaGlobal =
    slaActive.length > 0
      ? Math.round((slaActive.filter((r) => r.slaElapsed <= r.slaHours).length / slaActive.length) * 100)
      : 100;
  const pendingEsc = scopedEscalations.filter((e) => e.status !== "resolved");
  const closedEsc = useMemo(
    () => scopedEscalations.filter((e) => e.status === "resolved").sort(
      (a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()
    ),
    [scopedEscalations],
  );

  const statusSummary = useMemo(() => {
    const activeEscalatedRequestIds = new Set(
      scopedEscalations
        .filter((e) => e.status !== "resolved" && e.requestId)
        .map((e) => e.requestId as string),
    );
    const summary = {
      total,
      new: 0,
      qualifying: 0,
      assigned: 0,
      inProgress: 0,
      pending: 0,
      resolved: 0,
      closed: 0,
      escalated: 0,
    };

    items.forEach((r) => {
      if (r.status === "closed") summary.closed += 1;
      else if (r.status === "resolved") summary.resolved += 1;
      else if (r.status === "pending") summary.pending += 1;
      else if (r.status === "in_progress" || r.status === "reopened") summary.inProgress += 1;
      else if (r.status === "assigned" || r.status === "qualified") summary.assigned += 1;
      else if (r.inTriage || r.status === "qualifying") summary.qualifying += 1;
      else if (r.status === "new") summary.new += 1;

      if (r.status === "escalated" || activeEscalatedRequestIds.has(r.id)) {
        summary.escalated += 1;
      }
    });

    return summary;
  }, [items, scopedEscalations, total]);

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

  // ── Escalations sorted by urgency ─────────────────────────────────────────────
  const sortedEsc = useMemo(
    () => [...scopedEscalations].sort((a, b) => b.slaOverHours - a.slaOverHours),
    [scopedEscalations],
  );

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

  // ── Mutations ─────────────────────────────────────────────────────────────────
  const reviewMut = useMutation({
    mutationFn: (id: string) => reviewEscalation(id),
    onSuccess: () => { toast.success("Escalade prise en revue"); invalidate(); },
    onError: () => toast.error("Impossible de prendre en revue"),
  });

  const arbitrageMut = useMutation({
    mutationFn: async () => {
      if (!arbitrageEsc) throw new Error("Aucune escalade sélectionnée");
      await resolveEscalation(arbitrageEsc.id, {
        comment: arbitrageComment.trim() || undefined,
        action: arbitrageAction,
      });
    },
    onSuccess: () => {
      const msg =
        arbitrageAction === "resolve"
          ? "Décision validée — escalade clôturée"
          : "Escalade rejetée — dossier retourné";
      toast.success(msg);
      setArbitrageOpen(false);
      setArbitrageEsc(null);
      setArbitrageComment("");
      invalidate();
    },
    onError: () => toast.error("Erreur lors de l'arbitrage"),
  });

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
            {" "}— Vue globale en lecture seule. Arbitrage des escalades de direction uniquement.
          </span>
        </p>
      </div>

      <header>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Vue globale</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Tableau de bord global —{" "}
          {loadReq ? "chargement…" : `${total} demandes · ${scopeLabel}`}.
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
              {scopeDetail}. Ce filtre pilote les tickets, les statuts, les escalades visibles et le rapport.
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

      {/* Panneau annonce globale */}
      <GlassCard className="p-4">
        <div className="mb-3 flex items-center gap-2">
          <Megaphone className="h-4 w-4 text-primary" />
          <span className="text-sm font-semibold">Annonce globale</span>
          <span className="text-xs text-muted-foreground">
            — diffusée à toute la plateforme (tous rôles)
          </span>
        </div>
        <div className="space-y-3">
          <Input
            placeholder="Titre de l'annonce"
            value={annTitle}
            onChange={(e) => setAnnTitle(e.target.value)}
            className="rounded-xl"
          />
          <div className="flex flex-col gap-2 sm:flex-row">
            <Textarea
              placeholder="Contenu du message…"
              value={annBody}
              onChange={(e) => setAnnBody(e.target.value)}
              className="min-h-[80px] flex-1 resize-none rounded-xl"
              rows={3}
            />
            <div className="flex flex-row flex-wrap gap-2 sm:flex-col sm:flex-nowrap">
              <Select
                value={annCategory}
                onValueChange={(v) =>
                  setAnnCategory(v as "general" | "maintenance" | "incident" | "information" | "urgence")
                }
              >
                <SelectTrigger className="w-full rounded-xl sm:w-[130px]">
                  <SelectValue placeholder="Catégorie" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="general">Général</SelectItem>
                  <SelectItem value="information">Information</SelectItem>
                  <SelectItem value="maintenance">Maintenance</SelectItem>
                  <SelectItem value="incident">Incident</SelectItem>
                  <SelectItem value="urgence">Urgence</SelectItem>
                </SelectContent>
              </Select>
              <Select
                value={annPriority}
                onValueChange={(v) => setAnnPriority(v as "low" | "medium" | "high" | "critical")}
              >
                <SelectTrigger className="w-full rounded-xl sm:w-[130px]">
                  <SelectValue placeholder="Priorité" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="low">Basse</SelectItem>
                  <SelectItem value="medium">Normale</SelectItem>
                  <SelectItem value="high">Haute</SelectItem>
                  <SelectItem value="critical">Urgente</SelectItem>
                </SelectContent>
              </Select>
              <Button
                className="gradient-primary w-full rounded-xl sm:w-auto"
                disabled={!annTitle.trim() || !annBody.trim() || annMut.isPending}
                onClick={() => annMut.mutate()}
              >
                {annMut.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                <span className="ml-1.5">Publier</span>
              </Button>
            </div>
          </div>
        </div>
      </GlassCard>

      {/* KPIs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 stagger">
        <GlassCard className="space-y-1">
          <div className="text-sm text-muted-foreground">Total demandes</div>
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
        <GlassCard className="space-y-1">
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <ArrowUpRight className="h-3.5 w-3.5 text-warning" /> Escalades direction
          </div>
          {loadEsc ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" /> : (
            <>
              <div className="text-3xl font-bold text-warning">{pendingEsc.length}</div>
              <div className="text-xs text-muted-foreground">en attente d'arbitrage</div>
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

      {/* Section escalades direction */}
      <GlassCard className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Escalades direction</h2>
            <p className="text-xs text-muted-foreground">
              {loadEsc
                ? "Chargement…"
                : `${sortedEsc.length} escalade${sortedEsc.length !== 1 ? "s" : ""} — triées par urgence délai décroissante`}
            </p>
          </div>
        </div>

        {loadEsc ? (
          <div className="flex h-24 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/40" />
          </div>
        ) : sortedEsc.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Aucune escalade de direction en cours.</p>
        ) : (
          <ul className="space-y-2">
            {sortedEsc.map((e) => (
              <li
                key={e.id}
                className="flex flex-wrap items-start gap-3 rounded-2xl border border-border/40 bg-card/40 p-3 transition hover:border-primary/40"
              >
                <span
                  className={cn(
                    "mt-0.5 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wider",
                    levelTone[e.level],
                  )}
                >
                  {e.level}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {e.requestId ? (
                      <Link
                        to="/app/dg/tickets/$id"
                        params={{ id: e.requestId }}
                        className="font-mono text-[11px] text-primary hover:underline"
                      >
                        {e.requestRef}
                      </Link>
                    ) : (
                      <span className="font-mono text-[11px] text-muted-foreground">{e.requestRef}</span>
                    )}
                    <Badge variant="outline" className="text-[10px]">{e.priority}</Badge>
                    {e.status === "resolved" && (
                      <Badge className="bg-success/15 text-success">Clôturée</Badge>
                    )}
                    {e.status === "in_review" && (
                      <Badge className="bg-warning/20 text-warning-foreground dark:text-warning">En revue</Badge>
                    )}
                  </div>
                  <div className="mt-0.5 text-sm font-medium">{e.title}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {e.fromAgent} → <span className="font-medium text-foreground/80">{e.toAgent}</span>
                    {" · "}{e.reason}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">Délai dépassé</div>
                    <div className="text-sm font-semibold text-destructive">+{e.slaOverHours}h</div>
                  </div>
                  {e.status !== "resolved" && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.status === "open" && (
                        <Button
                          size="sm"
                          variant="outline"
                          className="h-7 rounded-full px-2.5 text-xs"
                          disabled={reviewMut.isPending}
                          onClick={() => reviewMut.mutate(e.id)}
                        >
                          Examiner
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="h-7 rounded-full px-2.5 text-xs gradient-primary text-background"
                        onClick={() => {
                          setArbitrageEsc(e);
                          setArbitrageComment("");
                          setArbitrageAction("resolve");
                          setArbitrageOpen(true);
                        }}
                      >
                        <CheckCircle2 className="mr-1 h-3 w-3" /> Arbitrer
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        className="h-7 rounded-full px-2.5 text-xs border-destructive/40 text-destructive hover:bg-destructive/10"
                        onClick={() => {
                          setArbitrageEsc(e);
                          setArbitrageComment("");
                          setArbitrageAction("reject");
                          setArbitrageOpen(true);
                        }}
                      >
                        <XCircle className="mr-1 h-3 w-3" /> Rejeter
                      </Button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </GlassCard>

      {/* Historique des arbitrages */}
      <GlassCard className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Historique des arbitrages</h2>
            <p className="text-xs text-muted-foreground">
              {loadEsc
                ? "Chargement…"
                : `${closedEsc.length} arbitrage${closedEsc.length !== 1 ? "s" : ""} clôturé${closedEsc.length !== 1 ? "s" : ""}`}
            </p>
          </div>
        </div>
        {loadEsc ? (
          <div className="flex h-16 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/40" />
          </div>
        ) : closedEsc.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            Aucun arbitrage clôturé pour l'instant.
          </p>
        ) : (
          <ul className="space-y-2">
            {closedEsc.map((e) => (
              <li
                key={e.id}
                className="flex flex-wrap items-start gap-3 rounded-2xl border border-success/20 bg-success/5 p-3"
              >
                <span className={cn("mt-0.5 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wider", levelTone[e.level])}>
                  {e.level}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {e.requestId ? (
                      <Link
                        to="/app/dg/tickets/$id"
                        params={{ id: e.requestId }}
                        className="font-mono text-[11px] text-primary hover:underline"
                      >
                        {e.requestRef}
                      </Link>
                    ) : (
                      <span className="font-mono text-[11px] text-muted-foreground">{e.requestRef}</span>
                    )}
                    <Badge className="bg-success/15 text-success text-[10px]">Clôturée</Badge>
                    <Badge variant="outline" className="text-[10px]">{e.priority}</Badge>
                  </div>
                  <div className="mt-0.5 text-sm font-medium">{e.title}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {e.fromAgent} → <span className="font-medium text-foreground/80">{e.toAgent}</span>
                    {" · "}{formatDistanceToNow(new Date(e.at), { addSuffix: true, locale: fr })}
                  </div>
                  {e.decisionComment && (
                    <div className="mt-1.5 rounded-xl border border-primary/20 bg-primary/5 px-3 py-2 text-xs text-foreground/80">
                      <span className="font-semibold text-primary">Décision :</span>{" "}{e.decisionComment}
                    </div>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <CheckCircle2 className="h-4 w-4 text-success" />
                </div>
              </li>
            ))}
          </ul>
        )}
      </GlassCard>

      {/* Carte thermique SLA par direction */}
      <GlassCard>
        <h2 className="mb-4 font-semibold">Carte thermique des délais par direction</h2>
        {loadReq ? (
          <div className="flex h-24 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
          </div>
        ) : dirStats.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune donnée disponible.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {dirStats.map((s) => (
              <div
                key={s.id}
                className={cn("rounded-2xl border px-4 py-3", slaColorClass(s.slaRespect))}
              >
                <div className="text-xs font-medium">{directionLookup[s.id] ?? s.id}</div>
                <div className="mt-1 text-2xl font-bold">{s.slaRespect}%</div>
                <div className="mt-0.5 text-[11px] opacity-80">
                  {s.total} demandes · {s.overdue} hors délai
                </div>
              </div>
            ))}
          </div>
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
                          Aucune demande pour cette direction.
                        </div>
                      )}
                    </div>

                    {/* Liste demandes cliquables */}
                    <div>
                      <h3 className="mb-3 text-sm font-semibold">
                        Demandes récentes ({dirReqs.length})
                      </h3>
                      <div className="max-h-[200px] space-y-2 overflow-y-auto">
                        {dirReqs.length === 0 ? (
                          <p className="text-sm text-muted-foreground">Aucune demande.</p>
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

      {/* Dialog arbitrage */}
      <Dialog open={arbitrageOpen} onOpenChange={setArbitrageOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>
              {arbitrageAction === "resolve" ? "Arbitrage — Valider" : "Arbitrage — Rejeter"}
            </DialogTitle>
            <DialogDescription>
              Escalade {arbitrageEsc?.requestRef}. Un commentaire d'arbitrage est obligatoire.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>
              Commentaire d'arbitrage <span className="text-destructive">*</span>
            </Label>
            <Textarea
              value={arbitrageComment}
              onChange={(e) => setArbitrageComment(e.target.value)}
              placeholder={
                arbitrageAction === "resolve"
                  ? "Décision : validation et motif…"
                  : "Motif du rejet et instructions de retour…"
              }
              className="resize-none"
              rows={4}
            />
          </div>
          <DialogFooter>
            <Button
              variant="ghost"
              className="rounded-full"
              onClick={() => setArbitrageOpen(false)}
            >
              Annuler
            </Button>
            <Button
              className={cn(
                "rounded-full",
                arbitrageAction === "resolve"
                  ? "gradient-primary"
                  : "bg-destructive text-destructive-foreground hover:bg-destructive/90",
              )}
              disabled={!arbitrageComment.trim() || arbitrageMut.isPending}
              onClick={() => arbitrageMut.mutate()}
            >
              {arbitrageMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              {arbitrageAction === "resolve" ? "Valider la décision" : "Confirmer le rejet"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
