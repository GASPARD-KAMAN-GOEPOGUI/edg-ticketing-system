import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useUser } from "@/lib/session";
import { useState, useEffect, useCallback } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fetchUser, buildAvatarUrl } from "@/lib/api/accounts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchRequests } from "@/lib/api/requests";
import { priorityLabels, statusLabels } from "@/lib/mock-data";
import type { RequestStatus, Priority } from "@/lib/mock-data";
import {
  Ticket, Clock, Search, Inbox,
  ShieldAlert, AlertTriangle, CheckCircle2, RotateCcw, TrendingUp,
} from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { useSessionState } from "@/lib/use-session-state";
import { cn, initialsFor } from "@/lib/utils";

export const Route = createFileRoute("/app/my-tickets")({
  beforeLoad: () => requireRole("agent-support", "chief-service", "admin"),
  head: () => ({ meta: [{ title: "Mes tickets — EDG Support" }] }),
  component: MyTicketsPage,
});

const ACTIVE_STATUSES: RequestStatus[] = [
  "new", "qualifying", "qualified", "assigned",
  "in_progress", "pending", "escalated", "reopened",
];

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

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => { setPage(1); }, [filterStatus, filterPriority, debouncedSearch]);

  const baseFilters = {
    assignee_id: sessionUser?.id,
    ...(filterPriority !== "all" && { priority: filterPriority }),
    ...(filterStatus !== "all" && { request_status: filterStatus }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };

  // Requête principale : paginée pour l'affichage
  const { data, isLoading, isError } = useQuery({
    queryKey: ["my-tickets", baseFilters, page, pageSize],
    queryFn: () => fetchRequests({ ...baseFilters, page, limit: pageSize }),
    staleTime: 30_000,
    enabled: !!sessionUser?.id,
  });

  // Requête stats : workload affectée à l'agent connecté.
  const { data: statsData } = useQuery({
    queryKey: ["my-tickets-stats", sessionUser?.id],
    queryFn: () => fetchRequests({ assignee_id: sessionUser!.id, limit: 1000 }),
    staleTime: 60_000,
    enabled: !!sessionUser?.id,
  });

  const allItems = data?.items ?? [];
  const paged = allItems;

  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  // Avatars des demandeurs — un seul fetch par demandeur unique visible sur la page courante.
  const requesterIds = [...new Set(paged.map((r) => r.requesterId).filter(Boolean))];
  const requesterAvatarQueries = useQueries({
    queries: requesterIds.map((id) => ({
      queryKey: ["user", id],
      queryFn: () => fetchUser(id),
      staleTime: 300_000,
    })),
  });
  const requesterAvatarById = new Map(
    requesterIds.map((id, i) => [id, requesterAvatarQueries[i]?.data]),
  );

  const assignedTickets = statsData?.items ?? [];
  const activeAssignedTickets = assignedTickets.filter((r) => ACTIVE_STATUSES.includes(r.status));
  const resolvedTickets = assignedTickets.filter((r) => r.status === "resolved" || r.status === "closed");
  const measuredSlaTickets = assignedTickets.filter((r) => r.slaHours > 0);
  const resolutionDurations = resolvedTickets
    .map((r) => {
      const end = r.resolvedAt ?? r.closedAt ?? r.updatedAt;
      const startMs = new Date(r.createdAt).getTime();
      const endMs = end ? new Date(end).getTime() : Number.NaN;
      return Number.isFinite(startMs) && Number.isFinite(endMs)
        ? Math.max(0, (endMs - startMs) / 3_600_000)
        : null;
    })
    .filter((value): value is number => value != null);
  const kpiInProgress = assignedTickets.filter((r) => r.status === "in_progress").length;
  const kpiBreached = activeAssignedTickets.filter((r) => r.slaHours > 0 && r.slaElapsed > r.slaHours).length;
  const kpiCritical = activeAssignedTickets.filter((r) => r.priority === "critical").length;
  const kpiResolved = resolvedTickets.length;
  const kpiSlaRate = measuredSlaTickets.length > 0
    ? Math.round((measuredSlaTickets.filter((r) => r.slaElapsed <= r.slaHours).length / measuredSlaTickets.length) * 100)
    : null;
  const kpiAvgResolution = resolutionDurations.length > 0
    ? Math.round((resolutionDurations.reduce((sum, value) => sum + value, 0) / resolutionDurations.length) * 10) / 10
    : null;

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
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
            Tickets qui vous sont personnellement assignés.
          </p>
        </div>
        <LayoutToggle layout={layout} onChange={setLayout} />
      </motion.header>

      {/* ── KPI row ────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.04 }}
        className="grid grid-cols-1 gap-3 sm:grid-cols-3"
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

        <GlassCard className={cn("flex items-center gap-3 p-4", kpiBreached > 0 && "border-destructive/40 bg-destructive/3")}>
          <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", kpiBreached > 0 ? "bg-destructive/15" : "bg-muted")}>
            <AlertTriangle className={cn("h-4 w-4", kpiBreached > 0 ? "text-destructive" : "text-muted-foreground")} />
          </span>
          <div>
            <div className={cn("text-2xl font-bold leading-none", kpiBreached > 0 && "text-destructive")}>{kpiBreached}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Délai dépassé</div>
          </div>
        </GlassCard>

        <GlassCard className={cn("flex items-center gap-3 p-4", kpiCritical > 0 && "border-orange-500/40 bg-orange-500/3")}>
          <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", kpiCritical > 0 ? "bg-orange-500/15" : "bg-muted")}>
            <ShieldAlert className={cn("h-4 w-4", kpiCritical > 0 ? "text-orange-500" : "text-muted-foreground")} />
          </span>
          <div>
            <div className={cn("text-2xl font-bold leading-none", kpiCritical > 0 && "text-orange-500")}>{kpiCritical}</div>
            <div className="mt-0.5 text-xs text-muted-foreground">Critiques</div>
          </div>
        </GlassCard>
      </motion.div>

      {/* ── KPI performance personnelle ─────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.06 }}
        className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      >
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
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10">
            <TrendingUp className="h-4 w-4 text-primary" />
          </span>
          <div>
            <div className="text-2xl font-bold leading-none">
              {kpiSlaRate != null ? `${kpiSlaRate}%` : "—"}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">Taux de délai respecté</div>
          </div>
        </GlassCard>

        <GlassCard className="flex items-center gap-3 p-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted">
            <Clock className="h-4 w-4 text-muted-foreground" />
          </span>
          <div>
            <div className="text-2xl font-bold leading-none">
              {kpiAvgResolution != null ? `${kpiAvgResolution}h` : "—"}
            </div>
            <div className="mt-0.5 text-xs text-muted-foreground">Délai moyen résolution</div>
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
              {isError ? (
                <AlertTriangle className="h-6 w-6 text-muted-foreground" />
              ) : (
                <CheckCircle2 className="h-6 w-6 text-emerald-500" />
              )}
            </motion.div>
            <h3 className="font-semibold">
              {isError ? "Erreur de chargement" : "Aucun ticket en cours"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError
                ? "Impossible de charger vos tickets."
                : "Vous n'avez aucun ticket actif assigné pour le moment."}
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
                  const slaOver = r.slaElapsed > r.slaHours;
                  const slaLeft = Math.max(0, r.slaHours - r.slaElapsed);
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
                          : slaOver
                          ? "border-orange-400/30"
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
                        <div className={cn("flex items-center gap-1 text-xs font-medium", slaOver ? "text-destructive" : "text-muted-foreground")}>
                          <Clock className="h-3.5 w-3.5" />
                          {slaOver ? "Délai dépassé" : `${slaLeft}h restantes`}
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
                  const slaOver = r.slaElapsed > r.slaHours;
                  const slaLeft = Math.max(0, r.slaHours - r.slaElapsed);
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
                            <div className={cn("flex items-center gap-1 text-xs font-medium shrink-0", slaOver ? "text-destructive" : "text-muted-foreground")}>
                              <Clock className="h-3 w-3" />
                              {slaOver ? "Délai !" : `${slaLeft}h`}
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
