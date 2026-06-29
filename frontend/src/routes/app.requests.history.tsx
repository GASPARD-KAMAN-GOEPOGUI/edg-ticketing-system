import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { fetchRequests } from "@/lib/api/requests";
import { fetchDirections } from "@/lib/api/directions-units";
import { exportXLSX, exportCSV } from "@/lib/export";
import { toast } from "sonner";
import { useUser } from "@/lib/session";
import { cn } from "@/lib/utils";
import {
  Search, History, CheckCircle2, XCircle, Lock,
  Calendar, ChevronRight, ArrowLeft,
  Download, X, ChevronDown, FileText,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  format, formatDistanceToNow,
  startOfDay, endOfDay, startOfWeek, endOfWeek,
  startOfMonth, endOfMonth, startOfYear, endOfYear,
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

type TerminalStatus = "resolved" | "closed" | "rejected";

const TABS: { key: TerminalStatus; label: string; icon: LucideIcon; activeClass: string }[] = [
  {
    key: "resolved",
    label: "Résolues",
    icon: CheckCircle2,
    activeClass: "border-emerald-500 text-emerald-600 dark:text-emerald-400 bg-emerald-500/8",
  },
  {
    key: "closed",
    label: "Clôturées",
    icon: Lock,
    activeClass: "border-border text-foreground bg-foreground/6",
  },
  {
    key: "rejected",
    label: "Rejetées",
    icon: XCircle,
    activeClass: "border-destructive text-destructive bg-destructive/8",
  },
];

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

function HistoryCard({ r }: { r: RequestItem }) {
  return (
    <GlassCard className="flex h-full flex-col gap-3 p-4 transition-shadow hover:shadow-xl">
      <div className="flex items-start justify-between gap-2">
        <StatusBadge status={r.status} />
        <span className="font-mono text-[11px] text-muted-foreground/60 shrink-0">{r.ref}</span>
      </div>
      <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
      <div className={`flex items-center gap-1.5 text-xs font-medium ${priorityDotClass[r.priority]}`}>
        <span className="h-2 w-2 shrink-0 rounded-full bg-current" />
        {priorityLabels[r.priority]}
      </div>
      {r.description && (
        <p className="line-clamp-2 text-xs text-muted-foreground">{r.description}</p>
      )}
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

  const [tab, setTab]       = useSessionState<TerminalStatus>("hist:tab", "resolved");
  const [q, setQ]           = useSessionState<string>("hist:q", "");
  const [layout, setLayout] = useSessionState<LayoutMode>("hist:layout", "list");
  const [dateFrom, setDateFrom] = useSessionState<string>("hist:dateFrom", "");
  const [dateTo, setDateTo]     = useSessionState<string>("hist:dateTo", "");
  const [page, setPage]     = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [debouncedQ, setDebouncedQ] = useState(q);
  const [exporting, setExporting] = useState(false);
  useScrollRestoration("hist:list");

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q), 400);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => { setPage(1); }, [tab, debouncedQ, dateFrom, dateTo]);

  const applyQuickDate = useCallback((preset: "today" | "week" | "month" | "year") => {
    const now = new Date();
    if (preset === "today")  { setDateFrom(isoDate(startOfDay(now)));  setDateTo(isoDate(endOfDay(now)));  }
    else if (preset === "week")  { setDateFrom(isoDate(startOfWeek(now, { locale: fr }))); setDateTo(isoDate(endOfWeek(now, { locale: fr }))); }
    else if (preset === "month") { setDateFrom(isoDate(startOfMonth(now))); setDateTo(isoDate(endOfMonth(now))); }
    else if (preset === "year")  { setDateFrom(isoDate(startOfYear(now))); setDateTo(isoDate(endOfYear(now))); }
    setPage(1);
  }, [setDateFrom, setDateTo]);

  const clearDates = useCallback(() => { setDateFrom(""); setDateTo(""); setPage(1); }, [setDateFrom, setDateTo]);

  const hasDateFilter = !!dateFrom || !!dateTo;

  const filters = {
    page,
    limit: pageSize,
    request_status: tab,
    ...(sessionUser?.id && { requester_id: sessionUser.id }),
    ...(debouncedQ && { search: debouncedQ }),
    ...(dateFrom && { date_from: dateFrom }),
    ...(dateTo && { date_to: dateTo }),
  };

  const exportFilters = { ...filters, page: 1, limit: 1000 };

  const { data, isLoading, isError } = useQuery({
    queryKey: ["requests-history", filters],
    queryFn: () => fetchRequests(filters),
    staleTime: 60_000,
  });

  const { data: directionsData } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const directionMap = useMemo(
    () => new Map((directionsData ?? []).map((d) => [String(d.id), d.name])),
    [directionsData],
  );

  const handleExport = useCallback(async (fmt: "xlsx" | "csv") => {
    setExporting(true);
    try {
      const all = await fetchRequests(exportFilters);
      if (all.items.length === 0) { toast.warning("Aucune demande à exporter."); return; }
      if (fmt === "xlsx") exportXLSX(all.items, directionMap, { dateFrom: dateFrom || undefined, dateTo: dateTo || undefined, sheetName: "Historique EDG" });
      else exportCSV(all.items, directionMap, { dateFrom: dateFrom || undefined, dateTo: dateTo || undefined });
      toast.success(`Export ${fmt.toUpperCase()} — ${all.items.length} demande${all.items.length > 1 ? "s" : ""}`);
    } catch {
      toast.error("Impossible de générer l'export.");
    } finally {
      setExporting(false);
    }
  }, [exportFilters, directionMap, dateFrom, dateTo]);

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

  const currentTab = TABS.find((t) => t.key === tab)!;

  const emptyMessage: Record<TerminalStatus, string> = {
    resolved: "Aucune demande résolue dans l'historique.",
    closed:   "Aucune demande clôturée dans l'historique.",
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
            <Link to="/app/requests" className="flex items-center gap-1 hover:text-foreground transition-colors">
              <ArrowLeft className="h-3.5 w-3.5" />
              Mes demandes
            </Link>
          </div>
          <div className="flex items-center gap-2">
            <History className="h-6 w-6 text-muted-foreground" />
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Historique</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} demande{total > 1 ? "s" : ""} {statusLabels[tab].toLowerCase()}{total > 1 ? "s" : ""}.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" className="rounded-full" disabled={exporting}>
                <Download className="mr-1.5 h-4 w-4" />
                {exporting ? "Export…" : "Exporter"}
                <ChevronDown className="ml-1 h-3.5 w-3.5 opacity-60" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onClick={() => handleExport("xlsx")}>
                <FileText className="mr-2 h-4 w-4 text-emerald-600" />
                Excel (.xlsx)
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => handleExport("csv")}>
                <FileText className="mr-2 h-4 w-4 text-muted-foreground" />
                CSV (.csv)
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </motion.header>

      {/* Onglets de statut */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.04 }}
        className="flex flex-wrap items-center gap-2"
      >
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all",
                active
                  ? t.activeClass
                  : "border-border/50 text-muted-foreground hover:border-border hover:text-foreground",
              )}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          );
        })}
      </motion.div>

      {/* Barre de recherche + filtres de date */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.08 }}
      >
        <GlassCard className="space-y-3 p-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={handleQChange}
              placeholder="Rechercher par référence, titre…"
              className="h-11 pl-9"
            />
          </div>

          {/* Filtres de date */}
          <div className="flex flex-wrap items-center gap-2 border-t border-border/30 pt-3">
            <Calendar className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground">Période :</span>
            {(["today", "week", "month", "year"] as const).map((p) => (
              <button
                key={p}
                onClick={() => applyQuickDate(p)}
                className="rounded-full border border-border/50 px-3 py-1 text-xs font-medium text-muted-foreground transition-colors hover:border-primary/50 hover:text-primary"
              >
                {p === "today" ? "Aujourd'hui" : p === "week" ? "Cette semaine" : p === "month" ? "Ce mois" : "Cette année"}
              </button>
            ))}
            <span className="text-xs text-muted-foreground">ou</span>
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
                className="h-8 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
              <span className="text-xs text-muted-foreground">→</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
                className="h-8 rounded-lg border border-border/50 bg-background px-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary/40"
              />
            </div>
            {hasDateFilter && (
              <button
                onClick={clearDates}
                className="flex items-center gap-1 rounded-full border border-destructive/30 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/10 transition-colors"
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
              {isError ? "Impossible de charger l'historique." : emptyMessage[tab]}
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
                    <HistoryCard r={r} />
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
                          onClick={() => navigate({ to: "/app/requests/$id", params: { id: r.id } })}
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
                              ? formatDistanceToNow(new Date(r.updatedAt), { addSuffix: true, locale: fr })
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
                      <HistoryCard r={r} />
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
            onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
          />
        </>
      </AsyncSwap>
    </div>
  );
}
