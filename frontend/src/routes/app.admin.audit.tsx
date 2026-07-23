import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, checkHealth } from "@/lib/api/client";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchRequestStats } from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import {
  Database,
  Server,
  Layers,
  Network,
  Users2,
  Inbox,
  CheckCircle2,
  XCircle,
  Loader2,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";

export const Route = createFileRoute("/app/admin/audit")({
  head: () => ({ meta: [{ title: "Audit système — Admin EDG" }] }),
  component: AuditPage,
});

type GlobalStats = {
  total_requests: number;
  in_triage: number;
  sla_breached: number;
  open_escalations: number;
  resolution_rate: number;
  avg_satisfaction: number;
};

function StatusDot({ ok, loading }: { ok?: boolean; loading?: boolean }) {
  if (loading) return <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />;
  return ok
    ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    : <XCircle className="h-4 w-4 text-destructive" />;
}

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
  color = "primary",
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: number | string;
  sub?: string;
  color?: "primary" | "success" | "warning" | "destructive" | "info";
}) {
  const colorMap = {
    primary: "bg-primary/10 text-primary",
    success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    destructive: "bg-destructive/10 text-destructive",
    info: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  };
  return (
    <GlassCard className="flex items-center gap-4 py-4">
      <div className={cn("grid h-11 w-11 shrink-0 place-items-center rounded-2xl", colorMap[color])}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="text-2xl font-bold tabular-nums">{value}</div>
        <div className="text-xs font-medium text-muted-foreground">{label}</div>
        {sub && <div className="text-[10px] text-muted-foreground/70">{sub}</div>}
      </div>
    </GlassCard>
  );
}

function AuditPage() {
  const qc = useQueryClient();

  const { data: health, isLoading: healthLoading, isError: healthError } = useQuery({
    queryKey: ["audit-health"],
    queryFn: checkHealth,
    staleTime: 30_000,
    retry: 1,
  });

  const { data: directions = [], isLoading: dirsLoading } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: units = [], isLoading: unitsLoading } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });

  const { data: usersPage, isLoading: usersLoading } = useQuery({
    queryKey: ["users-audit"],
    queryFn: () => fetchUsers({ limit: 1 }),
    staleTime: 5 * 60_000,
  });

  const { data: reqStats, isLoading: reqLoading } = useQuery({
    queryKey: ["request-stats"],
    queryFn: fetchRequestStats,
    staleTime: 30_000,
  });

  const { data: globalKpis, isLoading: kpisLoading } = useQuery<GlobalStats>({
    queryKey: ["stats-global-audit"],
    queryFn: () => apiFetch<GlobalStats>("/stats/global"),
    staleTime: 30_000,
    retry: 1,
  });

  const apiOk = !healthError && health?.status === "ok";
  const dbOk = !healthError && health?.database === "connected";
  const totalUsers = usersPage?.total ?? 0;
  const totalRequests = reqStats ? Object.values(reqStats).reduce((s, v) => s + v, 0) : 0;

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ["audit-health"] });
    qc.invalidateQueries({ queryKey: ["directions"] });
    qc.invalidateQueries({ queryKey: ["units"] });
    qc.invalidateQueries({ queryKey: ["users-audit"] });
    qc.invalidateQueries({ queryKey: ["request-stats"] });
    qc.invalidateQueries({ queryKey: ["stats-global-audit"] });
  }

  return (
    <div className="mx-auto max-w-5xl space-y-8">

      {/* En-tête */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <ShieldCheck className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Audit système</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            État du backend, statistiques des demandes et données organisationnelles.
          </p>
        </div>
        <Button variant="outline" className="rounded-full gap-2" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4" /> Actualiser
        </Button>
      </header>

      {/* Section 1 : Santé du système */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Server className="h-4 w-4" /> État du système
        </h2>
        <GlassCard className="divide-y divide-border/40 p-0 overflow-hidden">
          {[
            {
              label: "API Backend",
              desc: "FastAPI — endpoint /health",
              ok: apiOk,
              loading: healthLoading,
              detail: healthError ? "Non joignable" : health?.status ?? "—",
            },
            {
              label: "Base de données",
              desc: "MySQL / SQLAlchemy (async)",
              ok: dbOk,
              loading: healthLoading,
              detail: healthError ? "Erreur connexion" : health?.database ?? "—",
            },
          ].map((row) => (
            <div key={row.label} className="flex items-center gap-4 px-5 py-4">
              <StatusDot ok={row.ok} loading={row.loading} />
              <div className="flex-1 min-w-0">
                <div className="font-medium text-sm">{row.label}</div>
                <div className="text-xs text-muted-foreground">{row.desc}</div>
              </div>
              <span className={cn(
                "rounded-full px-2.5 py-0.5 text-[11px] font-semibold",
                row.loading
                  ? "bg-muted text-muted-foreground"
                  : row.ok
                  ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "bg-destructive/10 text-destructive",
              )}>
                {row.loading ? "Vérification…" : row.detail}
              </span>
            </div>
          ))}
        </GlassCard>
      </section>

      {/* Section 2 : Inventaire */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Database className="h-4 w-4" /> Inventaire
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={Inbox}   label="Demandes totales" value={reqLoading ? "…" : totalRequests} sub={globalKpis ? `${globalKpis.in_triage} en triage` : undefined} color="primary" />
          <StatCard icon={Users2}  label="Utilisateurs"      value={usersLoading ? "…" : totalUsers}  color="info" />
          <StatCard icon={Network} label="Directions"         value={dirsLoading ? "…" : directions.length} color="success" />
          <StatCard icon={Layers}  label="Services & Unités"  value={unitsLoading ? "…" : units.length} color="warning" />
        </div>

        {reqStats && (
          <GlassCard className="p-0 overflow-hidden">
            <div className="border-b border-border/40 px-5 py-3">
              <h3 className="text-sm font-semibold">Demandes par statut</h3>
            </div>
            <div className="flex flex-wrap gap-0 divide-x divide-border/40">
              {Object.entries(reqStats).map(([status, count]) => (
                <div key={status} className="flex-1 min-w-[100px] px-4 py-3 text-center">
                  <div className="text-lg font-bold tabular-nums">{count}</div>
                  <div className="text-[10px] text-muted-foreground capitalize">{status.replace("_", " ")}</div>
                </div>
              ))}
            </div>
          </GlassCard>
        )}

        {globalKpis && !kpisLoading && (
          <div className="grid gap-3 sm:grid-cols-3">
            <GlassCard className="py-3">
              <div className="text-xs text-muted-foreground">Taux de résolution</div>
              <div className="mt-1 text-xl font-bold text-emerald-500">{globalKpis.resolution_rate}%</div>
            </GlassCard>
            <GlassCard className="py-3">
              <div className="text-xs text-muted-foreground">SLA dépassées</div>
              <div className={cn("mt-1 text-xl font-bold", globalKpis.sla_breached > 0 ? "text-destructive" : "text-emerald-500")}>
                {globalKpis.sla_breached}
              </div>
            </GlassCard>
            <GlassCard className="py-3">
              <div className="text-xs text-muted-foreground">Satisfaction moyenne</div>
              <div className="mt-1 text-xl font-bold text-amber-500">
                {globalKpis.avg_satisfaction > 0 ? `${globalKpis.avg_satisfaction}/5` : "—"}
              </div>
            </GlassCard>
          </div>
        )}
      </section>
    </div>
  );
}
