import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { fetchResolvedByMe } from "@/lib/api/requests";
import { priorityLabels } from "@/lib/mock-data";
import type { Priority } from "@/lib/mock-data";
import { CheckCircle2, AlertTriangle, Search, X, FileCheck2 } from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import { cn } from "@/lib/utils";

// Ouvert aux rôles traitants ET à l'admin, qui traite aussi des tickets — même
// périmètre que la garde serveur `_treating_roles_guard`.
const PAGE_ACCESS_ROLES = ["chief-service", "technicien", "chef-division-support", "admin"] as const;

export const Route = createFileRoute("/app/resolved")({
  beforeLoad: () => requireRole(...PAGE_ACCESS_ROLES),
  head: () => ({ meta: [{ title: "Tickets résolus — EDG Support" }] }),
  component: ResolvedTicketsPage,
});

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

function ResolvedTicketsPage() {
  const navigate = useNavigate();
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const searchTerm = search.trim().toLowerCase();

  // Le périmètre est forcé par le serveur depuis le jeton : la recherche ne
  // filtre que l'affichage local, elle n'élargit jamais ce qui est renvoyé.
  const { data, isLoading, isError } = useQuery({
    queryKey: ["resolved-by-me"],
    queryFn: () => fetchResolvedByMe({ limit: 200 }),
    staleTime: 30_000,
  });

  const allItems = data?.items ?? [];
  const items = searchTerm
    ? allItems.filter((r) =>
        [r.ref, r.title, r.requesterName].some((v) => v?.toLowerCase().includes(searchTerm)),
      )
    : allItems;

  const total = items.length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const paged = items.slice((page - 1) * pageSize, page * pageSize);

  const openTicket = (ticketId: string) =>
    navigate({ to: "/app/resolved/tickets/$id", params: { id: ticketId } });

  const state: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
      ? "empty"
      : "ready";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-end justify-between gap-3"
      >
        <div>
          <div className="flex items-center gap-2">
            <FileCheck2 className="h-6 w-6 text-success" />
            <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Tickets résolus</h1>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} ticket{total > 1 ? "s" : ""} dont vous avez terminé le traitement.
          </p>
        </div>
        <LayoutToggle layout={layout} onChange={setLayout} />
      </motion.header>

      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.06 }}
      >
        <GlassCard className="p-4">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }}
              placeholder="Rechercher par référence, titre, demandeur…"
              className="h-11 w-full rounded-xl border border-border/50 bg-background/50 pl-9 pr-9 text-sm outline-none focus:border-primary/40"
            />
            {search && (
              <button
                type="button"
                onClick={() => { setSearch(""); setPage(1); }}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                aria-label="Effacer la recherche"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </GlassCard>
      </motion.div>

      <AsyncSwap
        state={state}
        empty={
          <GlassCard className="py-16 text-center">
            <motion.div
              className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 18 }}
            >
              {isError
                ? <AlertTriangle className="h-6 w-6 text-muted-foreground" />
                : <CheckCircle2 className="h-6 w-6 text-success" />}
            </motion.div>
            <h3 className="font-semibold">
              {isError
                ? "Erreur de chargement"
                : searchTerm
                  ? "Aucun ticket résolu trouvé"
                  : "Aucun ticket résolu"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError
                ? "Impossible de charger vos tickets résolus."
                : searchTerm
                  ? "Essayez une autre référence, un titre ou un demandeur."
                  : "Vous n'avez encore terminé le traitement d'aucun ticket."}
            </p>
          </GlassCard>
        }
      >
        <>
          {layout === "list" ? (
            <GlassCard className="overflow-hidden p-0">
              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => (
                  <motion.div
                    key={r.id}
                    layout
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.3, delay: i * 0.03 }}
                    role="link"
                    tabIndex={0}
                    onClick={() => openTicket(r.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openTicket(r.id); }
                    }}
                    className="flex cursor-pointer items-start gap-4 border-b border-border/30 px-5 py-4 transition-colors last:border-0 hover:bg-background/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                  >
                    <div className="min-w-0 flex-1 space-y-1.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] text-primary">{r.ref}</span>
                        <PriorityBadge priority={r.priority} />
                        <StatusBadge status={r.status} />
                      </div>
                      <p className="font-semibold leading-snug">{r.title}</p>
                      <div className="text-xs text-muted-foreground">
                        {r.requesterName} · {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                      </div>
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </GlassCard>
          ) : (
            <motion.div layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
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
                    <GlassCard
                      className="flex h-full min-h-[172px] cursor-pointer flex-col gap-3 p-4 transition-shadow hover:shadow-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
                      role="link"
                      tabIndex={0}
                      onClick={() => openTicket(r.id)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openTicket(r.id); }
                      }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <StatusBadge status={r.status} />
                        <span className="font-mono text-[11px] text-muted-foreground/60">{r.ref}</span>
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
                      </div>
                    </GlassCard>
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
