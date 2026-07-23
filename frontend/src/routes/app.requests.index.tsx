import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { useEffect, useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { statusLabels, priorityLabels } from "@/lib/mock-data";
import type { RequestStatus, Priority, RequestItem } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { fetchRequests } from "@/lib/api/requests";
import {
  Plus, Search, Inbox, MapPin, Calendar, CheckCircle2,
  Wrench, Zap, FileText, Shield, Plug, CreditCard,
  HardHat, Briefcase, BarChart2, MessageCircle,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import {
  format, formatDistanceToNow,
  startOfDay, endOfDay, startOfWeek, endOfWeek,
  startOfMonth, endOfMonth, startOfYear, endOfYear,
} from "date-fns";
import { fr } from "date-fns/locale";
import {
  EscalationProgressBar,
  buildRequesterStepsFromStatus,
} from "@/components/escalation-progress-bar";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { useSessionState, useScrollRestoration } from "@/lib/use-session-state";
import { useRole, useUser } from "@/lib/session";
import { RejectedTicketModal } from "@/components/rejected-ticket-modal";

const isoDate = (d: Date) => format(d, "yyyy-MM-dd");

export const Route = createFileRoute("/app/requests/")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Mes demandes — EDG Support" }] }),
  component: RequestsList,
});

function getCategoryIcon(category: string): LucideIcon {
  const lc = category.toLowerCase();
  if (lc.includes("panne") || lc.includes("réseau") || lc.includes("réseau")) return Zap;
  if (lc.includes("maintenance") || lc.includes("dépannage") || lc.includes("depannage")) return Wrench;
  if (lc.includes("factur") || lc.includes("paie") || lc.includes("rembours") || lc.includes("budget")) return CreditCard;
  if (lc.includes("document") || lc.includes("admin") || lc.includes("carrière") || lc.includes("congé")) return FileText;
  if (lc.includes("accès") || lc.includes("applicatif") || lc.includes("sécurité")) return Shield;
  if (lc.includes("raccordement") || lc.includes("branchement")) return Plug;
  if (lc.includes("travaux")) return HardHat;
  if (lc.includes("communication")) return MessageCircle;
  if (lc.includes("carrière")) return Briefcase;
  if (lc.includes("stat") || lc.includes("rapport")) return BarChart2;
  return FileText;
}

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

const PERSONAL_ACTIVE_STATUSES: RequestStatus[] = [
  "new",
  "qualifying",
  "qualified",
  "assigned",
  "in_progress",
  "pending",
  "escalated",
  "resolved",
  "reopened",
];
const PERSONAL_TERMINAL_STATUSES: RequestStatus[] = ["closed", "cancelled", "rejected"];
const PERSONAL_TERMINAL_STATUS_SET = new Set<RequestStatus>(PERSONAL_TERMINAL_STATUSES);
const REQUEST_STATUS_OPTIONS = PERSONAL_ACTIVE_STATUSES;

function RequestCard({ r }: { r: RequestItem }) {
  const CategoryIcon = getCategoryIcon(r.category);
  const steps = buildRequesterStepsFromStatus(r.status);
  return (
    <GlassCard className="flex h-full flex-col gap-3 p-4 transition-shadow hover:shadow-xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
          <CategoryIcon className="h-4 w-4" />
        </div>
        <StatusBadge status={r.status} />
      </div>

      {/* Title */}
      <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>

      {/* Priority */}
      <div className={`flex items-center gap-1.5 text-xs font-medium ${priorityDotClass[r.priority]}`}>
        <span className="h-2 w-2 shrink-0 rounded-full bg-current" />
        {priorityLabels[r.priority]}
      </div>

      {/* Description */}
      {r.description && (
        <p className="line-clamp-2 text-xs text-muted-foreground">{r.description}</p>
      )}

      {/* Spacer */}
      <div className="flex-1" />

      {/* Meta */}
      <div className="space-y-1">
        {r.locationLabel && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{r.locationLabel}</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3 shrink-0" />
          {format(new Date(r.createdAt), "d MMMM yyyy", { locale: fr })}
        </div>
        {r.updatedAt && r.updatedAt !== r.createdAt && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-3 w-3 shrink-0 inline-flex items-center justify-center opacity-60">↻</span>
            Mis à jour {formatDistanceToNow(new Date(r.updatedAt), { addSuffix: true, locale: fr })}
          </div>
        )}
        <p className="font-mono text-[11px] text-muted-foreground/60">Réf. {r.ref}</p>
      </div>

      {/* Progress bar */}
      <div className="border-t border-border/30 pt-2">
        <EscalationProgressBar
          compact
          steps={steps}
          className="!border-0 !shadow-none !bg-transparent !backdrop-blur-none !rounded-none !px-0 !py-0"
        />
      </div>
    </GlassCard>
  );
}

function RequestsList() {
  const [role] = useRole();
  const sessionUser = useUser();
  const isUser = role === "user";
  const navigate = useNavigate();
  const [rejectedModalId, setRejectedModalId] = useState<string | null>(null);

  const [q, setQ] = useSessionState<string>("req:q", "");
  const [status, setStatus] = useSessionState<string>("req:status", "all");
  const [origin, setOrigin] = useSessionState<string>("req:origin", "all");
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [debouncedQ, setDebouncedQ] = useState(q);
  const [dateFrom, setDateFrom] = useSessionState<string>("req:dateFrom", "");
  const [dateTo, setDateTo] = useSessionState<string>("req:dateTo", "");
  const [periodPreset, setPeriodPreset] = useSessionState<string>("req:period", "all");
  useScrollRestoration("req:list");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 400);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    if (PERSONAL_TERMINAL_STATUS_SET.has(status as RequestStatus)) setStatus("all");
  }, [status, setStatus]);

  useEffect(() => { setPage(1); }, [status, origin, debouncedQ, dateFrom, dateTo]);

  const applyQuickDate = useCallback((preset: "today" | "week" | "month" | "year") => {
    const now = new Date();
    if (preset === "today") { setDateFrom(isoDate(startOfDay(now))); setDateTo(isoDate(endOfDay(now))); }
    else if (preset === "week") { setDateFrom(isoDate(startOfWeek(now, { locale: fr }))); setDateTo(isoDate(endOfWeek(now, { locale: fr }))); }
    else if (preset === "month") { setDateFrom(isoDate(startOfMonth(now))); setDateTo(isoDate(endOfMonth(now))); }
    else if (preset === "year") { setDateFrom(isoDate(startOfYear(now))); setDateTo(isoDate(endOfYear(now))); }
    setPeriodPreset(preset);
    setPage(1);
  }, [setDateFrom, setDateTo, setPeriodPreset]);

  const clearDates = useCallback(() => {
    setDateFrom(""); setDateTo(""); setPeriodPreset("all"); setPage(1);
  }, [setDateFrom, setDateTo, setPeriodPreset]);

  const handlePeriodChange = useCallback((val: string) => {
    if (val === "all") { clearDates(); }
    else if (val === "custom") { setPeriodPreset("custom"); }
    else { applyQuickDate(val as "today" | "week" | "month" | "year"); }
  }, [clearDates, applyQuickDate, setPeriodPreset]);

  const hasDateFilter = !!dateFrom || !!dateTo;
  const visibleStatus = PERSONAL_TERMINAL_STATUS_SET.has(status as RequestStatus) ? "all" : status;

  const filters = {
    page,
    limit: pageSize,
    exclude_status: PERSONAL_TERMINAL_STATUSES.join(","),
    ...(visibleStatus !== "all" && { request_status: visibleStatus }),
    ...(sessionUser?.id && { requester_id: sessionUser.id }),
    ...(!isUser && origin === "internal" && { is_external: false }),
    ...(!isUser && origin === "external" && { is_external: true }),
    ...(debouncedQ && { search: debouncedQ }),
    ...(dateFrom && { date_from: dateFrom }),
    ...(dateTo && { date_to: dateTo }),
  };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["requests", filters],
    queryFn: () => fetchRequests(filters),
    staleTime: 30_000,
  });

  const { data: directionsData } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: unitsData = [] } = useQuery({
    queryKey: ["units-all"],
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });

  const directionMap = useMemo(
    () => new Map((directionsData ?? []).map((d) => [String(d.id), d.name])),
    [directionsData],
  );

  // serviceId (unit) → direction_id, pour les requêtes où direction_id est null
  const unitToDirectionId = useMemo(
    () => new Map(unitsData.map((u) => [String(u.id), u.direction_id ? String(u.direction_id) : ""])),
    [unitsData],
  );

  const resolveDirection = useCallback(
    (r: { directionId?: string; serviceId?: string }): string => {
      if (r.directionId) {
        const name = directionMap.get(String(r.directionId));
        if (name) return name;
      }
      if (r.serviceId) {
        const dirId = unitToDirectionId.get(String(r.serviceId));
        if (dirId) return directionMap.get(dirId) ?? "—";
      }
      return "—";
    },
    [directionMap, unitToDirectionId],
  );

  const paged = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
    ? "empty"
    : "ready";

  const handleQChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setQ(e.target.value);
  }, [setQ]);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-end justify-between gap-3"
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Mes demandes
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} demande{total > 1 ? "s" : ""} trouvée{total > 1 ? "s" : ""}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
          <Button asChild className="rounded-full gradient-primary shadow-lg shadow-primary/30">
            <Link to="/app/new">
              <Plus className="mr-1 h-4 w-4" /> Nouvelle demande
            </Link>
          </Button>
        </div>
      </motion.header>

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
      >
        <GlassCard className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            {/* Recherche */}
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={handleQChange}
                placeholder="Rechercher par numéro, titre…"
                className="h-9 pl-9"
              />
            </div>

            {/* Statut */}
            <Select value={visibleStatus} onValueChange={setStatus}>
              <SelectTrigger className="h-9 w-40 shrink-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les statuts</SelectItem>
                {REQUEST_STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s}>{statusLabels[s]}</SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Origine (non-user) */}
            {!isUser && (
              <Select value={origin} onValueChange={setOrigin}>
                <SelectTrigger className="h-9 w-36 shrink-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes origines</SelectItem>
                  <SelectItem value="internal">Interne</SelectItem>
                  <SelectItem value="external">Externe</SelectItem>
                </SelectContent>
              </Select>
            )}

            {/* Période */}
            <div className="flex items-center gap-1.5 shrink-0">
              <Calendar className="h-3.5 w-3.5 text-muted-foreground" />
              <Select value={periodPreset} onValueChange={handlePeriodChange}>
                <SelectTrigger className="h-9 w-40">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes les dates</SelectItem>
                  <SelectItem value="today">Aujourd'hui</SelectItem>
                  <SelectItem value="week">Cette semaine</SelectItem>
                  <SelectItem value="month">Ce mois</SelectItem>
                  <SelectItem value="year">Cette année</SelectItem>
                  <SelectItem value="custom">Personnalisé…</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {/* Dates custom */}
            {periodPreset === "custom" && (
              <div className="flex items-center gap-1.5 shrink-0">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                  className="h-9 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
                <span className="text-xs text-muted-foreground">→</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                  className="h-9 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
            )}

            {/* Effacer */}
            {hasDateFilter && (
              <button
                onClick={clearDates}
                className="flex shrink-0 items-center gap-1 rounded-full border border-destructive/30 px-2.5 py-1.5 text-xs text-destructive hover:bg-destructive/10 transition-colors"
              >
                <X className="h-3 w-3" /> Effacer
              </button>
            )}
          </div>
        </GlassCard>
      </motion.div>

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
              <Inbox className="h-6 w-6 text-muted-foreground" />
            </motion.div>
            <h3 className="font-semibold">Aucune demande</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError
                ? "Impossible de charger les demandes."
                : "Vous n'avez pas encore soumis de demande. Cliquez sur « Nouvelle demande » pour commencer."}
            </p>
            {!isError && (
              <Button asChild className="mt-4 rounded-full gradient-primary shadow-lg shadow-primary/30">
                <Link to="/app/new"><Plus className="mr-1 h-4 w-4" /> Nouvelle demande</Link>
              </Button>
            )}
          </GlassCard>
        }
      >
        <>
          {/* Mobile cards */}
          <motion.div layout className="space-y-3 md:hidden">
            <AnimatePresence mode="popLayout" initial={false}>
              {paged.map((r, i) => (
                <motion.div
                  key={r.id}
                  layout
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10, scale: 0.97 }}
                  transition={{ duration: 0.35, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
                  whileHover={{ y: -3 }}
                >
                  {r.status === "rejected" ? (
                    <button
                      type="button"
                      className="block w-full text-left"
                      onClick={() => setRejectedModalId(r.id)}
                    >
                      <RequestCard r={r} />
                    </button>
                  ) : (
                    <Link to="/app/requests/$id" params={{ id: r.id }} className="block">
                      <RequestCard r={r} />
                    </Link>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>

          {/* Desktop — table (layout=list) ou grille (layout=grid) */}
          {layout === "list" ? (
            <GlassCard className="hidden overflow-hidden p-0 md:block">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 text-left font-semibold">Référence</th>
                      <th className="px-5 py-3 text-left font-semibold">Sujet</th>
                      <th className="px-5 py-3 text-left font-semibold">Direction</th>
                      <th className="px-5 py-3 text-left font-semibold">Origine</th>
                      <th className="px-5 py-3 text-left font-semibold">Priorité</th>
                      <th className="px-5 py-3 text-left font-semibold">Statut</th>
                      <th className="px-5 py-3 text-left font-semibold">Dates</th>
                    </tr>
                  </thead>
                  <tbody>
                    <AnimatePresence mode="popLayout" initial={false}>
                      {paged.map((r, i) => (
                        <motion.tr
                          key={r.id}
                          layout
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -6 }}
                          transition={{ duration: 0.3, delay: i * 0.03 }}
                          className="border-t border-border/40 transition-colors hover:bg-background/50 cursor-pointer"
                          onClick={() =>
                            r.status === "rejected"
                              ? setRejectedModalId(r.id)
                              : navigate({ to: "/app/requests/$id", params: { id: r.id } })
                          }
                        >
                          <td className="px-5 py-4">
                            <span className="font-mono text-xs text-primary">
                              <motion.span layoutId={`req-ref-${r.id}`} className="inline-block">
                                {r.ref}
                              </motion.span>
                            </span>
                          </td>
                          <td className="px-5 py-4 font-medium">{r.title}</td>
                          <td className="px-5 py-4 text-muted-foreground">
                            {resolveDirection(r)}
                          </td>
                          <td className="px-5 py-4">
                            {r.isExternal ? (
                              <span className="inline-flex rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground dark:text-accent">
                                Externe
                              </span>
                            ) : (
                              <span className="inline-flex rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                                Interne
                              </span>
                            )}
                          </td>
                          <td className="px-5 py-4">
                            <PriorityBadge priority={r.priority} />
                          </td>
                          <td className="px-5 py-4">
                            <StatusBadge status={r.status} />
                          </td>
                          <td className="px-5 py-4 text-xs text-muted-foreground">
                            <div className="flex items-center gap-1">
                              <Calendar className="h-3 w-3 shrink-0" />
                              {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                            </div>
                            {["resolved", "closed", "rejected", "cancelled"].includes(r.status) && r.updatedAt && (
                              <div className="mt-0.5 flex items-center gap-1 text-success">
                                <CheckCircle2 className="h-3 w-3 shrink-0" />
                                {format(new Date(r.updatedAt), "d MMM yyyy", { locale: fr })}
                              </div>
                            )}
                          </td>
                        </motion.tr>
                      ))}
                    </AnimatePresence>
                  </tbody>
                </table>
              </div>
            </GlassCard>
          ) : (
            <motion.div layout className="hidden gap-4 md:grid md:grid-cols-2 xl:grid-cols-3">
              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => (
                  <motion.div
                    key={r.id}
                    layout
                    initial={{ opacity: 0, scale: 0.96 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.94 }}
                    transition={{ duration: 0.3, delay: i * 0.04 }}
                    whileHover={{ y: -3 }}
                  >
                    {r.status === "rejected" ? (
                      <button
                        type="button"
                        className="block h-full w-full text-left"
                        onClick={() => setRejectedModalId(r.id)}
                      >
                        <RequestCard r={r} />
                      </button>
                    ) : (
                      <Link to="/app/requests/$id" params={{ id: r.id }} className="block h-full">
                        <RequestCard r={r} />
                      </Link>
                    )}
                  </motion.div>
                ))}
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

      <RejectedTicketModal
        id={rejectedModalId}
        open={!!rejectedModalId}
        onClose={() => setRejectedModalId(null)}
      />
    </div>
  );
}
