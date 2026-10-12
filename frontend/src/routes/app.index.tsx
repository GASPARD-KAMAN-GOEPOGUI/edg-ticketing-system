import { createFileRoute, Link } from "@tanstack/react-router";
import { useUser } from "@/lib/session";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import type { RequestItem } from "@/lib/mock-data";
import { useMemo } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { fetchMyRequestsStats, fetchRequests } from "@/lib/api/requests";
import { fetchDirections } from "@/lib/api/directions-units";
import { ticketDetailRouteForList, type TicketListRoute } from "@/lib/ticket-navigation";
import {
  RECENT_EXCLUDED_STATUSES,
  computeHomeCounts,
  donutSegments,
  type DonutSegment,
} from "@/lib/home-dashboard";
import { ArrowRight, Clock, Inbox, Plus, CheckCircle2, AlertTriangle } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";

export const Route = createFileRoute("/app/")({
  head: () => ({ meta: [{ title: "Tableau de bord — EDG Support" }] }),
  component: Dashboard,
});

// Temps réel : les clés ["my-requests-stats"] et ["my-requests"] sont
// invalidées par tout événement SSE `request.*` (lib/realtime/invalidation-map).
// staleTime ne sert qu'à éviter un refetch au simple remontage de la page.
const STALE_MS = 30_000;

function Dashboard() {
  const sessionUser = useUser();
  const fullName = sessionUser
    ? sessionUser.firstname
      ? `${sessionUser.firstname} ${sessionUser.name}`
      : sessionUser.name
    : null;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {fullName ? `Bonjour, ${fullName} 👋` : "Bonjour 👋"}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Voici l'état de vos tickets personnels.
          </p>
        </div>
        <Button asChild className="rounded-full gradient-primary shadow-lg shadow-primary/30">
          <Link to="/app/new">
            <Plus className="mr-1 h-4 w-4" /> Nouveau ticket
          </Link>
        </Button>
      </header>

      <PersonalDashboard userId={sessionUser?.id} />
    </div>
  );
}

/* ─── Accueil personnel ───────────────────────────────────────────────────── */

function PersonalDashboard({ userId }: { userId?: string }) {
  // Compteurs calculés en SQL : une seule réponse de quelques octets.
  const { data: stats, isLoading: statsLoading } = useQuery({
    queryKey: ["my-requests-stats", userId],
    queryFn: fetchMyRequestsStats,
    enabled: !!userId,
    staleTime: STALE_MS,
    placeholderData: keepPreviousData,
  });
  // Seulement les 3 tickets affichés, déjà filtrés par le serveur.
  const { data: recent, isLoading: recentLoading } = useQuery({
    queryKey: ["my-requests", "recent-active", userId],
    queryFn: () =>
      fetchRequests({ requester_id: userId!, exclude_status: RECENT_EXCLUDED_STATUSES, limit: 3 }),
    enabled: !!userId,
    staleTime: STALE_MS,
    placeholderData: keepPreviousData,
  });

  const counts = useMemo(
    () => computeHomeCounts(stats?.byStatus ?? {}, stats?.total ?? 0),
    [stats],
  );
  const segments = useMemo(() => donutSegments(stats?.byStatus ?? {}), [stats]);

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Tickets créés"
          value={counts.total}
          icon={Inbox}
          tone="primary"
          hint="Au total"
          loading={statsLoading}
        />
        <Stat
          label="En cours"
          value={counts.active}
          icon={Clock}
          tone="accent"
          loading={statsLoading}
        />
        <Stat
          label="Résolues"
          value={counts.done}
          icon={CheckCircle2}
          tone="success"
          loading={statsLoading}
        />
        <Stat
          label="Annulées"
          value={counts.cancelled}
          icon={AlertTriangle}
          tone="destructive"
          loading={statsLoading}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <RecentList items={recent?.items ?? []} isLoading={recentLoading} />
        <StatusRing segments={segments} isLoading={statsLoading} />
      </div>
    </>
  );
}

/* ─── Composants ─────────────────────────────────────────────────────────── */

function Stat({
  label,
  value,
  hint,
  icon: Icon,
  tone = "primary",
  loading = false,
}: {
  label: string;
  value: number;
  hint?: string;
  icon: typeof Inbox;
  tone?: "primary" | "success" | "destructive" | "accent";
  loading?: boolean;
}) {
  const toneMap = {
    primary: "bg-primary/10 text-primary",
    success: "bg-success/15 text-success",
    destructive: "bg-destructive/15 text-destructive",
    accent: "bg-accent/15 text-accent",
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
          // Squelette à la taille exacte du chiffre : aucun saut de mise en page.
          <div className="h-9 w-16 animate-pulse rounded-lg bg-muted" aria-hidden />
        ) : (
          <div className="text-3xl font-bold tracking-tight tabular-nums">{value}</div>
        )}
        {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
      </div>
    </GlassCard>
  );
}

const RECENT_LIST_ROUTE: TicketListRoute = "/app/requests";

function RecentList({ items, isLoading }: { items: RequestItem[]; isLoading: boolean }) {
  const detailRoute = ticketDetailRouteForList(RECENT_LIST_ROUTE);
  // Référentiel partagé avec le reste de l'application (même clé de cache).
  const { data: dirs = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections(),
    staleTime: 10 * 60_000,
  });
  const dirNames = useMemo(() => new Map(dirs.map((d) => [String(d.id), d.name])), [dirs]);

  return (
    <GlassCard className="p-4 sm:p-6 lg:col-span-2">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="min-w-0 truncate font-semibold">Tickets récents</h3>
        <Button asChild variant="ghost" size="sm" className="rounded-full">
          <Link to={RECENT_LIST_ROUTE}>
            Voir tout <ArrowRight className="ml-1 h-3.5 w-3.5" />
          </Link>
        </Button>
      </div>
      {isLoading ? (
        <ul className="space-y-1.5" aria-hidden>
          {[0, 1, 2].map((i) => (
            <li key={i} className="space-y-2 rounded-2xl p-3">
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
              <div className="h-4 w-3/4 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/2 animate-pulse rounded bg-muted" />
            </li>
          ))}
        </ul>
      ) : items.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Aucun ticket.</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((r) => (
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
                <div className="mt-1.5 line-clamp-2 text-sm font-medium leading-snug sm:line-clamp-1">
                  {r.title}
                </div>
                {/* Ligne 3 : direction (ou catégorie) + date */}
                <div className="mt-0.5 text-xs text-muted-foreground">
                  {dirNames.get(String(r.directionId)) ?? r.category}
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

/** Anneau SVG natif — remplace le camembert Recharts (librairie entière chargée
 *  pour une seule forme). Survol : libellé et valeur via <title>. */
function StatusRing({ segments, isLoading }: { segments: DonutSegment[]; isLoading: boolean }) {
  const radius = 15.9155; // circonférence = 100 : les longueurs s'expriment en %
  return (
    <GlassCard className="p-4 sm:p-6">
      <h3 className="mb-2 font-semibold">Répartition par statut</h3>
      {isLoading ? (
        <div className="flex h-56 items-center justify-center" aria-hidden>
          <div className="h-36 w-36 animate-pulse rounded-full border-[14px] border-muted" />
        </div>
      ) : segments.length === 0 ? (
        <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">
          Aucune donnée
        </div>
      ) : (
        <>
          <div className="flex h-44 items-center justify-center sm:h-56">
            <svg
              viewBox="0 0 42 42"
              className="h-full max-h-40 w-auto -rotate-90 sm:max-h-48"
              role="img"
              aria-label={segments.map((s) => `${s.label} : ${s.value}`).join(", ")}
            >
              {segments.map((s) => (
                <circle
                  key={s.key}
                  cx="21"
                  cy="21"
                  r={radius}
                  fill="none"
                  stroke={s.color}
                  strokeWidth="5"
                  strokeDasharray={`${s.length * 100} ${100 - s.length * 100}`}
                  strokeDashoffset={-s.offset * 100}
                  className="transition-[stroke-dasharray,stroke-dashoffset] duration-500"
                >
                  <title>{`${s.label} : ${s.value}`}</title>
                </circle>
              ))}
            </svg>
          </div>
          <ul className="mt-1 grid grid-cols-1 gap-1 text-xs sm:grid-cols-2 sm:gap-1.5">
            {segments.map((s) => (
              <li key={s.key} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: s.color }} />
                <span className="min-w-0 truncate text-muted-foreground">{s.label}</span>
                <span className="ml-auto shrink-0 font-medium tabular-nums">{s.value}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </GlassCard>
  );
}
