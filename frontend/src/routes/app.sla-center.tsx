import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo } from "react";
import { usePagination, PaginationBar } from "@/components/pagination-bar";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Flame,
  LayoutList,
  RotateCcw,
  Users,
  Send,
  Timer,
} from "lucide-react";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { fetchRequests } from "@/lib/api/requests";
import { fetchSlaReopenStats, fetchInterventionStats } from "@/lib/api/reports";
import type { RequestItem, RequestStatus } from "@/lib/mock-data";
import { requireRole } from "@/lib/auth-guard";
import { useRole, useUser } from "@/lib/session";
import { fetchDirections, fetchUnit, fetchUnits } from "@/lib/api/directions-units";
import type { Unit } from "@/lib/api/directions-units";

export const Route = createFileRoute("/app/sla-center")({
  beforeLoad: () => requireRole("chief-service", "chief-departement", "director", "admin"),
  head: () => ({ meta: [{ title: "Centre SLA — EDG Support" }] }),
  component: SlaCenterPage,
});

// ── Constants ─────────────────────────────────────────────────────────────────

const ACTIVE_STATUSES: RequestStatus[] = [
  "new", "qualifying", "qualified", "assigned",
  "in_progress", "pending", "escalated", "reopened",
];

// ── Helpers ───────────────────────────────────────────────────────────────────

const isActive = (r: RequestItem) => ACTIVE_STATUSES.includes(r.status);
const isBreached = (r: RequestItem) => r.slaElapsed > r.slaHours;

function complianceColor(rate: number): string {
  if (rate >= 90) return "text-emerald-600";
  if (rate >= 70) return "text-amber-600";
  return "text-destructive";
}

function complianceBarColor(rate: number): string {
  if (rate >= 90) return "bg-emerald-500";
  if (rate >= 70) return "bg-amber-500";
  return "bg-destructive";
}

function formatOverdue(hours: number): string {
  if (hours < 1) return "< 1h";
  if (hours < 24) return `+${Math.round(hours)}h`;
  const days = Math.floor(hours / 24);
  const rem = Math.round(hours % 24);
  return rem > 0 ? `+${days}j ${rem}h` : `+${days}j`;
}

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
  compliant: number;
  breached: number;
  rate: number;
};

// ── Page ──────────────────────────────────────────────────────────────────────

function SlaCenterPage() {
  const [role] = useRole();
  const sessionUser = useUser();
  const isDirector = role === "director";
  const isChiefService = role === "chief-service";
  const isChief = role === "chief-service" || role === "chief-departement";

  const filters = useMemo(
    () => ({
      limit: 500,
      ...(isDirector && sessionUser?.direction_id
        ? { direction_id: sessionUser.direction_id }
        : isChief && sessionUser?.unit_id
        ? { unit_id: sessionUser.unit_id }
        : {}),
    }),
    [isDirector, isChief, sessionUser?.direction_id, sessionUser?.unit_id],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["sla-center", filters],
    queryFn: () => fetchRequests(filters),
    staleTime: 30_000,
  });

  // BR-SLA-REOPEN-001 — statistiques croisées cycles SLA / réouvertures.
  const { data: reopenStats } = useQuery({
    queryKey: ["sla-reopen-stats"],
    queryFn: () => fetchSlaReopenStats(),
    staleTime: 60_000,
  });

  // BR-TRACE-001 — statistiques agrégées sur les interventions.
  const { data: interventionStats } = useQuery({
    queryKey: ["intervention-stats"],
    queryFn: () => fetchInterventionStats(),
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

  const breachedList = useMemo(
    () =>
      active
        .filter(isBreached)
        .sort((a, b) => (b.slaElapsed - b.slaHours) - (a.slaElapsed - a.slaHours)),
    [active],
  );

  const critical = useMemo(
    () => active.filter((r) => r.priority === "critical"),
    [active],
  );

  const { page: bPage, setPage: setBPage, totalPages: bTotalPages, paged: pagedBreached, total: bTotal, pageSize: bPageSize, setPageSize: setBPageSize } = usePagination(breachedList, 15);

  const conformityRate =
    active.length > 0
      ? ((active.length - breachedList.length) / active.length) * 100
      : 100;

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
        const compliant = items.filter((r) => !isBreached(r)).length;
        return {
          id,
          label: (isDirector || isChief)
            ? serviceLabel(id)
            : directionLabel(id),
          total: items.length,
          compliant,
          breached: items.length - compliant,
          rate: items.length > 0 ? (compliant / items.length) * 100 : 100,
        };
      })
      .sort((a, b) => a.rate - b.rate);
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
      <div>
        <h1 className="text-2xl font-bold">Centre SLA</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {isDirector
            ? "Suivi des engagements SLA de votre direction"
            : "Vue d'ensemble SLA — toutes les directions"}
        </p>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-4">
        <KpiCard
          label="Taux de conformité"
          value={`${conformityRate.toFixed(1)}%`}
          sub={`${active.length - breachedList.length} conformes / ${active.length}`}
          icon={CheckCircle2}
          iconBg={
            conformityRate >= 90
              ? "bg-emerald-500/15"
              : conformityRate >= 70
                ? "bg-amber-500/15"
                : "bg-destructive/15"
          }
          iconColor={
            conformityRate >= 90
              ? "text-emerald-600"
              : conformityRate >= 70
                ? "text-amber-600"
                : "text-destructive"
          }
          progress={conformityRate}
          progressColor={complianceBarColor(conformityRate)}
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
          label="En dépassement SLA"
          value={breachedList.length}
          sub={breachedList.length > 0 ? "action requise" : "aucun dépassement"}
          icon={AlertTriangle}
          iconBg={breachedList.length > 0 ? "bg-destructive/15" : "bg-emerald-500/15"}
          iconColor={breachedList.length > 0 ? "text-destructive" : "text-emerald-600"}
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
              sub={
                reopenStats.first_cycle_sla_compliance_rate != null
                  ? `conformité SLA ${reopenStats.first_cycle_sla_compliance_rate.toFixed(1)}%`
                  : undefined
              }
              icon={CheckCircle2}
              iconBg="bg-primary/10"
              iconColor="text-primary"
            />
            <KpiCard
              label="Durée moy. après réouverture"
              value={reopenStats.avg_post_reopen_cycle_hours != null ? `${reopenStats.avg_post_reopen_cycle_hours.toFixed(1)}h` : "—"}
              sub={
                reopenStats.post_reopen_sla_compliance_rate != null
                  ? `conformité SLA ${reopenStats.post_reopen_sla_compliance_rate.toFixed(1)}%`
                  : undefined
              }
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
          <h2 className="mb-4 font-semibold capitalize">SLA par {groupLabel}</h2>
          {groupRows.length === 0 ? (
            <p className="text-sm text-muted-foreground">Aucun ticket actif.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-xs text-muted-foreground">
                    <th className="py-2 pr-4 text-left capitalize">{groupLabel}</th>
                    <th className="py-2 px-3 text-right">Actifs</th>
                    <th className="py-2 px-3 text-right">Conformes</th>
                    <th className="py-2 px-3 text-right">Breach</th>
                    <th className="py-2 pl-3 text-right">Taux</th>
                    <th className="w-32 py-2 pl-4"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/50">
                  {groupRows.map((row) => (
                    <tr key={row.id} className="transition-colors hover:bg-muted/30">
                      <td className="py-2.5 pr-4 font-medium">{row.label}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums">{row.total}</td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-emerald-600">
                        {row.compliant}
                      </td>
                      <td className="py-2.5 px-3 text-right tabular-nums text-destructive">
                        {row.breached}
                      </td>
                      <td
                        className={`py-2.5 pl-3 text-right tabular-nums font-semibold ${complianceColor(row.rate)}`}
                      >
                        {row.rate.toFixed(1)}%
                      </td>
                      <td className="py-2.5 pl-4">
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className={`h-full rounded-full transition-all ${complianceBarColor(row.rate)}`}
                            style={{ width: `${row.rate}%` }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </GlassCard>
      )}

      {/* Breached tickets list */}
      <GlassCard>
        <h2 className="mb-4 flex items-center gap-2 font-semibold">
          <AlertTriangle className="h-4 w-4 text-destructive" />
          Tickets en dépassement SLA
          {breachedList.length > 0 && (
            <span className="ml-1 rounded-full bg-destructive/15 px-2 py-0.5 text-xs font-semibold text-destructive">
              {breachedList.length}
            </span>
          )}
        </h2>

        {breachedList.length === 0 ? (
          <div className="flex items-center gap-2 text-sm text-emerald-600">
            <CheckCircle2 className="h-4 w-4" />
            Toutes les SLA sont respectées.
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
                  <th className="py-2 pr-3 text-right">Dépassé de</th>
                  <th className="py-2 text-left">Statut</th>
                  <th className="py-2"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/50">
                {pagedBreached.map((r) => (
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
                    <td className="py-2.5 pr-3 text-right font-semibold tabular-nums text-destructive">
                      {formatOverdue(r.slaElapsed - r.slaHours)}
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
