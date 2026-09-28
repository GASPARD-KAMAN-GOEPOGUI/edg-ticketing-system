import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useState, useEffect } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fetchUser, buildAvatarUrl } from "@/lib/api/accounts";
import { fetchTransmittedByMe } from "@/lib/api/requests";
import { priorityLabels } from "@/lib/mock-data";
import type { Priority } from "@/lib/mock-data";
import { Send, Clock, AlertTriangle, RotateCcw, Search, X } from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { cn, initialsFor, formatElapsedHours } from "@/lib/utils";

export const Route = createFileRoute("/app/transmitted")({
  beforeLoad: () => requireRole("chief-service", "technicien", "chef-division-support", "admin"),
  head: () => ({ meta: [{ title: "Tickets transmis — EDG Support" }] }),
  component: TransmittedTicketsPage,
});

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

function TransmittedTicketsPage() {
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const searchTerm = search.trim();

  useEffect(() => {
    setPage(1);
  }, [searchTerm]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["transmitted-by-me", page, pageSize, searchTerm],
    queryFn: () => fetchTransmittedByMe({
      page,
      limit: pageSize,
      search: searchTerm || undefined,
    }),
    staleTime: 30_000,
  });

  const paged = data?.items ?? [];
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

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
    ? "empty"
    : "ready";

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
            <Send className="h-6 w-6 text-primary" />
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Tickets transmis</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Tickets dont vous avez personnellement transmis le traitement — quel que soit le porteur actuel.
          </p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:min-w-[360px] sm:flex-row sm:items-center sm:justify-end">
          <div className="relative min-w-0 flex-1 sm:w-72">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              type="search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Rechercher un ticket transmis"
              className="h-10 w-full rounded-full border border-border/50 bg-background/70 pl-9 pr-9 text-sm shadow-sm outline-none transition focus:border-primary/50 focus:ring-2 focus:ring-primary/20"
            />
            {search && (
              <button
                type="button"
                aria-label="Effacer la recherche"
                onClick={() => setSearch("")}
                className="absolute right-2 top-1/2 grid h-6 w-6 -translate-y-1/2 place-items-center rounded-full text-muted-foreground transition hover:bg-muted hover:text-foreground"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>
          <LayoutToggle layout={layout} onChange={setLayout} />
        </div>
      </motion.header>

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
                <Send className="h-6 w-6 text-muted-foreground" />
              )}
            </motion.div>
            <h3 className="font-semibold">
              {isError
                ? "Erreur de chargement"
                : searchTerm
                ? "Aucun ticket transmis trouvé"
                : "Aucun ticket transmis"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError
                ? "Impossible de charger vos tickets transmis."
                : searchTerm
                ? "Essayez une autre référence, un titre ou un requérant."
                : "Vous n'avez encore transmis le traitement d'aucun ticket."}
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
                      className={cn(
                        "flex items-start gap-4 border-b px-5 py-4 last:border-0",
                        r.priority === "critical"
                          ? "border-destructive/30 bg-destructive/3"
                          : r.status === "reopened"
                          ? "border-amber-500/30 bg-amber-500/3"
                          : "border-border/30",
                      )}
                    >
                      <div className="min-w-0 flex-1 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-[11px] text-primary">{r.ref}</span>
                          <PriorityBadge priority={r.priority} />
                          <StatusBadge status={r.status} />
                          {r.status === "reopened" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                              <RotateCcw className="h-2.5 w-2.5" /> Réouvert
                            </span>
                          )}
                        </div>
                        <p className="font-semibold leading-snug">{r.title}</p>
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
                    >
                      <GlassCard className={cn(
                        "flex h-full min-h-[196px] flex-col gap-3 p-4",
                        r.priority === "critical" && "border-destructive/40 bg-destructive/3",
                        r.status === "reopened"   && "border-amber-500/40 bg-amber-500/3",
                      )}>
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

                        <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
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
