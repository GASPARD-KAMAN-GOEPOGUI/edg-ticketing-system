import { createFileRoute, Link } from "@tanstack/react-router";
import { useRole, useUser } from "@/lib/session";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { statusLabels } from "@/lib/mock-data";
import type { RequestItem } from "@/lib/mock-data";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchCsatStats } from "@/lib/api/csat";
import { fetchQueue, fetchRequests, fetchRequestStats, fetchTriage } from "@/lib/api/requests";
import type { RequestStats } from "@/lib/api/requests";
import { fetchNotifications } from "@/lib/api/notifications";
import { fetchDirections } from "@/lib/api/directions-units";
import {
  ticketDetailRouteForList,
  type TicketDetailRoute,
  type TicketListRoute,
} from "@/lib/ticket-navigation";
import {
  ArrowRight,
  Bell,
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
  SlidersHorizontal,
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

export const Route = createFileRoute("/app/")({
  head: () => ({ meta: [{ title: "Tableau de bord — EDG Support" }] }),
  component: Dashboard,
});

function Dashboard() {
  const sessionUser = useUser();
  const firstName = sessionUser?.name?.split(" ")[0] || null;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {firstName ? `Bonjour, ${firstName} 👋` : "Bonjour 👋"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Voici l'état de vos demandes personnelles.
          </p>
        </div>
        <Button asChild className="rounded-full gradient-primary shadow-lg shadow-primary/30">
          <Link to="/app/new">
            <Plus className="mr-1 h-4 w-4" /> Nouvelle demande
          </Link>
        </Button>
      </header>

      <PersonalDashboard />
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

const PERSONAL_ACTIVE_STATUSES = new Set<RequestItem["status"]>([
  "new",
  "qualifying",
  "qualified",
  "assigned",
  "in_progress",
  "pending",
  "resolved",
  "reopened",
  "escalated",
]);

function isActivePersonalRequest(request: RequestItem): boolean {
  return PERSONAL_ACTIVE_STATUSES.has(request.status);
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

function RecentList({
  items,
  isLoading,
  title = "Demandes récentes",
  to = "/app/requests",
  detailTo,
  wide = true,
  className = "",
  limit = 5,
}: {
  items: RequestItem[];
  isLoading?: boolean;
  title?: string;
  to?: TicketListRoute;
  detailTo?: TicketDetailRoute;
  wide?: boolean;
  className?: string;
  limit?: number;
}) {
  const detailRoute = detailTo ?? ticketDetailRouteForList(to);
  const { data: dirs = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 60_000,
  });
  return (
    <GlassCard className={`p-4 sm:p-6 ${wide ? "lg:col-span-2" : ""} ${className}`}>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="min-w-0 truncate font-semibold">{title}</h3>
        <Button asChild variant="ghost" size="sm" className="rounded-full">
          <Link to={to}>
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
          {items.slice(0, limit).map((r) => (
            <li key={r.id}>
              <Link
                to={detailRoute}
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

/* ─── Accueil personnel ───────────────────────────────────────────────────── */

function PersonalRoleShortcuts() {
  const [role] = useRole();
  const shortcutsByRole: Record<string, { to: string; label: string; description: string; icon: typeof Inbox }[]> = {
    user: [],
    agent: [
      { to: "/app/my-tickets", label: "Mes tickets", description: "Tickets qui me sont assignés", icon: Users2 },
      { to: "/app/queue", label: "File d'attente", description: "Tickets orientés à traiter", icon: Inbox },
    ],
    chief: [
      { to: "/app/chief-inbox", label: "Boîte de traitement", description: "Tickets du service à organiser", icon: MessageSquareWarning },
      { to: "/app/queue", label: "File d'attente", description: "Demandes orientées et à qualifier", icon: Inbox },
      { to: "/app/supervision", label: "Supervision", description: "Suivi de l'activité du service", icon: AlertTriangle },
      { to: "/app/reports", label: "Rapports", description: "Indicateurs du service", icon: TrendingUp },
    ],
    director: [
      { to: "/app/supervision", label: "Supervision", description: "Tickets escaladés ou à arbitrer", icon: AlertTriangle },
      { to: "/app/direction", label: "Vue direction", description: "Pilotage des services de la direction", icon: Building2 },
      { to: "/app/sla-center", label: "Centre SLA", description: "Suivi des délais et risques", icon: Clock },
      { to: "/app/reports", label: "Rapports Direction", description: "Performance par service", icon: TrendingUp },
    ],
    admin: [
      { to: "/app/dg", label: "Vue globale", description: "Pilotage inter-directions", icon: Building2 },
      { to: "/app/admin/users", label: "Utilisateurs & rôles", description: "Administration des comptes", icon: Users2 },
      { to: "/app/admin/directions", label: "Directions", description: "Structure de l'organisation", icon: Building2 },
      { to: "/app/admin/routing", label: "Routage", description: "Règles métier des demandes", icon: SlidersHorizontal },
      { to: "/app/admin/sla", label: "SLA & politiques", description: "Paramètres de délais", icon: Clock },
    ],
  };
  const shortcuts = shortcutsByRole[role] ?? [];
  if (shortcuts.length === 0) return null;

  return (
    <GlassCard className="p-4 sm:p-6">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="font-semibold">Accès métier séparé</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            Ces raccourcis ouvrent les espaces de traitement, pilotage ou administration. Ils ne changent pas vos données personnelles.
          </p>
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-muted-foreground" />
      </div>
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {shortcuts.map((shortcut) => {
          const Icon = shortcut.icon;
          return (
            <Link
              key={shortcut.to}
              to={shortcut.to as never}
              className="flex items-start gap-3 rounded-2xl border border-border/50 bg-background/50 p-4 transition hover:border-primary/40 hover:bg-primary/5"
            >
              <Icon className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
              <span className="min-w-0">
                <span className="block text-sm font-semibold">{shortcut.label}</span>
                <span className="mt-0.5 block text-xs text-muted-foreground">{shortcut.description}</span>
              </span>
            </Link>
          );
        })}
      </div>
    </GlassCard>
  );
}

function PersonalDashboard() {
  const sessionUser = useUser();
  const { data, isLoading } = useQuery({
    queryKey: ["my-requests", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, limit: 100 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });
  const { data: cancelledData } = useQuery({
    queryKey: ["my-cancelled", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, request_status: "cancelled" }),
    enabled: !!sessionUser?.id,
    staleTime: 60_000,
  });
  const items             = data?.items ?? [];
  const activeItems       = items.filter(isActivePersonalRequest);
  const recentActiveItems = activeItems.slice(0, 3);
  const total             = data?.total ?? 0;
  const active            = activeItems.length;
  const done              = items.filter((r) => ["resolved", "closed"].includes(r.status)).length;
  const cancelled         = cancelledData?.total ?? 0;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Demandes créées"   value={total}     icon={Inbox}        tone="primary"      hint="Au total" loading={isLoading} />
        <Stat label="En cours"          value={active}    icon={Clock}        tone="accent"        loading={isLoading} />
        <Stat label="Résolues"          value={done}      icon={CheckCircle2} tone="success"       loading={isLoading} />
        <Stat label="Annulées"          value={cancelled} icon={AlertTriangle} tone="destructive"  loading={isLoading} />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={recentActiveItems} isLoading={isLoading} limit={3} />
        <StatusPie  data={items}  isLoading={isLoading} />
      </div>
      <PersonalRoleShortcuts />
    </>
  );
}

function AgentDashboard() {
  const sessionUser = useUser();
  const { data: assignedData, isLoading: loadAssigned } = useQuery({
    queryKey: ["agent-dashboard", "assigned", sessionUser?.id],
    queryFn: () => fetchQueue({ assignee_id: sessionUser!.id, limit: 200 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });

  const { data: queueData, isLoading: loadQueue } = useQuery({
    queryKey: ["agent-dashboard", "queue", sessionUser?.id, sessionUser?.direction_id, sessionUser?.unit_id],
    queryFn: () => fetchQueue({ limit: 200 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });

  const { data: triageData, isLoading: loadTriage } = useQuery({
    queryKey: ["agent-dashboard", "triage", sessionUser?.id],
    queryFn: () => fetchTriage({ limit: 100 }),
    enabled: !!sessionUser?.id,
    staleTime: 20_000,
  });

  const { data: myRequestsData, isLoading: loadMyRequests } = useQuery({
    queryKey: ["agent-dashboard", "my-requests", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, limit: 50 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });

  const { data: unreadNotifications, isLoading: loadNotifications } = useQuery({
    queryKey: ["agent-dashboard", "notifications", sessionUser?.id],
    queryFn: () => fetchNotifications({ meId: sessionUser!.id, unread: true, limit: 1 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
  });

  const assigned = assignedData?.items ?? [];
  const queued = queueData?.items ?? [];
  const myRequests = myRequestsData?.items ?? [];
  const inProgress = assigned.filter((r) => r.status === "in_progress").length;
  const pendingCount = assigned.filter((r) => r.status === "pending").length;
  const escalatedMine = assigned.filter((r) => r.status === "escalated").length;
  const reopenedCount = assigned.filter((r) => r.status === "reopened").length;
  const slaBreachedMine = assigned.filter((r) => r.slaElapsed > r.slaHours).length;

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        <Stat label="File d'attente" value={queueData?.total ?? 0} icon={Inbox} tone="primary" loading={loadQueue} hint="Tickets orientés" />
        <Stat label="À qualifier" value={triageData?.total ?? 0} icon={SlidersHorizontal} tone="warning" loading={loadTriage} hint="Demandes non orientées" />
        <Stat label="Mes tickets" value={assignedData?.total ?? 0} icon={Users2} tone="accent" loading={loadAssigned} hint="Assignés à moi" />
        <Stat label="Mes demandes" value={myRequestsData?.total ?? 0} icon={Plus} tone="success" loading={loadMyRequests} hint="Créées par moi" />
        <Stat label="Non lues" value={unreadNotifications?.total ?? 0} icon={Bell} tone="destructive" loading={loadNotifications} hint="Notifications" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="En cours" value={inProgress} icon={Clock} tone="accent" loading={loadAssigned} hint="Mes tickets actifs" />
        <Stat label="En attente" value={pendingCount} icon={MessageSquareWarning} tone="warning" loading={loadAssigned} hint="Attente demandeur" />
        <Stat label="SLA dépassés" value={slaBreachedMine} icon={AlertTriangle} tone="destructive" loading={loadAssigned} hint="Mes tickets en retard" />
        <Stat label="Réouverts / escaladés" value={reopenedCount + escalatedMine} icon={ArrowUpRight} tone="warning" loading={loadAssigned} />
      </div>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.45fr)_minmax(320px,0.55fr)]">
        <RecentList
          title="Mes tickets récents"
          to="/app/my-tickets"
          items={assigned}
          isLoading={loadAssigned}
          wide={false}
          className="xl:min-h-[420px]"
          limit={6}
        />
        <div className="grid gap-4">
          <StatusPie data={assigned} isLoading={loadAssigned} />
          <GlassCard className="p-4 sm:p-6">
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 className="font-semibold">Accès agent</h3>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>
            <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
              <Button asChild variant="outline" className="justify-start rounded-2xl">
                <Link to="/app/my-tickets">
                  <Users2 className="mr-2 h-4 w-4" /> Mes tickets
                </Link>
              </Button>
              <Button asChild variant="outline" className="justify-start rounded-2xl">
                <Link to="/app/queue">
                  <Inbox className="mr-2 h-4 w-4" /> File d'attente
                </Link>
              </Button>
              <Button asChild variant="outline" className="justify-start rounded-2xl">
                <Link to="/app/queue" search={{ tab: "qualify" }}>
                  <SlidersHorizontal className="mr-2 h-4 w-4" /> À qualifier
                </Link>
              </Button>
              <Button asChild variant="outline" className="justify-start rounded-2xl">
                <Link to="/app/notifications">
                  <Bell className="mr-2 h-4 w-4" /> Notifications
                </Link>
              </Button>
            </div>
          </GlassCard>
        </div>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <RecentList
          title="File d'attente récente"
          to="/app/queue"
          items={queued}
          isLoading={loadQueue}
          wide={false}
        />
        <RecentList
          title="Mes demandes récentes"
          to="/app/requests"
          items={myRequests}
          isLoading={loadMyRequests}
          wide={false}
        />
      </div>
    </>
  );
}
function ChiefDashboard() {
  const sessionUser = useUser();
  const serviceId = sessionUser?.unit_id;

  const { data, isLoading } = useQuery({
    queryKey: ["chief-requests", serviceId],
    queryFn: () => fetchRequests({ unit_id: serviceId, limit: 200 }),
    enabled: !!serviceId,
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
        <Stat label="Total service"   value={total}        icon={Inbox}               tone="primary"      loading={isLoading} hint={serviceId ? `Service ${serviceId}` : undefined} />
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
        <RecentList
          title="Tickets du service"
          to="/app/supervision"
          detailTo="/app/supervision/tickets/$id"
          items={items.slice(0, 5)}
          isLoading={isLoading}
        />
        <StatusPie  data={items}              isLoading={isLoading} />
      </div>
    </>
  );
}

function DirectorDashboard() {
  const sessionUser = useUser();
  const directionId = sessionUser?.direction_id ?? (
    sessionUser?.role === "director" ? sessionUser?.unit_id : undefined
  );

  const { data, isLoading } = useQuery({
    queryKey: ["director-requests", directionId],
    queryFn: () => fetchRequests({ direction_id: directionId, limit: 200 }),
    enabled: !!directionId,
    staleTime: 30_000,
  });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });

  if (!directionId) {
    return (
      <GlassCard className="flex min-h-[320px] flex-col items-center justify-center gap-3 py-16 text-center">
        <div className="rounded-full bg-warning/15 p-4 text-warning">
          <AlertTriangle className="h-8 w-8" />
        </div>
        <h3 className="text-xl font-semibold">Direction non renseignée</h3>
        <p className="max-w-md text-sm text-muted-foreground">
          Votre accueil directeur affichera les données dès que votre compte sera rattaché à une direction.
        </p>
      </GlassCard>
    );
  }

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
        <RecentList
          title="Tickets de la direction"
          to="/app/direction"
          detailTo="/app/direction/tickets/$id"
          items={items.slice(0, 5)}
          isLoading={isLoading}
        />
        <StatusPie  data={items}              isLoading={isLoading} />
      </div>
    </>
  );
}

const GLOBAL_ACTIVE = new Set(["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"]);

function GlobalDashboard() {
  const { data: stats, isLoading } = useQuery({ queryKey: ["req-stats"], queryFn: fetchRequestStats, staleTime: 30_000 });
  const { data: csat } = useQuery({ queryKey: ["csat-stats"], queryFn: fetchCsatStats, staleTime: 300_000 });
  const { data: allReqData, isLoading: loadAllReq } = useQuery({
    queryKey: ["global-dashboard-requests"],
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
      if (GLOBAL_ACTIVE.has(r.status)) {
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
      <RecentList
        title="Tickets récents"
        to="/app/admin/users"
        detailTo="/app/admin/tickets/$id"
        items={recentData?.items ?? []}
        isLoading={loadRecent}
      />
    </>
  );
}
