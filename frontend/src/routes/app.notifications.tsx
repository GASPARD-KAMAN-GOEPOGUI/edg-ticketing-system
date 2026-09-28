import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import {
  Bell,
  CheckCircle2,
  AlertTriangle,
  MessageSquare,
  Mail,
  MailOpen,
  ArrowRight,
  Zap,
  RotateCcw,
  MessageCircleReply,
  ShieldAlert,
  BellOff,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
} from "@/lib/api/notifications";
import { closeRequest, reopenRequest } from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import { PaginationBar, usePagination } from "@/components/pagination-bar";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { toast } from "sonner";
import type { Role } from "@/lib/mock-data";
import { useRole, useUser } from "@/lib/session";
import { ticketDetailRouteForNotification } from "@/lib/ticket-navigation";

export const Route = createFileRoute("/app/notifications")({
  head: () => ({ meta: [{ title: "Notifications — EDG Support" }] }),
  component: Notifications,
});

type NotifType = "info" | "success" | "warning";

type Notif = {
  id: string;
  type: NotifType;
  title: string;
  body: string;
  at: string;
  read: boolean;
  requestId?: string;
  actionUrl?: string;
  source: "request" | "system";
};


// ── Utilitaires visuels ────────────────────────────────────────────────────
const iconFor = (t: NotifType) =>
  t === "success" ? CheckCircle2 : t === "warning" ? AlertTriangle : MessageSquare;

const toneFor = (t: NotifType) =>
  t === "success"
    ? "bg-success/15 text-success"
    : t === "warning"
      ? "bg-warning/20 text-warning-foreground dark:text-warning"
      : "bg-info/15 text-info";

const labelFor = (t: NotifType, source?: "request" | "system") =>
  source === "system" ? "Système" : t === "success" ? "Résolution" : t === "warning" ? "Alerte" : "Info";

const labelToneFor = (t: NotifType) =>
  t === "success"
    ? "bg-success/12 text-success"
    : t === "warning"
      ? "bg-warning/15 text-warning-foreground dark:text-warning"
      : "bg-info/12 text-info";

const borderFor = (n: Notif) =>
  !n.read
    ? n.type === "warning"
      ? "border-l-4 border-l-warning/60"
      : n.type === "success"
        ? "border-l-4 border-l-success/60"
        : "border-l-4 border-l-primary/50"
    : "";

// ── Actions contextuelles ──────────────────────────────────────────────────
type ActionDef = {
  label: string;
  icon: typeof ArrowRight;
  variant: "default" | "outline" | "ghost";
  action: "navigate" | "close" | "reopen";
};

function getActions(n: Notif): ActionDef[] {
  const t = n.title.toLowerCase();
  if (t.includes("sla"))
    return [
      { label: "Voir le ticket", icon: ArrowRight, variant: "outline", action: "navigate" },
      { label: "Prendre en charge", icon: Zap, variant: "default", action: "navigate" },
    ];
  if (t.includes("commentaire") || t.includes("réponse reçue"))
    return [
      { label: "Répondre", icon: MessageCircleReply, variant: "outline", action: "navigate" },
    ];
  if (t.includes("résolue"))
    return [
      { label: "Confirmer clôture", icon: CheckCircle2, variant: "default", action: "close" },
      { label: "Rouvrir", icon: RotateCcw, variant: "ghost", action: "reopen" },
    ];
  // Toutes les notifications liées à une demande (assignée, routée, rejetée, etc.)
  if (n.requestId && n.source === "request")
    return [
      { label: "Voir le ticket", icon: ArrowRight, variant: "outline", action: "navigate" },
    ];
  return [];
}

function isQualificationNotification(n: Notif): boolean {
  const target = `${n.actionUrl ?? ""} ${n.title} ${n.body}`.toLowerCase();
  return (
    target.includes("/app/triage") ||
    target.includes("/app/queue?tab=qualify") ||
    target.includes("demande à qualifier") ||
    target.includes("demande a qualifier") ||
    target.includes("support général") ||
    target.includes("support general")
  );
}

/** Une notification designe TOUJOURS un ticket precis : on ouvre sa fiche, sur
 *  le panneau d'actions.
 *
 *  Les notifications de qualification renvoyaient auparavant vers la file
 *  d'attente entiere (`/app/queue`) : il fallait y retrouver le bon ticket,
 *  le deplier, puis chercher l'action — alors que la notification portait deja
 *  son `request_id`. Le repli sur la liste ne subsiste que si ce dernier
 *  manque, ce qui ne devrait pas arriver.
 *
 *  `actionUrl` continue de choisir l'ESPACE de destination (file d'attente,
 *  Distribution, Ma boite...) pour que le fil d'Ariane et le bouton Retour
 *  restent coherents avec l'endroit d'ou vient le ticket. */
function navigateNotification(n: Notif, navigate: ReturnType<typeof useNavigate>, role: Role): boolean {
  if (n.requestId) {
    navigate({
      to: ticketDetailRouteForNotification(n.actionUrl, role),
      params: { id: n.requestId },
      search: { tab: "treatment" },
    });
    return true;
  }
  if (isQualificationNotification(n)) {
    navigate({ to: "/app/queue", search: { tab: "qualify" } });
    return true;
  }
  return false;
}

// ── Composant carte — mode LISTE ───────────────────────────────────────────
function NotifListCard({
  n,
  onCardClick,
  onToggleRead,
  archived,
  navigate,
  role,
  onActionToast,
  onClose,
  onReopen,
}: {
  n: Notif;
  onCardClick: (n: Notif) => void;
  onToggleRead: (id: string) => void;
  archived: boolean;
  navigate: ReturnType<typeof useNavigate>;
  role: Role;
  onActionToast: (msg: string) => void;
  onClose: (id: string) => void;
  onReopen: (id: string) => void;
}) {
  const Icon = iconFor(n.type);
  const actions = getActions(n);
  return (
    <GlassCard
      className={cn(
        "group relative overflow-hidden p-0 transition-all hover:shadow-lg",
        borderFor(n),
      )}
    >
      {/* Zone cliquable principale */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onCardClick(n)}
        onKeyDown={(e) => e.key === "Enter" && onCardClick(n)}
        className={cn(
          "flex cursor-pointer items-start gap-4 px-5 py-4",
          n.requestId && "hover:bg-foreground/3",
        )}
      >
        <span className={cn("mt-0.5 grid h-10 w-10 shrink-0 place-items-center rounded-xl", toneFor(n.type))}>
          <Icon className="h-5 w-5" />
        </span>

        <div className="min-w-0 flex-1 pr-14">
          <div className="flex flex-wrap items-center gap-2">
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide", labelToneFor(n.type))}>
              {labelFor(n.type, n.source)}
            </span>
            <h3 className="font-semibold leading-tight">{n.title}</h3>
            {!n.read && (
              <span className="h-2 w-2 shrink-0 rounded-full bg-primary" />
            )}
          </div>
          <p className="mt-1 text-sm text-muted-foreground leading-relaxed">{n.body}</p>
          <div className="mt-1.5 text-xs text-muted-foreground">{n.at}</div>
        </div>
      </div>

      {/* Boutons d'action contextuels */}
      {actions.length > 0 && (
        <div
          className="flex flex-wrap gap-2 border-t border-border/30 px-5 pb-3.5 pt-2.5"
          onClick={(e) => e.stopPropagation()}
        >
          {actions.map((a) => (
            <Button
              key={a.label}
              size="sm"
              variant={a.variant}
              className={cn(
                "h-7 rounded-full px-3 text-xs",
                a.variant === "default" && "gradient-primary text-primary-foreground",
              )}
              onClick={() => {
                onToggleRead(n.id);
                if (a.action === "navigate") {
                  if (!navigateNotification(n, navigate, role)) {
                    toast.info("Aucun ticket lié à cette notification.");
                  }
                } else if (a.action === "close") {
                  if (n.requestId) onClose(n.requestId);
                  else toast.info("Aucun ticket lié à cette notification.");
                } else if (a.action === "reopen") {
                  if (n.requestId) onReopen(n.requestId);
                  else toast.info("Aucun ticket lié à cette notification.");
                }
              }}
            >
              <a.icon className="mr-1 h-3 w-3" />
              {a.label}
            </Button>
          ))}
        </div>
      )}

      {/* Boutons lu/supprimer */}
      <div
        className="absolute right-3 top-3 flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={() => onToggleRead(n.id)}
          className="rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-foreground/8 hover:text-foreground"
          title={n.read ? "Marquer non lue" : "Marquer lue"}
        >
          {n.read ? <Mail className="h-3.5 w-3.5" /> : <MailOpen className="h-3.5 w-3.5" />}
        </button>
      </div>
    </GlassCard>
  );
}

// ── Composant carte — mode GRILLE ──────────────────────────────────────────
function NotifGridCard({
  n,
  onCardClick,
  onToggleRead,
  archived,
  navigate,
  role,
  onActionToast,
  onClose,
  onReopen,
}: {
  n: Notif;
  onCardClick: (n: Notif) => void;
  onToggleRead: (id: string) => void;
  archived: boolean;
  navigate: ReturnType<typeof useNavigate>;
  role: Role;
  onActionToast: (msg: string) => void;
  onClose: (id: string) => void;
  onReopen: (id: string) => void;
}) {
  const Icon = iconFor(n.type);
  const actions = getActions(n);
  return (
    <GlassCard
      className={cn(
        "group relative flex h-full flex-col overflow-hidden p-0 transition-all hover:shadow-lg hover:-translate-y-0.5",
        borderFor(n),
      )}
    >
      {/* Haut : icône + type + temps + actions lu/del */}
      <div className="flex items-start justify-between gap-2 px-4 pt-4">
        <div className="flex items-center gap-2.5">
          <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", toneFor(n.type))}>
            <Icon className="h-4.5 w-4.5" />
          </span>
          <div>
            <span className={cn("rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide", labelToneFor(n.type))}>
              {labelFor(n.type, n.source)}
            </span>
            <div className="mt-0.5 text-[10px] text-muted-foreground">{n.at}</div>
          </div>
        </div>
        <div className="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
          <button
            onClick={(e) => { e.stopPropagation(); onToggleRead(n.id); }}
            className="rounded-md p-1 text-muted-foreground transition hover:bg-foreground/8 hover:text-foreground"
            title={n.read ? "Marquer non lue" : "Marquer lue"}
          >
            {n.read ? <Mail className="h-3 w-3" /> : <MailOpen className="h-3 w-3" />}
          </button>
        </div>
      </div>

      {/* Corps : titre + body cliquable */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onCardClick(n)}
        onKeyDown={(e) => e.key === "Enter" && onCardClick(n)}
        className={cn(
          "flex-1 cursor-pointer px-4 pb-3 pt-2",
          n.requestId && "hover:bg-foreground/3",
        )}
      >
        <div className="flex items-start gap-1.5">
          <h3 className="flex-1 text-sm font-semibold leading-snug">{n.title}</h3>
          {!n.read && (
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-primary" />
          )}
        </div>
        <p className="mt-1 line-clamp-3 text-xs text-muted-foreground leading-relaxed">
          {n.body}
        </p>
      </div>

      {/* Pied : actions */}
      {actions.length > 0 && (
        <div
          className="flex flex-wrap gap-1.5 border-t border-border/30 px-4 pb-3.5 pt-2.5"
          onClick={(e) => e.stopPropagation()}
        >
          {actions.map((a) => (
            <Button
              key={a.label}
              size="sm"
              variant={a.variant}
              className={cn(
                "h-6 rounded-full px-2.5 text-[11px]",
                a.variant === "default" && "gradient-primary text-primary-foreground",
              )}
              onClick={() => {
                onToggleRead(n.id);
                if (a.action === "navigate") {
                  if (!navigateNotification(n, navigate, role)) {
                    toast.info("Aucun ticket lié à cette notification.");
                  }
                } else if (a.action === "close") {
                  if (n.requestId) onClose(n.requestId);
                  else toast.info("Aucun ticket lié à cette notification.");
                } else if (a.action === "reopen") {
                  if (n.requestId) onReopen(n.requestId);
                  else toast.info("Aucun ticket lié à cette notification.");
                }
              }}
            >
              <a.icon className="mr-1 h-3 w-3" />
              {a.label}
            </Button>
          ))}
        </div>
      )}
    </GlassCard>
  );
}

// ── Page principale ────────────────────────────────────────────────────────
function Notifications() {
  const [role] = useRole();
  const sessionUser = useUser();
  const meId = sessionUser?.id;
  const qc = useQueryClient();

  const [filter, setFilter] = useState<"all" | "unread" | "archived">("all");
  const isArchivedView = filter === "archived";

  /* ── Notifications API — invalidées en temps réel via SSE (notification.*) ── */
  const { data: apiData } = useQuery({
    queryKey: ["notifications", meId, isArchivedView],
    queryFn: () => fetchNotifications({ meId, limit: 100, archived: isArchivedView }),
    enabled: !!meId,
    staleTime: 10_000,
    refetchOnWindowFocus: true,
  });

  const [reqNotifs, setReqNotifs] = useState<Notif[]>([]);
  useEffect(() => {
    // Pas de `if (!apiData) return` : au changement d'onglet la queryKey change
    // et `apiData` repasse à `undefined` le temps du chargement. Sortir ici
    // laissait afficher la liste de l'onglet PRÉCÉDENT — on montrait
    // l'historique sous l'onglet "Non lues", et inversement. Une liste vide le
    // temps du chargement est le comportement juste.
    setReqNotifs((apiData?.items as Notif[]) ?? []);
  }, [apiData]);

  /* ── Mutations ── */
  const markReadMut = useMutation({
    mutationFn: markNotificationRead,
    onError: () => toast.error("Impossible de marquer comme lue"),
    // Sans cette invalidation, le cache React Query gardait l'état d'AVANT la
    // lecture : `markRead`/`toggleRead` ne mettaient à jour que l'état local du
    // composant. En quittant puis revenant sur la page, l'effet ci-dessous
    // réécrasait cet état avec le cache périmé — les notifications
    // réapparaissaient non lues et l'onglet "Archivées" restait vide. Seul un
    // rechargement complet de la page, qui vide le cache mémoire, remettait
    // l'affichage d'aplomb. `markAllReadMut` invalidait déjà, d'où l'asymétrie.
    onSettled: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });

  const markAllReadMut = useMutation({
    mutationFn: () => markAllNotificationsRead(meId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
    onError: () => toast.error("Erreur lors du marquage"),
  });

  const notifs: Notif[] = reqNotifs;

  const [layout, setLayout] = useState<LayoutMode>("list");
  const navigate = useNavigate();

  const unread   = notifs.filter((n) => !n.read).length;
  const slaCount = reqNotifs.filter((n) => n.type === "warning" && n.title.toLowerCase().includes("sla")).length;
  const resCount = reqNotifs.filter((n) => n.title.toLowerCase().includes("résolue")).length;

  const visible = notifs
    .filter((n) => (filter === "unread" ? !n.read : true));

  const pageSize = layout === "grid" ? 9 : 6;
  const { paged, page, setPage, totalPages, total, setPageSize } =
    usePagination(visible, pageSize);

  const markRead = (id: string) => {
    setReqNotifs((p) => p.map((n) => (n.id === id ? { ...n, read: true } : n)));
    markReadMut.mutate(id);
  };

  const toggleRead = (id: string) => {
    const current = reqNotifs.find((n) => n.id === id);
    setReqNotifs((p) => p.map((n) => (n.id === id ? { ...n, read: !n.read } : n)));
    // API only supports mark-as-read (one-way); call only when transitioning unread→read
    if (current && !current.read) markReadMut.mutate(id);
  };


  const markAllRead = () => {
    setReqNotifs((p) => p.map((n) => ({ ...n, read: true })));
    markAllReadMut.mutate();
  };

  const handleCardClick = (n: Notif) => {
    markRead(n.id);
    navigateNotification(n, navigate, role);
  };

  const handleActionToast = (msg: string) => toast.success(msg);

  const invalidateRequests = () => {
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["request"] });
    qc.invalidateQueries({ queryKey: ["queue"] });
    qc.invalidateQueries({ queryKey: ["my-tickets"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
    qc.invalidateQueries({ queryKey: ["csat-stats"] });
  };

  const closeMut = useMutation({
    mutationFn: (id: string) => closeRequest(id),
    onSuccess: () => { invalidateRequests(); toast.success("Ticket clôturé."); },
    onError: () => toast.error("Impossible de clôturer le ticket."),
  });

  const reopenMut = useMutation({
    // BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : raccourci "Rouvrir"
    // depuis une notification, motif générique — le ticket retourne directement
    // en File d'attente (plus d'approbation chef à attendre).
    mutationFn: (id: string) => reopenRequest(id, "Réouverture demandée depuis les notifications."),
    onSuccess: () => { invalidateRequests(); toast.success("Ticket réouvert et replacé dans la File d'attente."); },
    onError: () => toast.error("Impossible de rouvrir le ticket."),
  });

  const cardProps = {
    onCardClick: handleCardClick,
    onToggleRead: toggleRead,
    archived: isArchivedView,
    navigate,
    role,
    onActionToast: handleActionToast,
    onClose: (id: string) => closeMut.mutate(id),
    onReopen: (id: string) => reopenMut.mutate(id),
  };

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      {/* ── En-tête ── */}
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Notifications
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {unread > 0
              ? `${unread} non lue${unread > 1 ? "s" : ""} sur ${notifs.length}`
              : "Toutes les notifications sont lues."}
          </p>
        </div>
        {/* Masqué à la demande du métier (2026-08-14). */}
        <div className="hidden items-center gap-2">
          {unread > 0 && (
            <Button variant="outline" className="rounded-full" onClick={markAllRead}>
              <MailOpen className="mr-1.5 h-4 w-4" /> Tout marquer lu
            </Button>
          )}
          <LayoutToggle layout={layout} onChange={setLayout} />
        </div>
      </header>

      {/* ── Résumé rapide — masqué à la demande du métier (2026-08-14) ── */}
      <div className="hidden grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-5">
        {[
          { label: "Non lues", value: unread, icon: Bell, tone: "text-primary bg-primary/10" },
          { label: "Alertes délais", value: slaCount, icon: AlertTriangle, tone: "text-warning-foreground dark:text-warning bg-warning/15" },
          { label: "Résolues", value: resCount, icon: CheckCircle2, tone: "text-success bg-success/12" },
        ].map(({ label, value, icon: Ic, tone }) => (
          <GlassCard key={label} className="flex items-center gap-3 py-3">
            <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", tone)}>
              <Ic className="h-4 w-4" />
            </span>
            <div>
              <div className="text-xl font-bold">{value}</div>
              <div className="text-[11px] text-muted-foreground">{label}</div>
            </div>
          </GlassCard>
        ))}
      </div>

      {/* ── Barre de filtres ── */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-2xl border border-border/40 bg-card/40 p-1">
          {(["all", "unread", "archived"] as const).map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1); }}
              className={cn(
                "rounded-xl px-4 py-1.5 text-sm font-medium transition-colors",
                filter === f
                  ? "bg-primary text-white shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {f === "all"
                ? isArchivedView ? "Toutes" : `Toutes (${notifs.length})`
                : f === "unread"
                  ? `Non lues${!isArchivedView && unread > 0 ? ` (${unread})` : ""}`
                  : "Archivées"}
            </button>
          ))}
        </div>
      </div>

      {/* ── Contenu ── */}
      {visible.length === 0 ? (
        <GlassCard className="py-20 text-center">
          <BellOff className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-3 font-semibold text-muted-foreground">
            {filter === "unread"
              ? "Aucune notification non lue"
              : filter === "archived"
                ? "Aucune notification archivée"
                : "Aucune notification"}
          </p>
          {filter === "unread" && (
            <button
              onClick={() => setFilter("all")}
              className="mt-1.5 text-sm text-primary hover:underline"
            >
              Voir toutes les notifications
            </button>
          )}
        </GlassCard>
      ) : layout === "list" ? (
        /* ── VUE LISTE ── */
        <div className="space-y-2.5">
          {paged.map((n) => (
            <NotifListCard key={n.id} n={n} {...cardProps} />
          ))}
        </div>
      ) : (
        /* ── VUE GRILLE ── */
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {paged.map((n) => (
            <NotifGridCard key={n.id} n={n} {...cardProps} />
          ))}
        </div>
      )}

      <PaginationBar
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
        onChange={setPage}
        onPageSizeChange={setPageSize}
        pageSizeOptions={layout === "grid" ? [9, 18] : [6, 10, 20]}
      />
    </div>
  );
}
