import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api/client";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchRequestStats } from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import {
  Activity,
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
  Hash,
  Building2,
  AlertTriangle,
  AlertCircle,
  GitBranchPlus,
  Unplug,
  BookX,
  Link2,
  ListChecks,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useQueryClient } from "@tanstack/react-query";

export const Route = createFileRoute("/app/admin/audit")({
  head: () => ({ meta: [{ title: "Audit système — Admin EDG" }] }),
  component: AuditPage,
});

// ── Types ─────────────────────────────────────────────────────────────────────

type HealthResponse = { status: string; database: string };
type GlobalStats = {
  total_requests: number;
  in_triage: number;
  sla_breached: number;
  open_escalations: number;
  resolution_rate: number;
  avg_satisfaction: number;
};
type RefItem = {
  id: number;
  code: string;
  label: string;
  sort_order: number;
  is_builtin: boolean;
  status: boolean;
  deleted_at: string | null;
};
type RefAll = {
  escalation_levels: RefItem[];
  escalation_statuses: RefItem[];
  workflow_statuses: RefItem[];
  task_types: RefItem[];
  task_statuses: RefItem[];
  account_statuses: RefItem[];
};

// ── Helpers ──────────────────────────────────────────────────────────────────

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

// ── Sous-composant : carte référentiel ────────────────────────────────────────

function RefCard({
  title,
  column,
  items,
  loading,
}: {
  title: string;
  column: string;
  items: RefItem[];
  loading: boolean;
}) {
  const active = items.filter((i) => i.status && !i.deleted_at);
  const builtin = active.filter((i) => i.is_builtin).length;
  const custom = active.length - builtin;

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="flex items-start justify-between gap-2 border-b border-border/40 px-4 py-3">
        <div className="min-w-0">
          <div className="font-mono text-xs font-semibold text-primary">{title}</div>
          <div className="mt-0.5 text-[11px] text-muted-foreground truncate">{column}</div>
        </div>
        <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
          <Link2 className="h-2.5 w-2.5" /> Câblé
        </span>
      </div>
      {loading ? (
        <div className="flex items-center gap-2 px-4 py-5 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Chargement…
        </div>
      ) : (
        <div className="px-4 py-3 space-y-2.5">
          <div className="flex gap-3 text-xs">
            <span className="text-muted-foreground">
              <span className="font-semibold text-foreground">{active.length}</span> actif{active.length !== 1 ? "s" : ""}
            </span>
            <span className="text-muted-foreground">
              <span className="font-semibold">{builtin}</span> builtin
            </span>
            {custom > 0 && (
              <span className="text-muted-foreground">
                <span className="font-semibold text-primary">{custom}</span> custom
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1">
            {active.map((item) => (
              <span
                key={item.id}
                className={cn(
                  "inline-flex items-center rounded-md px-1.5 py-0.5 font-mono text-[10px]",
                  item.is_builtin
                    ? "bg-muted text-muted-foreground"
                    : "bg-primary/10 text-primary",
                )}
                title={item.label}
              >
                {item.code}
              </span>
            ))}
            {items.filter((i) => i.deleted_at || !i.status).length > 0 && (
              <span className="inline-flex items-center rounded-md bg-destructive/10 px-1.5 py-0.5 font-mono text-[10px] text-destructive">
                +{items.filter((i) => i.deleted_at || !i.status).length} inactif{items.filter((i) => i.deleted_at || !i.status).length > 1 ? "s" : ""}
              </span>
            )}
          </div>
        </div>
      )}
    </GlassCard>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

function AuditPage() {
  const qc = useQueryClient();

  const { data: health, isLoading: healthLoading, isError: healthError } = useQuery({
    queryKey: ["audit-health"],
    queryFn: () => apiFetch<HealthResponse>("/health"),
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

  const { data: refAll, isLoading: refLoading } = useQuery<RefAll>({
    queryKey: ["references-all-audit"],
    queryFn: () => apiFetch<RefAll>("/references/all"),
    staleTime: 60_000,
  });

  const apiOk = !healthError && health?.status === "ok";
  const dbOk = !healthError && health?.database === "connected";
  const totalUsers = usersPage?.total ?? 0;
  const totalRequests = reqStats ? Object.values(reqStats).reduce((s, v) => s + v, 0) : 0;
  const directionMap = new Map(directions.map((d) => [String(d.id), d.name]));

  function refreshAll() {
    qc.invalidateQueries({ queryKey: ["audit-health"] });
    qc.invalidateQueries({ queryKey: ["directions"] });
    qc.invalidateQueries({ queryKey: ["units"] });
    qc.invalidateQueries({ queryKey: ["users-audit"] });
    qc.invalidateQueries({ queryKey: ["request-stats"] });
    qc.invalidateQueries({ queryKey: ["stats-global-audit"] });
    qc.invalidateQueries({ queryKey: ["references-all-audit"] });
  }

  const REF_META = [
    { key: "account_statuses" as keyof RefAll,    title: "account_status",    column: "account.account_status" },
    { key: "escalation_levels" as keyof RefAll,   title: "escalation_level",  column: "escalation.level" },
    { key: "escalation_statuses" as keyof RefAll, title: "escalation_status", column: "escalation.escalation_status" },
    { key: "task_types" as keyof RefAll,          title: "task_type",         column: "task.task_type" },
    { key: "task_statuses" as keyof RefAll,       title: "task_status",       column: "task.task_status" },
    { key: "workflow_statuses" as keyof RefAll,   title: "workflow_status",   column: "workflow.workflow_status + workflow_detail.workflow_status" },
  ];

  const totalRefCodes = REF_META.reduce((s, m) => s + (refAll?.[m.key]?.filter((i) => i.status && !i.deleted_at).length ?? 0), 0);

  return (
    <div className="mx-auto max-w-5xl space-y-8">

      {/* ── En-tête ── */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <ShieldCheck className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Audit système</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            État du backend, référentiels dynamiques, tables de données et unités organisationnelles.
          </p>
        </div>
        <Button variant="outline" className="rounded-full gap-2" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4" /> Actualiser
        </Button>
      </header>

      {/* ── Section 1 : Santé du système ── */}
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

      {/* ── Section 2 : Inventaire ── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Database className="h-4 w-4" /> Inventaire des tables
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard icon={Inbox}  label="Demandes totales"  value={reqLoading ? "…" : totalRequests} sub={globalKpis ? `${globalKpis.in_triage} en triage` : undefined} color="primary" />
          <StatCard icon={Users2} label="Utilisateurs"       value={usersLoading ? "…" : totalUsers}  color="info" />
          <StatCard icon={Network} label="Directions"        value={dirsLoading ? "…" : directions.length} color="success" />
          <StatCard icon={Layers} label="Services & Unités"  value={unitsLoading ? "…" : units.length} color="warning" />
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

      {/* ── Section 3 : Référentiels dynamiques (nouveau) ── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <ListChecks className="h-4 w-4" /> Référentiels dynamiques
          {!refLoading && refAll && (
            <span className="ml-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 normal-case tracking-normal">
              {totalRefCodes} codes actifs — 6 tables câblées
            </span>
          )}
        </h2>

        <GlassCard className="border-emerald-500/20 bg-emerald-500/3 px-5 py-3 text-sm">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
            <div className="text-xs text-muted-foreground leading-relaxed">
              <span className="font-semibold text-foreground">Validation applicative active</span> — les 6 colonnes métier
              ci-dessous sont câblées via <code className="rounded bg-muted px-1">check_ref_code()</code>.
              Toute valeur absente de la table correspondante est rejetée avec HTTP 422.
              L'admin peut ajouter un code via le CRUD : il devient immédiatement valide, sans redémarrage.
            </div>
          </div>
        </GlassCard>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {REF_META.map((m) => (
            <RefCard
              key={m.key}
              title={m.title}
              column={m.column}
              items={refAll?.[m.key] ?? []}
              loading={refLoading}
            />
          ))}
        </div>
      </section>

      {/* ── Section 4 : Table des Unités ── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Layers className="h-4 w-4" /> Table des unités
          {!unitsLoading && (
            <span className="ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary normal-case tracking-normal">
              {units.length} entrée{units.length !== 1 ? "s" : ""}
            </span>
          )}
        </h2>
        <GlassCard className="overflow-hidden p-0">
          {unitsLoading ? (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement des unités…
            </div>
          ) : units.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 py-16 text-center">
              <AlertTriangle className="h-6 w-6 text-warning-foreground dark:text-warning" />
              <p className="text-sm text-muted-foreground">Aucune unité enregistrée en base.</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-background/50 text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold"><div className="flex items-center gap-1.5"><Hash className="h-3 w-3" /> ID</div></th>
                  <th className="px-5 py-3 text-left font-semibold">Nom de l'unité</th>
                  <th className="px-5 py-3 text-left font-semibold"><div className="flex items-center gap-1.5"><Building2 className="h-3 w-3" /> Direction parente</div></th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-center font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {units.map((u) => (
                  <tr key={u.id} className="transition hover:bg-background/50">
                    <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">{u.id}</td>
                    <td className="px-5 py-3.5 font-medium">{u.name}</td>
                    <td className="px-5 py-3.5">
                      {u.direction_id ? (
                        <div className="flex items-center gap-1.5">
                          <Network className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-muted-foreground">
                            {directionMap.get(String(u.direction_id)) ?? `ID: ${u.direction_id}`}
                          </span>
                        </div>
                      ) : (
                        <span className="text-muted-foreground/50 italic">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">
                      {u.code ?? <span className="italic opacity-50">—</span>}
                    </td>
                    <td className="px-5 py-3.5 text-center">
                      <span className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold",
                        u.status
                          ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          : "bg-muted text-muted-foreground",
                      )}>
                        {u.status ? <><CheckCircle2 className="h-2.5 w-2.5" /> Actif</> : <><XCircle className="h-2.5 w-2.5" /> Inactif</>}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </GlassCard>
      </section>

      {/* ── Section 5 : Table des Directions ── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <Network className="h-4 w-4" /> Table des directions
          {!dirsLoading && (
            <span className="ml-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary normal-case tracking-normal">
              {directions.length} entrée{directions.length !== 1 ? "s" : ""}
            </span>
          )}
        </h2>
        <GlassCard className="overflow-hidden p-0">
          {dirsLoading ? (
            <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> Chargement des directions…
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-background/50 text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold"><div className="flex items-center gap-1.5"><Hash className="h-3 w-3" /> ID</div></th>
                  <th className="px-5 py-3 text-left font-semibold">Nom</th>
                  <th className="px-5 py-3 text-left font-semibold">Code</th>
                  <th className="px-5 py-3 text-right font-semibold">Unités</th>
                  <th className="px-5 py-3 text-center font-semibold">Statut</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/30">
                {directions.map((d) => {
                  const unitCount = units.filter((u) => String(u.direction_id) === String(d.id)).length;
                  return (
                    <tr key={d.id} className="transition hover:bg-background/50">
                      <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">{d.id}</td>
                      <td className="px-5 py-3.5 font-medium">{d.name}</td>
                      <td className="px-5 py-3.5 font-mono text-xs text-muted-foreground">{d.code ?? "—"}</td>
                      <td className="px-5 py-3.5 text-right">
                        <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary">
                          <Layers className="h-3 w-3" /> {unitCount}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-center">
                        <span className={cn(
                          "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-semibold",
                          d.status
                            ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                            : "bg-muted text-muted-foreground",
                        )}>
                          {d.status ? <><CheckCircle2 className="h-2.5 w-2.5" /> Actif</> : <><XCircle className="h-2.5 w-2.5" /> Inactif</>}
                        </span>
                      </td>
                    </tr>
                  );
                })}
                {directions.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-10 text-center text-sm text-muted-foreground">
                      Aucune direction en base.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </GlassCard>
      </section>

      {/* ── Section 6 : Analyse tables à faible valeur ── */}
      <section className="space-y-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          <BookX className="h-4 w-4" /> Tables à faible valeur opérationnelle
          <span className="ml-1 rounded-full bg-muted px-2 py-0.5 text-[11px] font-semibold text-muted-foreground normal-case tracking-normal">
            8 tables restantes (6 câblées)
          </span>
        </h2>

        {/* Groupe 1 — câblées (mis à jour) */}
        <GlassCard className="overflow-hidden p-0">
          <div className="flex items-center gap-3 border-b border-border/40 bg-emerald-500/5 px-5 py-3">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" />
            <div>
              <div className="text-sm font-semibold text-emerald-600 dark:text-emerald-400">
                Groupe 1 — Référentiels câblés avec validation applicative (6) ✓
              </div>
              <div className="text-xs text-muted-foreground">
                Colonnes <code className="rounded bg-muted px-1">String(50)</code> — validées via{" "}
                <code className="rounded bg-muted px-1">check_ref_code()</code> à chaque écriture.
                Valeurs admin disponibles immédiatement. Aucune FK MySQL ajoutée.
              </div>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-background/40 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-2.5 text-left font-semibold">Table de référence</th>
                <th className="px-5 py-2.5 text-left font-semibold">Colonne métier</th>
                <th className="px-5 py-2.5 text-left font-semibold">Service câblé</th>
                <th className="px-5 py-2.5 text-center font-semibold">État</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {[
                { table: "account_status",    col: "account.account_status",                       svc: "ServiceAccount (create + update)" },
                { table: "escalation_level",  col: "escalation.level",                             svc: "ServiceEscalation (create + update)" },
                { table: "escalation_status", col: "escalation.escalation_status",                 svc: "ServiceEscalation (create + update)" },
                { table: "task_type",         col: "task.task_type",                               svc: "ServiceTask (create + update)" },
                { table: "task_status",       col: "task.task_status",                             svc: "ServiceTask (create + update)" },
                { table: "workflow_status",   col: "workflow.workflow_status + workflow_detail.workflow_status", svc: "ServiceWorkflow (create/update/detail)" },
              ].map((row) => (
                <tr key={row.table} className="transition hover:bg-emerald-500/3">
                  <td className="px-5 py-3 font-mono text-xs font-semibold text-emerald-700 dark:text-emerald-400">{row.table}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{row.col}</td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">{row.svc}</td>
                  <td className="px-5 py-3 text-center">
                    <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                      <Link2 className="h-2.5 w-2.5" /> Câblé
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>

        {/* Groupe 2 — sans UI */}
        <GlassCard className="overflow-hidden p-0">
          <div className="flex items-center gap-3 border-b border-border/40 bg-amber-500/5 px-5 py-3">
            <GitBranchPlus className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
            <div>
              <div className="text-sm font-semibold text-amber-600 dark:text-amber-400">Groupe 2 — Sous-systèmes backend sans UI frontend (3)</div>
              <div className="text-xs text-muted-foreground">
                Backend complet (routes, services, schémas) — mais aucune page ni composant frontend ne les exploite.
              </div>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-background/40 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-2.5 text-left font-semibold">Table(s)</th>
                <th className="px-5 py-2.5 text-left font-semibold">Endpoint backend</th>
                <th className="px-5 py-2.5 text-left font-semibold">Statut frontend</th>
                <th className="px-5 py-2.5 text-left font-semibold">Recommandation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {[
                { tables: "workflow + workflow_detail", endpoint: "/workflows/, /requests/{id}/workflow", front: "workflow.ts existe, 0 page l'importe", rec: "Créer une page de suivi workflow" },
                { tables: "task",                       endpoint: "/tasks/ (approve/reject/cancel)",      front: "Fonctions dans workflow.ts, 0 page", rec: "Intégrer dans la fiche demande" },
                { tables: "sms_log",                    endpoint: "/sms-logs/ (admin)",                   front: "Aucun appel, 0 gateway SMS",         rec: "Supprimer ou intégrer gateway SMS" },
              ].map((row) => (
                <tr key={row.tables} className="transition hover:bg-amber-500/5">
                  <td className="px-5 py-3 font-mono text-xs font-semibold text-amber-600 dark:text-amber-400">{row.tables}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{row.endpoint}</td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                      <AlertCircle className="h-3 w-3" /> {row.front}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-xs text-muted-foreground">{row.rec}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>

        {/* Groupe 3 — announcement annexes */}
        <GlassCard className="overflow-hidden p-0">
          <div className="flex items-center gap-3 border-b border-border/40 bg-blue-500/5 px-5 py-3">
            <AlertCircle className="h-4 w-4 shrink-0 text-blue-500" />
            <div>
              <div className="text-sm font-semibold text-blue-600 dark:text-blue-400">Groupe 3 — Annexes announcement sans UI (4)</div>
              <div className="text-xs text-muted-foreground">
                FK valides vers <code className="rounded bg-muted px-1">announcement</code> — structurellement correctes,
                mais le module Communication frontend ne les expose pas encore.
              </div>
            </div>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-background/40 text-[11px] uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="px-5 py-2.5 text-left font-semibold">Table</th>
                <th className="px-5 py-2.5 text-left font-semibold">FK vers</th>
                <th className="px-5 py-2.5 text-left font-semibold">UI frontend</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border/30">
              {[
                { table: "announcement_channel",          fk: "announcement.id",                  ui: "Non exposé" },
                { table: "announcement_metric",           fk: "announcement.id",                  ui: "Non exposé" },
                { table: "announcement_target_direction", fk: "announcement.id + direction.id",   ui: "Non exposé" },
                { table: "announcement_target_role",      fk: "announcement.id",                  ui: "Non exposé" },
              ].map((row) => (
                <tr key={row.table} className="transition hover:bg-blue-500/5">
                  <td className="px-5 py-3 font-mono text-xs text-blue-600 dark:text-blue-400">{row.table}</td>
                  <td className="px-5 py-3 font-mono text-xs text-muted-foreground">{row.fk}</td>
                  <td className="px-5 py-3">
                    <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">
                      <XCircle className="h-3 w-3" /> {row.ui}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </GlassCard>

        {/* Bilan */}
        <div className="grid gap-3 sm:grid-cols-3">
          <GlassCard className="border-emerald-500/20 py-3 text-center">
            <div className="text-2xl font-bold text-emerald-500">6</div>
            <div className="text-xs text-muted-foreground">Référentiels câblés (validation active)</div>
          </GlassCard>
          <GlassCard className="border-amber-500/20 py-3 text-center">
            <div className="text-2xl font-bold text-amber-600 dark:text-amber-400">3</div>
            <div className="text-xs text-muted-foreground">Sous-systèmes sans UI frontend</div>
          </GlassCard>
          <GlassCard className="border-blue-500/20 py-3 text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">4</div>
            <div className="text-xs text-muted-foreground">Annexes announcement sans UI</div>
          </GlassCard>
        </div>
      </section>

      {/* ── Footer ── */}
      <div className="flex items-center gap-2 rounded-xl border border-border/40 bg-background/30 px-4 py-3 text-xs text-muted-foreground">
        <Activity className="h-3.5 w-3.5 shrink-0" />
        Audit mis à jour le 2026-06-19 — référentiels câblés (ÉTAPE 2 complète). Données en temps réel depuis le backend.
      </div>
    </div>
  );
}
