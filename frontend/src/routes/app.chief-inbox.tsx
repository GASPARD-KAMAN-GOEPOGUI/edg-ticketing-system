import { createFileRoute, Link, useRouterState } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useUser } from "@/lib/session";
import { ticketDetailRouteForList, type TicketDetailRoute } from "@/lib/ticket-navigation";
import { useState, useMemo } from "react";
import { useQuery, useQueries } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { fetchQueue } from "@/lib/api/requests";
import { fetchUser, buildAvatarUrl } from "@/lib/api/accounts";
import { cn, initialsFor } from "@/lib/utils";
import {
  ClipboardList, UserPlus, RotateCcw,
  Clock, Inbox, AlertTriangle, Wrench,
} from "lucide-react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { AsyncSwap } from "@/components/async-states";
import type { RequestItem } from "@/lib/mock-data";

export const Route = createFileRoute("/app/chief-inbox")({
  beforeLoad: () => requireRole("chief-service", "admin"),
  head: () => ({ meta: [{ title: "Boîte de traitement — EDG Support" }] }),
  component: ChiefInbox,
});

// ── Types internes ─────────────────────────────────────────────────────────────

type Tab = "assign" | "reopen" | "escalated";

const TABS: { key: Tab; label: string; icon: typeof ClipboardList; color: string }[] = [
  { key: "assign",   label: "À affecter",    icon: UserPlus,       color: "text-primary" },
  { key: "reopen",   label: "Réouvertures",  icon: RotateCcw,      color: "text-amber-500" },
  { key: "escalated",label: "Escalades",     icon: AlertTriangle,  color: "text-destructive" },
];

// ── Helpers ────────────────────────────────────────────────────────────────────

function isToAssign(r: RequestItem): boolean {
  return ["new", "qualifying", "qualified", "assigned"].includes(r.status) &&
    !r.infos?.reopen_requested;
}
function isReopenPending(r: RequestItem): boolean {
  return r.infos?.reopen_requested === true;
}
function isEscalated(r: RequestItem): boolean {
  return r.status === "escalated";
}

// ── Sous-composant : carte ticket ──────────────────────────────────────────────
// Les actions (affecter, réaffecter, rejeter, résoudre, retour directeur…) ne
// sont plus des boutons sur la card : toute la card est cliquable et amène sur
// l'onglet "Traitement" de la fiche détaillée, où elles vivent déjà.

function TicketRow({ r, detailRoute, requesterAvatar }: { r: RequestItem; detailRoute: TicketDetailRoute; requesterAvatar?: string }) {
  const slaOver = r.slaElapsed > r.slaHours;
  const slaLeft = Math.max(0, r.slaHours - r.slaElapsed);
  const showReopen = r.infos?.reopen_requested === true;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
    >
      <Link to={detailRoute} params={{ id: r.id }} className="block h-full">
        <GlassCard className={cn(
          "flex h-full min-h-[196px] flex-col gap-3 p-4 transition-shadow hover:shadow-xl",
          r.priority === "critical" && "border-destructive/40 bg-destructive/3",
          showReopen               && "border-amber-500/40 bg-amber-500/3",
          r.status === "escalated" && "border-orange-400/40 bg-orange-500/3",
        )}>
          {/* Infos principales */}
          <div className="min-w-0 space-y-1.5">
            <div className="flex items-start justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[11px] text-primary">{r.ref}</span>
                <PriorityBadge priority={r.priority} />
                <StatusBadge status={r.status} />
                {showReopen && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                    <RotateCcw className="h-2.5 w-2.5" /> Réouverture demandée
                  </span>
                )}
                {r.priority === "critical" && (
                  <span className="inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-bold text-destructive">
                    CRITIQUE
                  </span>
                )}
              </div>
              <Avatar className="h-6 w-6 shrink-0 border border-border/60">
                <AvatarImage src={buildAvatarUrl(requesterAvatar)} alt={r.requesterName} />
                <AvatarFallback className="bg-primary/10 text-[10px] font-bold text-primary">
                  {initialsFor(r.requesterName)}
                </AvatarFallback>
              </Avatar>
            </div>
            <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
            <div className="text-xs text-muted-foreground">
              {r.requesterName} · {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
            </div>
          </div>

          <div className="flex-1" />

          {/* Pied de card */}
          <div className="flex items-center justify-between gap-2 border-t border-border/30 pt-3">
            <div className={cn("flex items-center gap-1 text-xs font-medium", slaOver ? "text-destructive" : "text-muted-foreground")}>
              <Clock className="h-3.5 w-3.5" />
              {slaOver ? "Délai dépassé" : `${slaLeft}h restantes`}
            </div>
            <span className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <Wrench className="h-3 w-3" /> Traiter
            </span>
          </div>
        </GlassCard>
      </Link>
    </motion.div>
  );
}

// ── Composant principal ────────────────────────────────────────────────────────
// Partagé par /app/chief-inbox (chief-service) et /app/department-inbox
// (chief-departement) : deux espaces distincts avec leur propre route, garde de
// rôle et navigation ticket, mais la même interface — seul le périmètre de
// données change (service unique vs département entier).

export function ChiefInbox() {
  const sessionUser = useUser();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isDepartmentSpace = pathname.startsWith("/app/department-inbox");
  const spaceKey = isDepartmentSpace ? "department-inbox" : "chief-inbox";
  const listRoute = isDepartmentSpace ? "/app/department-inbox" : "/app/chief-inbox";
  const detailRoute = ticketDetailRouteForList(listRoute);

  const [activeTab, setActiveTab] = useState<Tab>("assign");

  // ── Données service ──────────────────────────────────────────────────────────
  const { data: queueData, isLoading, isError } = useQuery({
    queryKey: [spaceKey, sessionUser?.id, sessionUser?.unit_id],
    queryFn: () => fetchQueue({
      limit: 200,
      ...(sessionUser?.unit_id ? { unit_id: sessionUser.unit_id } : {}),
    }),
    staleTime: 30_000,
    enabled: !!sessionUser?.id,
  });

  const allItems = queueData?.items ?? [];

  const toAssign   = useMemo(() => allItems.filter(isToAssign),      [allItems]);
  const toReopen   = useMemo(() => allItems.filter(isReopenPending), [allItems]);
  const escalated  = useMemo(() => allItems.filter(isEscalated),     [allItems]);

  const tabItems: Record<Tab, RequestItem[]> = {
    assign: toAssign, reopen: toReopen, escalated,
  };
  const displayed = tabItems[activeTab];

  // Avatars des demandeurs — un seul fetch par demandeur unique affiché dans l'onglet actif.
  const requesterIds = [...new Set(displayed.map((r) => r.requesterId).filter(Boolean))];
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
    ? "loading" : isError || displayed.length === 0 ? "empty" : "ready";

  const scopeLabel = isDepartmentSpace ? "département" : "service";
  const emptyMessages: Record<Tab, string> = {
    assign:   "Aucun ticket en attente d'affectation.",
    reopen:   "Aucune demande de réouverture en attente.",
    escalated:`Aucune escalade reçue pour votre ${scopeLabel}.`,
  };

  return (
    <div className="mx-auto max-w-7xl space-y-6">

      {/* ── En-tête ──────────────────────────────────────────────────────────── */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center gap-2">
          <ClipboardList className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            {isDepartmentSpace ? "Boîte de traitement — Département" : "Boîte de traitement"}
          </h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Tickets de votre {scopeLabel} nécessitant une action de votre part.
        </p>
      </motion.header>

      {/* ── KPI row ──────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.04 }}
        className="grid grid-cols-1 gap-3 sm:grid-cols-3"
      >
        {TABS.map((t) => {
          const count = tabItems[t.key].length;
          const Icon = t.icon;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={cn(
                "text-left transition-all",
                activeTab === t.key && "scale-[1.02]",
              )}
            >
              <GlassCard className={cn(
                "flex items-center gap-3 p-4 transition-shadow",
                activeTab === t.key && "ring-2 ring-primary/30",
                count > 0 && t.key === "reopen"   && "border-amber-500/40",
                count > 0 && t.key === "escalated" && "border-destructive/40",
              )}>
                <span className={cn(
                  "grid h-9 w-9 shrink-0 place-items-center rounded-xl",
                  t.key === "assign"    && "bg-primary/10",
                  t.key === "reopen"    && (count > 0 ? "bg-amber-500/15" : "bg-muted"),
                  t.key === "escalated" && (count > 0 ? "bg-destructive/15" : "bg-muted"),
                )}>
                  <Icon className={cn("h-4 w-4", count > 0 ? t.color : "text-muted-foreground")} />
                </span>
                <div>
                  <div className={cn("text-2xl font-bold leading-none", count > 0 && t.key !== "assign" && t.color)}>
                    {count}
                  </div>
                  <div className="mt-0.5 text-xs text-muted-foreground">{t.label}</div>
                </div>
              </GlassCard>
            </button>
          );
        })}
      </motion.div>

      {/* ── Onglets ──────────────────────────────────────────────────────────── */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.08 }}
        className="flex gap-2 border-b border-border/40"
      >
        {TABS.map((t) => {
          const count = tabItems[t.key].length;
          return (
            <button
              key={t.key}
              onClick={() => setActiveTab(t.key)}
              className={cn(
                "flex items-center gap-2 border-b-2 px-4 pb-3 pt-1 text-sm font-medium transition-colors",
                activeTab === t.key
                  ? "border-primary text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
              {count > 0 && (
                <span className={cn(
                  "rounded-full px-1.5 py-0.5 text-[10px] font-bold",
                  t.key === "assign"    && "bg-primary/15 text-primary",
                  t.key === "reopen"    && "bg-amber-500/15 text-amber-600 dark:text-amber-400",
                  t.key === "escalated" && "bg-destructive/15 text-destructive",
                )}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </motion.div>

      {/* ── Grille ───────────────────────────────────────────────────────────── */}
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
            <h3 className="font-semibold">
              {isError ? "Erreur de chargement" : "Tout est traité"}
            </h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError ? "Impossible de charger les tickets." : emptyMessages[activeTab]}
            </p>
          </GlassCard>
        }
      >
        <GlassCard className="p-4">
          <div className="grid gap-3 xl:grid-cols-2">
            <AnimatePresence mode="popLayout" initial={false}>
              {displayed.map((r) => (
                <TicketRow
                  key={r.id}
                  r={r}
                  detailRoute={detailRoute}
                  requesterAvatar={requesterAvatarById.get(r.requesterId)?.avatar}
                />
              ))}
            </AnimatePresence>
          </div>
        </GlassCard>
      </AsyncSwap>
    </div>
  );
}
