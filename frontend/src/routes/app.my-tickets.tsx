import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useUser } from "@/lib/session";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fetchUsersByIds, buildAvatarUrl } from "@/lib/api/accounts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchRequests, fetchTransmittedByMe } from "@/lib/api/requests";
import { priorityLabels, statusLabels } from "@/lib/mock-data";
import type { RequestItem, RequestStatus, Priority } from "@/lib/mock-data";
import {
  Ticket, Clock, Search, Inbox,
  AlertTriangle, CheckCircle2, RotateCcw, Send, Repeat2,
} from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { useSessionState } from "@/lib/use-session-state";
import { cn, initialsFor, formatElapsedHours } from "@/lib/utils";
import { getUser } from "@/lib/session";
import { prefetch } from "@/lib/prefetch";

const ACTIVE_STATUSES: RequestStatus[] = [
  "new", "qualifying", "qualified", "assigned",
  "in_progress", "pending", "escalated", "reopened",
];
const TERMINAL_STATUSES = "resolved,closed,cancelled,rejected";

export const Route = createFileRoute("/app/my-tickets")({
  beforeLoad: () => requireRole("chief-service", "technicien", "chef-division-support", "admin"),
  head: () => ({ meta: [{ title: "Mes tickets — EDG Support" }] }),
  // Précharge la vue par défaut (sans filtre) au survol du lien — même
  // queryKey que le useQuery du composant tant qu'aucun filtre n'est appliqué,
  // donc réutilisé directement sans refetch si l'utilisateur arrive filtres neutres.
  loader: ({ context: { queryClient } }) => {
    const uid = getUser()?.id;
    if (!uid) return;
    return prefetch(queryClient.ensureQueryData({
      queryKey: ["my-tickets", { assignee_id: uid, exclude_status: TERMINAL_STATUSES }],
      queryFn: () => fetchRequests({ assignee_id: uid, exclude_status: TERMINAL_STATUSES, page: 1, limit: 1000 }),
      staleTime: 30_000,
    }));
  },
  component: MyTicketsPage,
});

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

function MyTicketsPage() {
  const sessionUser = useUser();
  const navigate = useNavigate();

  const [filterStatus, setFilterStatus] = useSessionState<string>("mt:status", "all");
  const [filterPriority, setFilterPriority] = useSessionState<string>("mt:priority", "all");
  const [search, setSearch] = useSessionState<string>("mt:q", "");
  const [debouncedSearch, setDebouncedSearch] = useState(search);
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const currentUserId = sessionUser?.id ? String(sessionUser.id) : "";
  const role = sessionUser?.role;
  // Le seul role qui voyait les escalades de son perimetre ici
  // (chief-departement) a ete retire le 2026-09-25.
  const includeScopedEscalations = false;
  const showScopedEscalations =
    includeScopedEscalations && (filterStatus === "all" || filterStatus === "escalated");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => { setPage(1); }, [filterStatus, filterPriority, debouncedSearch]);

  // Ancien raccourci "Réouvertures" : il écrivait mt:status=reopened en session.
  // Depuis son retrait, l'ouverture normale de Ma boîte doit revenir à tous les statuts.
  useEffect(() => {
    const status = new URLSearchParams(window.location.search).get("status");
    if (status) {
      setFilterStatus(status);
      return;
    }
    const cleanupKey = "mt:reopened-shortcut-cleaned";
    if (filterStatus === "reopened" && sessionStorage.getItem(cleanupKey) !== "1") {
      setFilterStatus("all");
      sessionStorage.setItem(cleanupKey, "1");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const baseFilters = {
    assignee_id: currentUserId,
    exclude_status: TERMINAL_STATUSES,
    ...(filterPriority !== "all" && { priority: filterPriority }),
    ...(filterStatus !== "all" && { request_status: filterStatus }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };
  const scopedEscalationFilters = {
    request_status: "escalated" as RequestStatus,
    ...(filterPriority !== "all" && { priority: filterPriority }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };

  // Requête principale : tickets assignés à l'intervenant connecté.
  const { data, isLoading, isError } = useQuery({
    queryKey: ["my-tickets", baseFilters],
    queryFn: () => fetchRequests({ ...baseFilters, page: 1, limit: 1000 }),
    staleTime: 30_000,
    enabled: !!currentUserId,
  });

  // Les escalades du périmètre chef sont traitées depuis Ma boîte, pas depuis Répartition.
  const {
    data: scopedEscalationsData,
    isLoading: scopedEscalationsLoading,
    isError: scopedEscalationsError,
  } = useQuery({
    queryKey: ["my-tickets", "scoped-escalations", scopedEscalationFilters, role],
    queryFn: () => fetchRequests({ ...scopedEscalationFilters, page: 1, limit: 1000 }),
    staleTime: 30_000,
    enabled: !!currentUserId && showScopedEscalations,
  });

  // Requête stats : workload affectée à l'agent connecté, indépendamment des
  // filtres appliqués à la liste affichée (les KPI doivent refléter la charge
  // totale, pas la vue filtrée). Quand aucun filtre n'est actif, `baseFilters`/
  // `scopedEscalationFilters` sont déjà identiques à ces requêtes stats — on
  // réutilise alors `data`/`scopedEscalationsData` au lieu de refaire le même
  // appel réseau une seconde fois.
  const mainFiltersNeutral = filterPriority === "all" && filterStatus === "all" && !debouncedSearch;
  // Ne réutiliser scopedEscalationsData que s'il a effectivement été fetché
  // avec exactement les mêmes filtres (showScopedEscalations=false → non fetché).
  const scopedFiltersNeutral = filterPriority === "all" && !debouncedSearch && showScopedEscalations;

  const { data: statsDataFetched } = useQuery({
    queryKey: ["my-tickets-stats", currentUserId],
    queryFn: () => fetchRequests({ assignee_id: currentUserId, exclude_status: TERMINAL_STATUSES, limit: 1000 }),
    staleTime: 60_000,
    enabled: !!currentUserId && !mainFiltersNeutral,
  });
  const statsData = mainFiltersNeutral ? data : statsDataFetched;

  const { data: scopedEscalationsStatsDataFetched } = useQuery({
    queryKey: ["my-tickets-stats", "scoped-escalations", currentUserId, role],
    queryFn: () => fetchRequests({ request_status: "escalated", limit: 1000 }),
    staleTime: 60_000,
    enabled: !!currentUserId && includeScopedEscalations && !scopedFiltersNeutral,
  });
  const scopedEscalationsStatsData = scopedFiltersNeutral
    ? scopedEscalationsData
    : scopedEscalationsStatsDataFetched;

  // KPI "Transmis"/"Retransmis" — comptages issus de /requests/transmitted
  // (BR-TRANSMIT-001/BR-RETRANSMIT-001), indépendants de assignee_id puisqu'un
  // ticket transmis n'est plus assigné à l'agent : besoin d'une requête dédiée.
  const { data: transmittedCountData } = useQuery({
    queryKey: ["my-tickets-transmitted-count", currentUserId],
    queryFn: () => fetchTransmittedByMe({ limit: 1 }),
    staleTime: 60_000,
    enabled: !!currentUserId,
  });
  const { data: retransmittedCountData } = useQuery({
    queryKey: ["my-tickets-retransmitted-count", currentUserId],
    queryFn: () => fetchTransmittedByMe({ limit: 1, retransmitted_only: true }),
    staleTime: 60_000,
    enabled: !!currentUserId,
  });
  const kpiTransmitted = transmittedCountData?.total ?? 0;
  const kpiRetransmitted = retransmittedCountData?.total ?? 0;

  const onlyMyAssignedTickets = (items?: RequestItem[]) =>
    (items ?? []).filter((r) => r.assigneeId === currentUserId);
  const mergeTickets = (assignedItems?: RequestItem[], scopedItems?: RequestItem[]) => {
    const byId = new Map<string, RequestItem>();
    for (const item of onlyMyAssignedTickets(assignedItems)) byId.set(item.id, item);
    if (includeScopedEscalations) {
      for (const item of scopedItems ?? []) {
        if (item.status === "escalated") byId.set(item.id, item);
      }
    }
    return Array.from(byId.values()).sort((a, b) => {
      const aDate = new Date(a.updatedAt ?? a.createdAt).getTime();
      const bDate = new Date(b.updatedAt ?? b.createdAt).getTime();
      return bDate - aDate;
    });
  };

  const allItems = useMemo(
    () => mergeTickets(data?.items, showScopedEscalations ? scopedEscalationsData?.items : undefined),
    [data?.items, scopedEscalationsData?.items, showScopedEscalations, includeScopedEscalations, currentUserId],
  );
  const total = allItems.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const paged = allItems.slice((page - 1) * pageSize, page * pageSize);

  // Avatars des demandeurs — un seul appel batché pour tous les demandeurs uniques
  // visibles sur la page courante (au lieu d'un appel HTTP par demandeur).
  const requesterIds = [...new Set(paged.map((r) => r.requesterId).filter(Boolean))];
  const { data: requesterProfiles } = useQuery({
    queryKey: ["users", "batch", requesterIds],
    queryFn: () => fetchUsersByIds(requesterIds),
    enabled: requesterIds.length > 0,
    staleTime: 300_000,
  });
  const requesterAvatarById = new Map(
    (requesterProfiles ?? []).map((u) => [String(u.id), u]),
  );

  const assignedTickets = useMemo(
    () => mergeTickets(statsData?.items, scopedEscalationsStatsData?.items),
    [statsData?.items, scopedEscalationsStatsData?.items, includeScopedEscalations, currentUserId],
  );
  const resolvedTickets = assignedTickets.filter((r) => r.status === "resolved" || r.status === "closed");
  const kpiInProgress = assignedTickets.filter((r) => r.status === "in_progress").length;
  const kpiResolved = resolvedTickets.length;

  const listLoading = isLoading || (showScopedEscalations && scopedEscalationsLoading);
  const listError = isError || (showScopedEscalations && scopedEscalationsError);
  const listState: "loading" | "empty" | "ready" = listLoading
    ? "loading"
    : listError || paged.length === 0
    ? "empty"
    : "ready";

  const handleSearch = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => setSearch(e.target.value),
    [setSearch],
  );

  const openTicketDetail = useCallback((id: string) => {
    navigate({ to: "/app/my-tickets/tickets/$id", params: { id } });
  }, [navigate]);
  const openTicketDetailFromKeyboard = useCallback((event: React.KeyboardEvent, id: string) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openTicketDetail(id);
    }
  }, [openTicketDetail]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">

      {/* ── En-tête ────────────────────────────────────────────────────────── */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-end justify-between gap-3"
      >
        <div>
          <div className="flex items-center gap-2">
            <Ticket className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Mes tickets</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Tickets qui vous sont assignés ou escalades nécessitant votre traitement.
          </p>
        </div>
        <LayoutToggle layout={layout} onChange={setLayout} />
      </motion.header>

      {/* ── KPI row — parcours de traitement (en cours -> résolu -> transmis -> retransmis) ── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.04 }}
        className="grid grid-cols-2 gap-3 sm:grid-cols-4"
      >
        <GlassCard className="flex items-center gap-3 p-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10">
            <Ticket className="h-4 w-4 text-primary" />
          </span>
          <div>
            <div className="text-2xl font-bold leading-none">{kpiInProgress}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">En cours</div>
          </div>
        </GlassCard>

        <GlassCard className="flex items-center gap-3 p-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-green-500/10">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
          </span>
          <div>
            <div className="text-2xl font-bold leading-none">{kpiResolved}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Total résolus</div>
          </div>
        </GlassCard>

        <GlassCard className="flex items-center gap-3 p-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-info/10">
            <Send className="h-4 w-4 text-info" />
          </span>
          <div>
            <div className="text-2xl font-bold leading-none">{kpiTransmitted}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Transmis</div>
          </div>
        </GlassCard>

        <GlassCard className={cn("flex items-center gap-3 p-4", kpiRetransmitted > 0 && "border-amber-500/40 bg-amber-500/3")}>
          <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", kpiRetransmitted > 0 ? "bg-amber-500/15" : "bg-muted")}>
            <Repeat2 className={cn("h-4 w-4", kpiRetransmitted > 0 ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground")} />
          </span>
          <div>
            <div className={cn("text-2xl font-bold leading-none", kpiRetransmitted > 0 && "text-amber-600 dark:text-amber-400")}>{kpiRetransmitted}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Retransmis</div>
          </div>
        </GlassCard>
      </motion.div>

      {/* ── Filtres ────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.08 }}
      >
        <GlassCard className="p-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={handleSearch}
                placeholder="Rechercher par référence, titre, demandeur…"
                className="h-11 pl-9"
              />
            </div>
            <Select value={filterStatus} onValueChange={setFilterStatus}>
              <SelectTrigger className="h-11 w-full sm:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les statuts</SelectItem>
                {ACTIVE_STATUSES.map((s) => (
                  <SelectItem key={s} value={s}>{statusLabels[s]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="h-11 w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes priorités</SelectItem>
                {(["critical", "high", "medium", "low"] as Priority[]).map((p) => (
                  <SelectItem key={p} value={p}>{priorityLabels[p]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </GlassCard>
      </motion.div>

      {/* ── Liste / Grille ─────────────────────────────────────────────────── */}
      <AsyncSwap
        state={listState}
        empty={
          <GlassCard className="py-16 text-center">
            <motion.div
              className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 18 }}
            >
              {listError ? (
                <AlertTriangle className="h-6 w-6 text-muted-foreground" />
              ) : (
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              )}
            </motion.div>
            <h3 className="font-semibold">
              {listError ? "Erreur de chargement" : "Aucun ticket en cours"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {listError
                ? "Impossible de charger vos tickets."
                : "Vous n'avez aucun ticket actif à traiter pour le moment."}
            </p>
          </GlassCard>
        }
      >
        <>
          {layout === "list" ? (
            /* ── Vue liste ──────────────────────────────────────────────── */
            <GlassCard className="overflow-hidden p-0">
              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => {
                  return (
                    <motion.div
                      key={r.id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.3, delay: i * 0.03 }}
                      role="link"
                      tabIndex={0}
                      onClick={() => openTicketDetail(r.id)}
                      onKeyDown={(event) => openTicketDetailFromKeyboard(event, r.id)}
                      className={cn(
                        "flex cursor-pointer items-start gap-4 border-b px-5 py-4 last:border-0 transition-colors hover:bg-background/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                        r.priority === "critical"
                          ? "border-destructive/30 bg-destructive/3"
                          : r.status === "reopened"
                          ? "border-amber-500/30 bg-amber-500/3"
                          : "border-border/30",
                      )}
                    >
                      <div className="min-w-0 flex-1 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to="/app/my-tickets/tickets/$id"
                            params={{ id: r.id }}
                            className="font-mono text-[11px] text-primary hover:underline"
                          >
                            {r.ref}
                          </Link>
                          <PriorityBadge priority={r.priority} />
                          <StatusBadge status={r.status} />
                          {r.status === "reopened" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                              <RotateCcw className="h-2.5 w-2.5" /> Réouvert
                            </span>
                          )}
                          {r.priority === "critical" && (
                            <span className="inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-bold text-destructive">
                              CRITIQUE
                            </span>
                          )}
                        </div>
                        <Link
                          to="/app/my-tickets/tickets/$id"
                          params={{ id: r.id }}
                          className="block font-semibold leading-snug hover:text-primary"
                        >
                          {r.title}
                        </Link>
                        {r.description && (
                          <p className="line-clamp-1 text-xs text-muted-foreground">{r.description}</p>
                        )}
                        <div className="text-xs text-muted-foreground">
                          {r.requesterName} · {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                        </div>
                      </div>

                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <div className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
                          <Clock className="h-3.5 w-3.5" />
                          {formatElapsedHours(r.slaElapsed)}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </GlassCard>
          ) : (
            /* ── Vue grille ─────────────────────────────────────────────── */
            <motion.div layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => {
                  return (
                    <motion.div
                      key={r.id}
                      layout
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.94 }}
                      transition={{ duration: 0.3, delay: i * 0.04 }}
                      whileHover={{ y: -3 }}
                    >
                      <GlassCard className={cn(
                        "flex h-full min-h-[196px] cursor-pointer flex-col gap-3 p-4 transition-shadow hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                        r.priority === "critical" && "border-destructive/40 bg-destructive/3",
                        r.status === "reopened"   && "border-amber-500/40 bg-amber-500/3",
                      )}
                        role="link"
                        tabIndex={0}
                        onClick={() => openTicketDetail(r.id)}
                        onKeyDown={(event) => openTicketDetailFromKeyboard(event, r.id)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <StatusBadge status={r.status} />
                            {r.status === "reopened" && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                                <RotateCcw className="h-2.5 w-2.5" />
                              </span>
                            )}
                          </div>
                          <div className="flex flex-col items-end gap-1">
                            <Avatar className="h-6 w-6 border border-border/60">
                              <AvatarImage src={buildAvatarUrl(requesterAvatarById.get(r.requesterId)?.avatar)} alt={r.requesterName} />
                              <AvatarFallback className="bg-primary/10 text-[10px] font-bold text-primary">
                                {initialsFor(r.requesterName)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="flex items-center gap-1 text-xs font-medium shrink-0 text-muted-foreground">
                              <Clock className="h-3 w-3" />
                              {formatElapsedHours(r.slaElapsed)}
                            </div>
                          </div>
                        </div>

                        <Link to="/app/my-tickets/tickets/$id" params={{ id: r.id }} className="hover:text-primary">
                          <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
                        </Link>
                        <div className={cn("flex items-center gap-1.5 text-xs font-medium", priorityDotClass[r.priority])}>
                          <span className="h-2 w-2 shrink-0 rounded-full bg-current" />
                          {priorityLabels[r.priority]}
                        </div>

                        <div className="flex-1" />
                        <div className="space-y-1">
                          <div className="text-xs text-muted-foreground">{r.requesterName}</div>
                          <div className="text-xs text-muted-foreground">
                            {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                          </div>
                          <p className="font-mono text-[11px] text-muted-foreground/60">Réf. {r.ref}</p>
                        </div>

                      </GlassCard>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </motion.div>
          )}

          <PaginationBar
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
            onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
          />
        </>
      </AsyncSwap>
    </div>
  );
}
