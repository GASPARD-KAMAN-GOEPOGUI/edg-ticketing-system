import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { getRole, useRole, useUser, roleLabels } from "@/lib/session";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { statusLabels } from "@/lib/mock-data";
import type { RequestItem } from "@/lib/mock-data";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCsatStats } from "@/lib/api/csat";
import { fetchRequests, fetchRequestStats } from "@/lib/api/requests";
import type { RequestStats } from "@/lib/api/requests";
import { fetchDirections } from "@/lib/api/directions-units";
import {
  ArrowRight,
  Clock,
  Inbox,
  Plus,
  CheckCircle2,
  AlertTriangle,
  Users2,
  TrendingUp,
  Building2,
  Star,
  Loader2,
  MessageSquareWarning,
  ArrowUpRight,
  RotateCcw,
} from "lucide-react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Legend,
} from "recharts";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

// Ces redirects reflètent ROLE_DEFAULT_ROUTES défini dans session.ts.
export const Route = createFileRoute("/app/")({
  beforeLoad: () => {
    const role = getRole();
    if (role === "dg")       throw redirect({ to: "/app/dg" });
    if (role === "director") throw redirect({ to: "/app/direction" });
    if (role === "chief")    throw redirect({ to: "/app/supervision" });
    if (role === "agent")    throw redirect({ to: "/app/queue" });
    if (role === "admin")    throw redirect({ to: "/app/admin/users" });
    // user et public voient le dashboard ici
  },
  head: () => ({ meta: [{ title: "Tableau de bord — EDG Support" }] }),
  component: Dashboard,
});

function Dashboard() {
  const [role] = useRole();
  const sessionUser = useUser();
  const firstName = sessionUser?.name?.split(" ")[0] || null;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="text-xs font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {roleLabels[role]}
          </div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">
            {firstName ? `Bonjour, ${firstName} 👋` : "Bonjour 👋"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Voici l'état des demandes pour votre espace.
          </p>
        </div>
        <Button asChild className="rounded-full gradient-primary shadow-lg shadow-primary/30">
          <Link to="/app/new">
            <Plus className="mr-1 h-4 w-4" /> Nouvelle demande
          </Link>
        </Button>
      </header>

      {role === "user"     && <UserDashboard />}
      {role === "agent"    && <AgentDashboard />}
      {role === "chief"    && <ChiefDashboard />}
      {role === "director" && <DirectorDashboard />}
      {role === "dg"       && <DgDashboard />}
      {role === "admin"    && <AdminDashboard />}
    </div>
  );
}

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function sumStats(stats: RequestStats | undefined, keys: string[]): number {
  if (!stats) return 0;
  return keys.reduce((acc, k) => acc + (stats[k] ?? 0), 0);
}

function totalStats(stats: RequestStats | undefined): number {
  if (!stats) return 0;
  return Object.values(stats).reduce((a, b) => a + b, 0);
}

/* ─── Composants partagés ────────────────────────────────────────────────── */

function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "primary",
  loading = false,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Inbox;
  tone?: "primary" | "success" | "warning" | "destructive" | "accent";
  loading?: boolean;
}) {
  const toneMap = {
    primary:     "bg-primary/10 text-primary",
    success:     "bg-success/15 text-success",
    warning:     "bg-warning/20 text-warning-foreground dark:text-warning",
    destructive: "bg-destructive/15 text-destructive",
    accent:      "bg-accent/15 text-accent",
  };
  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={"grid h-9 w-9 place-items-center rounded-xl " + toneMap[tone]}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div>
        {loading ? (
          <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" />
        ) : (
          <div className="text-3xl font-bold tracking-tight">{value}</div>
        )}
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </div>
    </GlassCard>
  );
}

function RecentList({ items, isLoading }: { items: RequestItem[]; isLoading?: boolean }) {
  const { data: dirs = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 60_000,
  });
  return (
    <GlassCard className="p-4 sm:p-6 lg:col-span-2">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold">Demandes récentes</h3>
        <Button asChild variant="ghost" size="sm" className="rounded-full">
          <Link to="/app/requests">
            Voir tout <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Link>
        </Button>
      </div>
      {isLoading ? (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
        </div>
      ) : items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Aucune demande.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.slice(0, 5).map((r) => (
            <li key={r.id}>
              <Link
                to="/app/requests/$id"
                params={{ id: r.id }}
                className="block rounded-2xl border border-transparent p-3 transition hover:border-border hover:bg-background/60"
              >
                {/* Ligne 1 : référence + priorité (gauche) · statut (droite) */}
                <div className="flex min-w-0 items-center justify-between gap-2">
                  <div className="flex min-w-0 flex-wrap items-center gap-1.5">
                    <span className="font-mono text-[11px] text-muted-foreground">{r.ref}</span>
                    <PriorityBadge priority={r.priority} />
                  </div>
                  <StatusBadge status={r.status} />
                </div>
                {/* Ligne 2 : titre (2 lignes max sur mobile) */}
                <div className="mt-1.5 line-clamp-2 text-sm font-medium leading-snug sm:line-clamp-1">{r.title}</div>
                {/* Ligne 3 : catégorie + date */}
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {dirs.find((d) => String(d.id) === String(r.directionId))?.name ?? r.category}
                  {" · "}
                  {formatDistanceToNow(new Date(r.createdAt), { addSuffix: true, locale: fr })}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </GlassCard>
  );
}

function StatusPie({ data, isLoading }: { data: RequestItem[]; isLoading?: boolean }) {
  const grouped = Object.entries(
    data.reduce<Record<string, number>>((acc, r) => {
      acc[r.status] = (acc[r.status] || 0) + 1;
      return acc;
    }, {}),
  ).map(([k, v]) => ({ name: statusLabels[k as keyof typeof statusLabels] ?? k, value: v, key: k }));

  const colors = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];
  return (
    <GlassCard className="p-4 sm:p-6">
      <h3 className="mb-2 font-semibold">Répartition par statut</h3>
      {isLoading ? (
        <div className="flex h-56 items-center justify-center">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
        </div>
      ) : grouped.length === 0 ? (
        <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">
          Aucune donnée
        </div>
      ) : (
        <>
          <div className="h-44 sm:h-56">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={grouped}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={42}
                  outerRadius={68}
                  paddingAngle={3}
                  stroke="none"
                >
                  {grouped.map((_, i) => (
                    <Cell key={i} fill={colors[i % colors.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-1 grid grid-cols-1 gap-1 text-xs sm:grid-cols-2 sm:gap-1.5">
            {grouped.map((g, i) => (
              <li key={g.key} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: colors[i % colors.length] }} />
                <span className="min-w-0 truncate text-muted-foreground">{g.name}</span>
                <span className="ml-auto shrink-0 font-medium">{g.value}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </GlassCard>
  );
}

/* ─── Dashboards par rôle ────────────────────────────────────────────────── */

function UserDashboard() {
  const sessionUser = useUser();
  const { data, isLoading } = useQuery({
    queryKey: ["my-requests", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, limit: 100 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });
  const items  = data?.items ?? [];
  const total  = data?.total ?? 0;
  const active = items.filter((r) => ["new", "assigned", "in_progress", "qualifying", "qualified"].includes(r.status)).length;
  const done   = items.filter((r) => ["resolved", "closed"].includes(r.status)).length;
  const waiting = items.filter((r) => r.status === "pending").length;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Demandes créées"   value={total}   icon={Inbox}       tone="primary"     hint="Au total" loading={isLoading} />
        <Stat label="En cours"          value={active}  icon={Clock}       tone="accent"       loading={isLoading} />
        <Stat label="Résolues"          value={done}    icon={CheckCircle2} tone="success"     loading={isLoading} />
        <Stat label="En attente"        value={waiting} icon={AlertTriangle} tone="warning"    loading={isLoading} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={items} isLoading={isLoading} />
        <StatusPie  data={items}  isLoading={isLoading} />
      </div>
    </>
  );
}

function AgentDashboard() {
  const sessionUser = useUser();
  const { data: assignedData, isLoading: loadAssigned } = useQuery({
    queryKey: ["assigned-requests", sessionUser?.id],
    queryFn: () => fetchRequests({ assignee_id: sessionUser!.id, limit: 100 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });
  const { data: stats, isLoading: loadStats } = useQuery({
    queryKey: ["req-stats"],
    queryFn: fetchRequestStats,
    staleTime: 30_000,
  });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });

  const assigned      = assignedData?.items ?? [];
  const queue         = sumStats(stats, ["new", "qualifying"]);
  const loading       = loadAssigned || loadStats;
  const inProgress    = assigned.filter((r) => r.status === "in_progress").length;
  const pendingCount  = assigned.filter((r) => r.status === "pending").length;
  const reopenedCount = assigned.filter((r) => r.status === "reopened").length;
  const slaBreachedMine = assigned.filter((r) => r.slaElapsed > r.slaHours).length;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="File d'attente"   value={queue}                        icon={Inbox}               tone="primary"      loading={loadStats}    hint="Nouvelles demandes" />
        <Stat label="Mes assignations" value={assignedData?.total ?? 0}     icon={Users2}              tone="accent"       loading={loadAssigned} />
        <Stat label="En cours"         value={inProgress}                   icon={Clock}               tone="accent"       loading={loadAssigned} hint="En traitement actif" />
        <Stat label="En attente"       value={pendingCount}                 icon={MessageSquareWarning} tone="warning"     loading={loadAssigned} hint="Attente demandeur" />
        <Stat label="CSAT moyen"       value={(csat?.global ?? 0) > 0 ? `${csat!.global}/5` : "—"} icon={Star} tone="warning" />
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="SLA dépassés"   value={slaBreachedMine}                icon={AlertTriangle}       tone="destructive"  loading={loadAssigned} hint="Mes tickets en retard" />
        <Stat label="Escaladés"      value={sumStats(stats, ["escalated"])} icon={ArrowUpRight}        tone="destructive"  loading={loadStats} />
        <Stat label="Réouverts"      value={reopenedCount}                  icon={RotateCcw}           tone="warning"      loading={loadAssigned} hint="Réouverts par demandeur" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={assigned} isLoading={loading} />
        <StatusPie  data={assigned}  isLoading={loading} />
      </div>
    </>
  );
}

function ChiefDashboard() {
  const sessionUser = useUser();
  const directionId = sessionUser?.direction_id;

  const { data, isLoading } = useQuery({
    queryKey: ["chief-requests", directionId],
    queryFn: () => fetchRequests({ direction_id: directionId, limit: 200 }),
    enabled: !!sessionUser,
    staleTime: 30_000,
  });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const ACTIVE_ST = ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"];
  const open         = items.filter((r) => ACTIVE_ST.includes(r.status)).length;
  const inProgress   = items.filter((r) => r.status === "in_progress").length;
  const pendingCount = items.filter((r) => r.status === "pending").length;
  const escalated    = items.filter((r) => r.status === "escalated").length;
  const reopened     = items.filter((r) => r.status === "reopened").length;
  const critical     = items.filter((r) => r.priority === "critical" && ACTIVE_ST.includes(r.status)).length;
  const slaBreached  = items.filter((r) => r.slaElapsed > r.slaHours && ACTIVE_ST.includes(r.status)).length;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Total service"   value={total}        icon={Inbox}               tone="primary"      loading={isLoading} hint={directionId ? `Direction ${directionId}` : undefined} />
        <Stat label="Ouvertes"        value={open}         icon={Clock}               tone="accent"        loading={isLoading} />
        <Stat label="En cours"        value={inProgress}   icon={Clock}               tone="accent"       loading={isLoading} />
        <Stat label="En attente"      value={pendingCount} icon={MessageSquareWarning} tone="warning"     loading={isLoading} />
        <Stat label="CSAT service"    value={(csat?.global ?? 0) > 0 ? `${csat!.global}/5` : "—"} icon={Star} tone="primary" />
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Escaladées"    value={escalated}   icon={AlertTriangle} tone="warning"     loading={isLoading} />
        <Stat label="SLA dépassés"  value={slaBreached} icon={ArrowUpRight}  tone="destructive" loading={isLoading} hint="Tickets en retard" />
        <Stat label="Réouvertes"    value={reopened}    icon={RotateCcw}     tone="warning"     loading={isLoading} />
        <Stat label="Critiques"     value={critical}    icon={AlertTriangle} tone="destructive" loading={isLoading} hint="Priorité critique active" />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={items.slice(0, 5)} isLoading={isLoading} />
        <StatusPie  data={items}              isLoading={isLoading} />
      </div>
    </>
  );
}

function DirectorDashboard() {
  const sessionUser = useUser();
  const directionId = sessionUser?.direction_id;

  const { data, isLoading } = useQuery({
    queryKey: ["director-requests", directionId],
    queryFn: () => fetchRequests({ direction_id: directionId, limit: 200 }),
    enabled: !!sessionUser,
    staleTime: 30_000,
  });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  const ACTIVE_ST = ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"];
  const open         = items.filter((r) => ACTIVE_ST.includes(r.status)).length;
  const inProgress   = items.filter((r) => r.status === "in_progress").length;
  const pendingCount = items.filter((r) => r.status === "pending").length;
  const escalated    = items.filter((r) => r.status === "escalated").length;
  const reopened     = items.filter((r) => r.status === "reopened").length;
  const critical     = items.filter((r) => r.priority === "critical" && ACTIVE_ST.includes(r.status)).length;
  const slaBreached  = items.filter((r) => r.slaElapsed > r.slaHours && ACTIVE_ST.includes(r.status)).length;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Total direction"  value={total}        icon={Inbox}                tone="primary"      loading={isLoading} hint={directionId ? `Direction ${directionId.toUpperCase()}` : undefined} />
        <Stat label="Ouvertes"         value={open}         icon={Clock}                tone="accent"       loading={isLoading} />
        <Stat label="En cours"         value={inProgress}   icon={Clock}                tone="accent"       loading={isLoading} />
        <Stat label="En attente"       value={pendingCount} icon={MessageSquareWarning} tone="warning"      loading={isLoading} />
        <Stat label="CSAT direction"   value={(csat?.global ?? 0) > 0 ? `${csat!.global}/5` : "—"} icon={Star} tone="success" />
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Escaladées"    value={escalated}   icon={AlertTriangle} tone="warning"     loading={isLoading} />
        <Stat label="SLA dépassés"  value={slaBreached} icon={ArrowUpRight}  tone="destructive" loading={isLoading} hint="Tickets en retard" />
        <Stat label="Réouvertes"    value={reopened}    icon={RotateCcw}     tone="warning"     loading={isLoading} />
        <Stat label="Critiques"     value={critical}    icon={AlertTriangle} tone="destructive" loading={isLoading} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={items.slice(0, 5)} isLoading={isLoading} />
        <StatusPie  data={items}              isLoading={isLoading} />
      </div>
    </>
  );
}

const DG_ACTIVE = new Set(["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"]);

function DgDashboard() {
  const { data: stats, isLoading } = useQuery({ queryKey: ["req-stats"], queryFn: fetchRequestStats, staleTime: 30_000 });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });
  const { data: allReqData, isLoading: loadAllReq } = useQuery({
    queryKey: ["dg-dashboard-requests"],
    queryFn: () => fetchRequests({ limit: 500 }),
    staleTime: 30_000,
  });

  const total    = totalStats(stats);
  const open     = sumStats(stats, ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"]);
  const resolved = sumStats(stats, ["resolved", "closed"]);

  const allItems = allReqData?.items ?? [];

  const dirStats = useMemo(() => {
    const map = new Map<string, { open: number; slaOk: number; total: number }>();
    allItems.forEach((r) => {
      const did = r.directionId ?? "unknown";
      const entry = map.get(did) ?? { open: 0, slaOk: 0, total: 0 };
      entry.total += 1;
      if (DG_ACTIVE.has(r.status)) {
        entry.open += 1;
        if (r.slaElapsed <= r.slaHours) entry.slaOk += 1;
      }
      map.set(did, entry);
    });
    return [...map.entries()].map(([id, s]) => ({
      id,
      total: s.total,
      slaRespect: s.open > 0 ? Math.round((s.slaOk / s.open) * 100) : 100,
    }));
  }, [allItems]);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Directions"       value={loadAllReq ? "…" : dirStats.length} icon={Building2}    tone="primary"  loading={loadAllReq} />
        <Stat label="Demandes totales" value={total}                               icon={Inbox}        tone="accent"   loading={isLoading} />
        <Stat label="Ouvertes"         value={open}                                icon={Clock}        tone="warning"  loading={isLoading} />
        <Stat label="Résolues"         value={resolved}                            icon={CheckCircle2} tone="success"  loading={isLoading} />
        <Stat label="CSAT global"      value={(csat?.global ?? 0) > 0 ? `${csat!.global}/5` : "—"} icon={Star} tone="warning" />
      </div>
      <GlassCard>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="font-semibold">Performance par direction</h3>
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
        </div>
        {loadAllReq ? (
          <div className="flex h-24 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
          </div>
        ) : dirStats.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucune donnée disponible.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {dirStats.map((s) => {
              const tone =
                s.slaRespect > 80
                  ? "bg-success/20 text-success border-success/30"
                  : s.slaRespect > 60
                    ? "bg-info/15 text-info border-info/30"
                    : s.slaRespect > 45
                      ? "bg-warning/20 text-warning border-warning/30"
                      : "bg-destructive/15 text-destructive border-destructive/30";
              return (
                <div key={s.id} className={"rounded-2xl border p-4 " + tone}>
                  <div className="text-xs font-medium uppercase tracking-wider opacity-70">{s.id.toUpperCase()}</div>
                  <div className="mt-3 text-2xl font-bold">{s.slaRespect}%</div>
                  <div className="text-[11px] opacity-70">SLA respecté · {s.total} dem.</div>
                </div>
              );
            })}
          </div>
        )}
      </GlassCard>
    </>
  );
}

function AdminDashboard() {
  const { data: stats, isLoading } = useQuery({ queryKey: ["req-stats"], queryFn: fetchRequestStats, staleTime: 30_000 });
  const { data: recentData, isLoading: loadRecent } = useQuery({
    queryKey: ["recent-requests"],
    queryFn: () => fetchRequests({ limit: 5 }),
    staleTime: 30_000,
  });
  const { data: directionsData, isLoading: loadDirs } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 60_000,
  });

  const total  = totalStats(stats);
  const open   = sumStats(stats, ["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"]);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Directions"       value={directionsData?.length ?? 0} icon={Building2}    tone="accent"   loading={loadDirs} />
        <Stat label="Demandes totales" value={total}                        icon={Inbox}        tone="primary"  loading={isLoading} />
        <Stat label="Ouvertes"         value={open}                         icon={Clock}        tone="warning"  loading={isLoading} />
        <Stat label="Système"          value="OK"                           icon={CheckCircle2} tone="success"  />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <GlassCard>
          <h3 className="mb-4 font-semibold">Accès rapides administration</h3>
          <div className="grid gap-2 sm:grid-cols-2">
            {[
              { to: "/app/admin/users",     label: "Utilisateurs & Rôles",  icon: Users2 },
              { to: "/app/admin/directions", label: "Directions & Services", icon: Building2 },
              { to: "/app/admin/sla",        label: "SLA & Priorités",       icon: Clock },
              { to: "/app/admin/logs",       label: "Journaux d'activité",   icon: Inbox },
            ].map((q) => (
              <Link
                key={q.label}
                to={q.to}
                className="flex items-center gap-3 rounded-2xl border border-border/50 bg-background/50 p-4 transition hover:border-primary/40 hover:bg-primary/5"
              >
                <q.icon className="h-5 w-5 text-primary" />
                <span className="text-sm font-medium">{q.label}</span>
              </Link>
            ))}
          </div>
        </GlassCard>
        <StatusPie data={recentData?.items ?? []} isLoading={loadRecent} />
      </div>
      <RecentList items={recentData?.items ?? []} isLoading={loadRecent} />
    </>
  );
}
