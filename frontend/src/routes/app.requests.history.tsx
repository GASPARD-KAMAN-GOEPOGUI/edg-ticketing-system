import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { buildAvatarUrl } from "@/lib/api/accounts";
import { initialsFor } from "@/lib/utils";
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
import { useUser } from "@/lib/session";
import {
  Search,
  History,
  CheckCircle2,
  XCircle,
  Lock,
  Calendar,
  ChevronRight,
  ArrowLeft,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  format,
  formatDistanceToNow,
  startOfDay,
  endOfDay,
  startOfWeek,
  endOfWeek,
  startOfMonth,
  endOfMonth,
  startOfYear,
  endOfYear,
} from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { useSessionState, useScrollRestoration } from "@/lib/use-session-state";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { statusLabels, priorityLabels } from "@/lib/mock-data";
import type { Priority, RequestItem } from "@/lib/mock-data";

const isoDate = (d: Date) => format(d, "yyyy-MM-dd");

export const Route = createFileRoute("/app/requests/history")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Historique — EDG Support" }] }),
  component: RequestHistory,
});

type TerminalStatus = "closed" | "cancelled" | "rejected";

const TABS: { key: TerminalStatus; label: string; icon: LucideIcon }[] = [
  {
    key: "closed",
    label: "Clôturées",
    icon: Lock,
  },
  {
    key: "cancelled",
    label: "Annulées",
    icon: XCircle,
  },
  {
    key: "rejected",
    label: "Rejetées",
    icon: XCircle,
  },
];

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

function HistoryCard({ r, requesterAvatar }: { r: RequestItem; requesterAvatar?: string }) {
  return (
    <GlassCard className="flex h-full min-h-[196px] flex-col gap-3 p-4 transition-shadow hover:shadow-xl">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-1.5">
          <StatusBadge status={r.status} />
          <Avatar className="h-6 w-6 border border-border/60">
            <AvatarImage src={buildAvatarUrl(requesterAvatar)} alt={r.requesterName} />
            <AvatarFallback className="bg-primary/10 text-[10px] font-bold text-primary">
              {initialsFor(r.requesterName)}
            </AvatarFallback>
          </Avatar>
        </div>
        <span className="font-mono text-[11px] text-muted-foreground/60 shrink-0">{r.ref}</span>
      </div>
      <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
      <div
        className={`flex items-center gap-1.5 text-xs font-medium ${priorityDotClass[r.priority]}`}
      >
        <span className="h-2 w-2 shrink-0 rounded-full bg-current" />
        {priorityLabels[r.priority]}
      </div>
      <div className="flex-1" />
      <div className="border-t border-border/30 pt-2 space-y-1">
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Calendar className="h-3 w-3 shrink-0" />
          Créée le {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
        </div>
        {r.updatedAt && r.updatedAt !== r.createdAt && (
          <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <CheckCircle2 className="h-3 w-3 shrink-0 opacity-60" />
            Clôturée {formatDistanceToNow(new Date(r.updatedAt), { addSuffix: true, locale: fr })}
          </div>
        )}
      </div>
      <div className="flex items-center justify-end text-xs text-primary font-medium gap-1">
        Voir le détail <ChevronRight className="h-3.5 w-3.5" />
      </div>
    </GlassCard>
  );
}

function RequestHistory() {
  const sessionUser = useUser();
  const navigate = useNavigate();

  const [tab, setTab] = useSessionState<TerminalStatus>("hist:tab", "closed");
  const [q, setQ] = useSessionState<string>("hist:q", "");
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [dateFrom, setDateFrom] = useSessionState<string>("hist:dateFrom", "");
  const [dateTo, setDateTo] = useSessionState<string>("hist:dateTo", "");
  const [periodPreset, setPeriodPreset] = useSessionState<string>("hist:period", "all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [debouncedQ, setDebouncedQ] = useState(q);
  useScrollRestoration("hist:list");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 400);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    setPage(1);
  }, [tab, debouncedQ, dateFrom, dateTo]);

  useEffect(() => {
    if (!TABS.some((t) => t.key === tab)) setTab("closed");
  }, [tab, setTab]);

  const applyQuickDate = useCallback(
    (preset: "today" | "week" | "month" | "year") => {
      const now = new Date();
      if (preset === "today") {
        setDateFrom(isoDate(startOfDay(now)));
        setDateTo(isoDate(endOfDay(now)));
      } else if (preset === "week") {
        setDateFrom(isoDate(startOfWeek(now, { locale: fr })));
        setDateTo(isoDate(endOfWeek(now, { locale: fr })));
      } else if (preset === "month") {
        setDateFrom(isoDate(startOfMonth(now)));
        setDateTo(isoDate(endOfMonth(now)));
      } else if (preset === "year") {
        setDateFrom(isoDate(startOfYear(now)));
        setDateTo(isoDate(endOfYear(now)));
      }
      setPeriodPreset(preset);
      setPage(1);
    },
    [setDateFrom, setDateTo, setPeriodPreset],
  );

  const clearDates = useCallback(() => {
    setDateFrom("");
    setDateTo("");
    setPeriodPreset("all");
    setPage(1);
  }, [setDateFrom, setDateTo, setPeriodPreset]);

  const handlePeriodChange = useCallback(
    (val: string) => {
      if (val === "all") {
        clearDates();
      } else if (val === "custom") {
        setPeriodPreset("custom");
      } else {
        applyQuickDate(val as "today" | "week" | "month" | "year");
      }
    },
    [clearDates, applyQuickDate, setPeriodPreset],
  );

  const hasDateFilter = !!dateFrom || !!dateTo;
  const safeTab: TerminalStatus = TABS.some((t) => t.key === tab) ? tab : "closed";

  const filters = useMemo(
    () => ({
      page,
      limit: pageSize,
      request_status: safeTab,
      ...(sessionUser?.id && { requester_id: sessionUser.id }),
      ...(debouncedQ && { search: debouncedQ }),
      ...(dateFrom && { date_from: dateFrom }),
      ...(dateTo && { date_to: dateTo }),
    }),
    [dateFrom, dateTo, debouncedQ, page, pageSize, sessionUser?.id, safeTab],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["requests-history", filters],
    queryFn: () => fetchRequests(filters),
    staleTime: 60_000,
  });

  const paged = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
      ? "empty"
      : "ready";

  const handleQChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => setQ(e.target.value),
    [setQ],
  );

  const currentTab = TABS.find((t) => t.key === safeTab)!;

  const emptyMessage: Record<TerminalStatus, string> = {
    closed: "Aucune demande clôturée dans l'historique.",
    cancelled: "Aucune demande annulée dans l'historique.",
    rejected: "Aucune demande rejetée dans l'historique.",
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* En-tête */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-end justify-between gap-3"
      >
        <div>
          <div className="mb-1 flex items-center gap-2 text-sm text-muted-foreground">
            <Link
              to="/app/requests"
              className="flex items-center gap-1 hover:text-foreground transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              Mes demandes
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <History className="h-6 w-6 text-muted-foreground" />
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Historique</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} demande{total > 1 ? "s" : ""} {statusLabels[safeTab].toLowerCase()}
            {total > 1 ? "s" : ""}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
        </div>
      </motion.header>

      {/* Barre de recherche + filtres */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
      >
        <GlassCard className="p-3">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative min-w-0 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={handleQChange}
                placeholder="Rechercher par numéro, titre…"
                className="h-9 pl-9"
              />
            </div>

            <Select value={safeTab} onValueChange={(value) => setTab(value as TerminalStatus)}>
              <SelectTrigger className="h-9 w-40 shrink-0">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TABS.map((t) => (
                  <SelectItem key={t.key} value={t.key}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

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

            {periodPreset === "custom" && (
              <div className="flex items-center gap-1.5 shrink-0">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
                <span className="text-xs text-muted-foreground">→</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => {
                    setDateTo(e.target.value);
                    setPage(1);
                  }}
                  className="h-9 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
                />
              </div>
            )}

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

      {/* Liste */}
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
              <currentTab.icon className="h-6 w-6 text-muted-foreground" />
            </motion.div>
            <h3 className="font-semibold">Aucun historique</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError ? "Impossible de charger l'historique." : emptyMessage[safeTab]}
            </p>
          </GlassCard>
        }
      >
        <>
          {/* Mobile — cartes */}
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
                  <Link to="/app/requests/$id" params={{ id: r.id }} className="block">
                    <HistoryCard r={r} requesterAvatar={sessionUser?.avatar} />
                  </Link>
                </motion.div>
              ))}
            </AnimatePresence>
          </motion.div>

          {/* Desktop — table (list) ou grille (grid) */}
          {layout === "list" ? (
            <GlassCard className="hidden overflow-hidden p-0 md:block">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 text-left font-semibold">Référence</th>
                      <th className="px-5 py-3 text-left font-semibold">Sujet</th>
                      <th className="px-5 py-3 text-left font-semibold">Priorité</th>
                      <th className="px-5 py-3 text-left font-semibold">Statut</th>
                      <th className="px-5 py-3 text-left font-semibold">Créée le</th>
                      <th className="px-5 py-3 text-left font-semibold">Clôturée</th>
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
                            navigate({ to: "/app/requests/$id", params: { id: r.id } })
                          }
                        >
                          <td className="px-5 py-4">
                            <span className="font-mono text-xs text-primary">{r.ref}</span>
                          </td>
                          <td className="px-5 py-4 font-medium max-w-[280px]">
                            <span className="line-clamp-1">{r.title}</span>
                          </td>
                          <td className="px-5 py-4">
                            <PriorityBadge priority={r.priority} />
                          </td>
                          <td className="px-5 py-4">
                            <StatusBadge status={r.status} />
                          </td>
                          <td className="px-5 py-4 text-xs text-muted-foreground">
                            {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                          </td>
                          <td className="px-5 py-4 text-xs text-muted-foreground">
                            {r.updatedAt && r.updatedAt !== r.createdAt
                              ? formatDistanceToNow(new Date(r.updatedAt), {
                                  addSuffix: true,
                                  locale: fr,
                                })
                              : "—"}
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
                    <Link to="/app/requests/$id" params={{ id: r.id }} className="block h-full">
                      <HistoryCard r={r} requesterAvatar={sessionUser?.avatar} />
                    </Link>
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
            onPageSizeChange={(s) => {
              setPageSize(s);
              setPage(1);
            }}
          />
        </>
      </AsyncSwap>
    </div>
  );
}
