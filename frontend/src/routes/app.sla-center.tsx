import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { usePagination, PaginationBar } from "@/components/pagination-bar";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Download,
  FileSpreadsheet,
  FileText,
  Flame,
  LayoutList,
  Loader2,
  MoreHorizontal,
  RotateCcw,
  Users,
  Send,
  Timer,
} from "lucide-react";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchRequests } from "@/lib/api/requests";
import { fetchSlaReopenStats, fetchInterventionStats, downloadReport, type ExportFormat } from "@/lib/api/reports";
import type { RequestItem, RequestStatus } from "@/lib/mock-data";
import { requireRole } from "@/lib/auth-guard";
import { useRole, useUser } from "@/lib/session";
import { fetchDirections, fetchUnit, fetchUnits } from "@/lib/api/directions-units";
import type { Unit } from "@/lib/api/directions-units";
import { toast } from "sonner";
import { formatElapsedHours } from "@/lib/utils";

export const Route = createFileRoute("/app/sla-center")({
  beforeLoad: () => requireRole("admin"),
  head: () => ({ meta: [{ title: "Centre SLA — EDG Support" }] }),
  component: SlaCenterPage,
});

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTIVE_STATUSES: RequestStatus[] = [
  "new", "qualifying", "assigned", "in_progress", "reopened",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const isActive = (r: RequestItem) => ACTIVE_STATUSES.includes(r.status);

// ── Sub-components ────────────────────────────────────────────────────────────

type KpiCardProps = {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ElementType;
  iconBg: string;
  iconColor: string;
  progress?: number;
  progressColor?: string;
};

function KpiCard({ label, value, sub, icon: Icon, iconBg, iconColor, progress, progressColor }: KpiCardProps) {
  return (
    <div className="glass flex flex-col gap-4 rounded-3xl p-4 transition-shadow duration-200 sm:p-6">
      <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${iconBg}`}>
        <Icon className={`h-5 w-5 ${iconColor}`} />
      </div>
      <div className="space-y-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="text-3xl font-bold leading-none tabular-nums">{value}</p>
        {sub && <p className="text-[11px] text-muted-foreground">{sub}</p>}
      </div>
      {progress !== undefined && (
        <div className="h-1 w-full overflow-hidden rounded-full bg-muted/50">
          <div
            className={`h-full rounded-full transition-all duration-500 ${progressColor ?? "bg-primary"}`}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
      )}
    </div>
  );
}

type GroupRow = {
  id: string;
  label: string;
  total: number;
  avgHours: number;
  totalHours: number;
};

// ── Page ──────────────────────────────────────────────────────────────────────

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}

function SlaCenterPage() {
  const [role] = useRole();
  const sessionUser = useUser();
  // director et chief-departement ont ete retires le 2026-09-25 : cette page
  // est desormais reservee a l'admin (garde de route), donc perimetre global.
  const isDirector = false;
  // chief-service (role supprime) ne peut plus jamais atteindre cette page (garde de route) ;
  // conserve `false` pour ne pas toucher a la logique downstream qui en depend.
  const isChiefService = false;
  const isChief = false;

  // Période d'affichage — par défaut les 30 derniers jours, ajustable librement.
  const [startDate, setStartDate] = useState(() => toISODate(new Date(Date.now() - 30 * 86_400_000)));
  const [endDate, setEndDate] = useState(() => toISODate(new Date()));
  const [exportPending, setExportPending] = useState(false);

  const resetPeriod = () => {
    setStartDate(toISODate(new Date(Date.now() - 30 * 86_400_000)));
    setEndDate(toISODate(new Date()));
  };

  const handleExport = async (fmt: ExportFormat) => {
    setExportPending(true);
    try {
      await downloadReport("sla-center", fmt, { start: startDate, end: endDate });
      toast.success("Export téléchargé.");
    } catch {
      toast.error("Erreur lors de l'export — vérifiez que le backend est démarré.");
    } finally {
      setExportPending(false);
    }
  };

  const filters = useMemo(
    () => ({
      limit: 500,
      date_from: startDate,
      date_to: endDate,
      ...(isDirector && sessionUser?.direction_id
        ? { direction_id: sessionUser.direction_id }
        : isChief && sessionUser?.unit_id
        ? { unit_id: sessionUser.unit_id }
        : {}),
    }),
    [isDirector, isChief, sessionUser?.direction_id, sessionUser?.unit_id, startDate, endDate],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["sla-center", filters],
    queryFn: () => fetchRequests(filters),
    staleTime: 30_000,
  });

  // BR-SLA-REOPEN-001 — statistiques croisées cycles SLA / réouvertures.
  const { data: reopenStats } = useQuery({
    queryKey: ["sla-reopen-stats", startDate, endDate],
    queryFn: () => fetchSlaReopenStats(startDate, endDate),
    staleTime: 60_000,
  });

  // BR-TRACE-001 — statistiques agrégées sur les interventions.
  const { data: interventionStats } = useQuery({
    queryKey: ["intervention-stats", startDate, endDate],
    queryFn: () => fetchInterventionStats(startDate, endDate),
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

  const directionLookup = useMemo(
    () => Object.fromEntries(directionsData.map((d) => [d.id, d.name])),
    [directionsData],
  );
  const baseServiceLookup = useMemo(
    () => Object.fromEntries(unitsData.map((u) => [String(u.id), u.name])),
    [unitsData],
  );

  const allItems = data?.items ?? [];

  const active = useMemo(() => allItems.filter(isActive), [allItems]);

  const visibleServiceIds = useMemo(
    () => Array.from(new Set(active.map((r) => r.serviceId).filter(Boolean) as string[])),
    [active],
  );

  const missingServiceIds = useMemo(
    () => visibleServiceIds.filter((id) => !baseServiceLookup[String(id)]),
    [baseServiceLookup, visibleServiceIds],
  );

  const { data: missingUnits = [] } = useQuery({
    queryKey: ["sla-center-missing-units", missingServiceIds],
    queryFn: async () => {
      const results = await Promise.all(
        missingServiceIds.map(async (id) => {
          try {
            return await fetchUnit(id);
          } catch {
            return null;
          }
        }),
      );
      return results.filter((unit): unit is Unit => unit !== null);
    },
    enabled: missingServiceIds.length > 0,
    staleTime: 5 * 60_000,
  });

  const serviceLookup = useMemo(
    () => ({
      ...baseServiceLookup,
      ...Object.fromEntries(missingUnits.map((u) => [String(u.id), u.name])),
    }),
    [baseServiceLookup, missingUnits],
  );

  const serviceLabel = (serviceId?: string) =>
    serviceId && serviceLookup[String(serviceId)] ? serviceLookup[String(serviceId)] : "—";

  const directionLabel = (directionId?: string) =>
    directionId && directionLookup[directionId] ? directionLookup[directionId] : "—";

  const sortedByDuration = useMemo(
    () => [...active].sort((a, b) => b.slaElapsed - a.slaElapsed),
    [active],
  );

  const critical = useMemo(
    () => active.filter((r) => r.priority === "critical"),
    [active],
  );

  const { page: bPage, setPage: setBPage, totalPages: bTotalPages, paged: pagedActive, total: bTotal, pageSize: bPageSize, setPageSize: setBPageSize } = usePagination(sortedByDuration, 15);

  const avgActiveHours = active.length > 0
    ? active.reduce((sum, r) => sum + (r.slaElapsed ?? 0), 0) / active.length
    : 0;
  const longestActiveHours = sortedByDuration[0]?.slaElapsed ?? 0;

  // Group by direction (DG/admin), by service (director), or by service (chief — one service)
  const groupRows = useMemo<GroupRow[]>(() => {
    const map = new Map<string, RequestItem[]>();
    for (const r of active) {
      const key = (isDirector || isChief) ? (r.serviceId ?? "unknown") : r.directionId;
      const list = map.get(key) ?? [];
      list.push(r);
      map.set(key, list);
    }
    return [...map.entries()]
      .map(([id, items]) => {
        const totalHours = items.reduce((sum, r) => sum + (r.slaElapsed ?? 0), 0);
        return {
          id,
          label: (isDirector || isChief)
            ? serviceLabel(id)
            : directionLabel(id),
          total: items.length,
          avgHours: items.length > 0 ? totalHours / items.length : 0,
          totalHours,
        };
      })
      .sort((a, b) => b.avgHours - a.avgHours);
  }, [active, isDirector, isChief, directionLookup, serviceLookup]);

  if (isLoading) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
        Chargement…
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex h-48 items-center justify-center text-sm text-destructive">
        Erreur lors du chargement des données SLA.
      </div>
    );
  }

  const groupLabel = (isDirector || isChief) ? "service" : "direction";

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Centre SLA</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {isDirector
              ? "Suivi des engagements SLA de votre direction"
              : "Vue d'ensemble SLA — toutes les directions"}
          </p>
        </div>

        {/* Filtre de période + export */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 rounded-2xl border border-border/50 bg-background/60 p-1.5 shadow-sm backdrop-blur">
            <input
              type="date"
              value={startDate}
              max={endDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="h-9 min-w-0 rounded-xl border border-border/40 bg-background/60 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
            <span className="text-xs text-muted-foreground">→</span>
            <input
              type="date"
              value={endDate}
              min={startDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="h-9 min-w-0 rounded-xl border border-border/40 bg-background/60 px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
            />
          </div>
          <Button variant="outline" size="sm" className="rounded-full" onClick={resetPeriod}>
            30 derniers jours
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30"
                disabled={exportPending}
              >
                {exportPending
                  ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                  : <Download className="mr-1.5 h-4 w-4" />}
                Exporter
                <MoreHorizontal className="ml-1 h-3.5 w-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-44">
              <DropdownMenuItem onSelect={() => handleExport("excel")}>
                <FileSpreadsheet className="h-4 w-4" /> Excel
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleExport("csv")}>
                <FileSpreadsheet className="h-4 w-4" /> CSV
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleExport("pdf")}>
                <FileText className="h-4 w-4" /> PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-4">
        <KpiCard
          label="Durée moyenne de traitement"
          value={formatElapsedHours(avgActiveHours)}
          sub="sur les tickets actifs"
          icon={Timer}
          iconBg="bg-primary/10"
          iconColor="text-primary"
        />
        <KpiCard
          label="Tickets actifs"
          value={active.length}
          sub="statuts non terminaux"
          icon={LayoutList}
          iconBg="bg-primary/10"
          iconColor="text-primary"
        />
        <KpiCard
          label="Durée la plus longue"
          value={formatElapsedHours(longestActiveHours)}
          sub="ticket actif le plus ancien en traitement"
          icon={AlertTriangle}
          iconBg="bg-muted"
          iconColor="text-muted-foreground"
        />
        <KpiCard
          label="Critiques actifs"
          value={critical.length}
          sub="priorité critique"
          icon={Flame}
          iconBg={critical.length > 0 ? "bg-orange-500/15" : "bg-muted"}
          iconColor={critical.length > 0 ? "text-orange-600" : "text-muted-foreground"}
        />
      </div>

      {/* BR-SLA-REOPEN-001 — cycles SLA / réouvertures (30 derniers jours) */}
      {reopenStats && (
        <GlassCard>
          <h2 className="mb-4 font-semibold">Réouvertures — {reopenStats.period}</h2>
          <div className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-5">
            <KpiCard
              label="Tickets réouverts"
              value={reopenStats.reopened_tickets}
              sub={`${reopenStats.reopen_rate.toFixed(1)}% des tickets avec SLA`}
              icon={RotateCcw}
              iconBg="bg-fuchsia-500/15"
              iconColor="text-fuchsia-600"
            />
            <KpiCard
              label="Réouvertures moy."
              value={reopenStats.avg_reopen_count?.toFixed(1) ?? "—"}
              sub="par ticket réouvert"
              icon={RotateCcw}
              iconBg="bg-fuchsia-500/15"
              iconColor="text-fuchsia-600"
            />
            <KpiCard
              label="Durée moy. 1er traitement"
              value={reopenStats.avg_first_cycle_hours != null ? `${reopenStats.avg_first_cycle_hours.toFixed(1)}h` : "—"}
              icon={CheckCircle2}
              iconBg="bg-primary/10"
              iconColor="text-primary"
            />
            <KpiCard
              label="Durée moy. après réouverture"
              value={reopenStats.avg_post_reopen_cycle_hours != null ? `${reopenStats.avg_post_reopen_cycle_hours.toFixed(1)}h` : "—"}
              icon={CheckCircle2}
              iconBg="bg-primary/10"
              iconColor="text-primary"
            />
            <KpiCard
              label="Tickets avec SLA"
              value={reopenStats.total_tickets_with_sla}
              sub="sur la période"
              icon={LayoutList}
              iconBg="bg-muted"
              iconColor="text-muted-foreground"
            />
          </div>
        </GlassCard>
      )}

      {/* BR-TRACE-001 — interventions (30 derniers jours) */}
      {interventionStats && (
        <GlassCard>
          <h2 className="mb-4 font-semibold">Interventions — {interventionStats.period}</h2>
          <div className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-5">
            <KpiCard
              label="Interventions"
              value={interventionStats.total_interventions}
              sub={`${interventionStats.distinct_agents} intervenant(s) distinct(s)`}
              icon={Users}
              iconBg="bg-primary/10"
              iconColor="text-primary"
            />
            <KpiCard
              label="Durée moyenne"
              value={interventionStats.avg_duration_hours != null ? `${interventionStats.avg_duration_hours.toFixed(1)}h` : "—"}
              sub={`${interventionStats.total_duration_hours.toFixed(1)}h cumulées`}
              icon={Timer}
              iconBg="bg-sky-500/15"
              iconColor="text-sky-600"
            />
            <KpiCard
              label="Transmissions"
              value={interventionStats.transmissions}
              sub="changements d'intervenant"
              icon={Send}
              iconBg="bg-sky-500/15"
              iconColor="text-sky-600"
            />
            <KpiCard
              label="Résolutions"
              value={interventionStats.resolutions}
              sub="traitements terminés"
              icon={CheckCircle2}
              iconBg="bg-emerald-500/15"
              iconColor="text-emerald-600"
            />
            <KpiCard
              label="Réouvertures"
              value={interventionStats.reopenings}
              sub="sur la période"
              icon={RotateCcw}
              iconBg="bg-fuchsia-500/15"
              iconColor="text-fuchsia-600"
            />
          </div>
          {interventionStats.by_agent.length > 0 && (
            <div className="mt-5 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="py-2 pr-4 text-left">Agent</th>
                    <th className="py-2 px-3 text-right">Interventions</th>
                    <th className="py-2 pl-3 text-right">Temps cumulé</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {interventionStats.by_agent.slice(0, 10).map((row) => (
                    <tr key={row.label} className="transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pr-4 font-medium">{row.label}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums">{row.intervention_count}</td>
                      <td className="py-2.5 pl-3 text-right tabular-nums">{row.total_hours.toFixed(1)}h</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      )}

      {!isChiefService && (
        <GlassCard>
          <h2 className="mb-4 font-semibold capitalize">Durée de traitement par {groupLabel}</h2>
          {groupRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun ticket actif.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="py-2 pr-4 text-left capitalize">{groupLabel}</th>
                    <th className="py-2 px-3 text-right">Actifs</th>
                    <th className="py-2 px-3 text-right">Durée moyenne</th>
                    <th className="py-2 pl-3 text-right">Durée cumulée</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {groupRows.map((row) => (
                    <tr key={row.id} className="transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pr-4 font-medium">{row.label}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums">{row.total}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-muted-foreground">
                        {formatElapsedHours(row.avgHours)}
                      </td>
                      <td className="py-2.5 pl-3 text-right tabular-nums text-muted-foreground">
                        {formatElapsedHours(row.totalHours)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      )}

      {/* Tickets actifs — durée de traitement, du plus long au plus récent */}
      <GlassCard>
        <h2 className="mb-4 flex items-center gap-2 font-semibold">
          <Timer className="h-4 w-4 text-muted-foreground" />
          Tickets actifs — durée de traitement
          {sortedByDuration.length > 0 && (
            <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
              {sortedByDuration.length}
            </span>
          )}
        </h2>

        {sortedByDuration.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CheckCircle2 className="h-4 w-4" />
            Aucun ticket actif.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-xs text-muted-foreground">
                  <th className="py-2 pr-3 text-left">Référence</th>
                  <th className="py-2 pr-3 text-left">Titre</th>
                  <th className="py-2 pr-3 text-left">Priorité</th>
                  <th className="py-2 pr-3 text-left capitalize">{groupLabel}</th>
                  <th className="py-2 pr-3 text-right">Durée</th>
                  <th className="py-2 text-left">Statut</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {pagedActive.map((r) => (
                  <tr key={r.id} className="transition-colors hover:bg-muted/30">
                    <td className="py-2.5 pr-3 font-mono text-xs text-muted-foreground">
                      {r.ref}
                    </td>
                    <td className="max-w-[180px] truncate py-2.5 pr-3">{r.title}</td>
                    <td className="py-2.5 pr-3">
                      <PriorityBadge priority={r.priority} />
                    </td>
                    <td className="py-2.5 pr-3 text-sm text-muted-foreground">
                      {isDirector || isChief
                        ? serviceLabel(r.serviceId)
                        : directionLabel(r.directionId)}
                    </td>
                    <td className="py-2.5 pr-3 text-right font-semibold tabular-nums text-muted-foreground">
                      {formatElapsedHours(r.slaElapsed)}
                    </td>
                    <td className="py-2.5">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="py-2.5 pl-3">
                      <Link
                        to="/app/sla-center/tickets/$id"
                        params={{ id: r.id }}
                        className="inline-flex items-center gap-0.5 text-xs text-primary hover:underline"
                      >
                        Voir <ChevronRight className="h-3 w-3" />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <PaginationBar
          page={bPage}
          totalPages={bTotalPages}
          total={bTotal}
          pageSize={bPageSize}
          onChange={setBPage}
          onPageSizeChange={setBPageSize}
        />
      </GlassCard>
    </div>
  );
}
