import { useState, useEffect } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  deleteNotification,
} from "@/lib/api/notifications";
import type { NotifItem } from "@/lib/api/notifications";
import { closeRequest, reopenRequest } from "@/lib/api/requests";
import {
  fetchPublishedAnnouncements,
  fetchActiveAlerts,
  roleToAnnounceAudience,
} from "@/lib/api/communication";
import type { Announcement } from "@/lib/mock-data";
import { announcementCategoryLabels } from "@/lib/mock-data";
import type { Role } from "@/lib/mock-data";
import { ticketDetailRouteForNotification } from "@/lib/ticket-navigation";
import {
  Bell, BellOff, Mail, MailOpen, X, ArrowRight,
  AlertTriangle, CheckCircle2, MessageSquare,
  Megaphone, ShieldAlert, Zap, RotateCcw,
} from "lucide-react";
import { toast } from "sonner";

type NotifType = "info" | "success" | "warning";
type Source = "request" | "announcement";

type PanelNotif = NotifItem & { source: Source };

function isQualificationNotification(n: PanelNotif): boolean {
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

function isInfoRequestNotification(n: PanelNotif): boolean {
  const target = `${n.title} ${n.body}`.toLowerCase();
  return (
    target.includes("information complémentaire") ||
    target.includes("information complementaire") ||
    target.includes("attend votre retour")
  );
}

const iconFor = (t: NotifType, source?: Source) => {
  if (source === "announcement") return Megaphone;
  if (t === "success") return CheckCircle2;
  if (t === "warning") return AlertTriangle;
  return MessageSquare;
};

const iconTone = (t: NotifType, source?: Source) => {
  if (source === "announcement") return "bg-primary/15 text-primary";
  if (t === "success") return "bg-success/15 text-success";
  if (t === "warning") return "bg-warning/20 text-warning-foreground dark:text-warning";
  return "bg-info/15 text-info";
};

const badgeLabel = (t: NotifType, source?: Source) => {
  if (source === "announcement") return "Annonce";
  if (t === "success") return "Résolution";
  if (t === "warning") return "Alerte";
  return "Info";
};

const badgeTone = (t: NotifType, source?: Source) => {
  if (source === "announcement") return "bg-primary/12 text-primary";
  if (t === "success") return "bg-success/12 text-success";
  if (t === "warning") return "bg-warning/15 text-warning-foreground dark:text-warning";
  return "bg-info/12 text-info";
};

type FilterTab = "all" | "unread" | "request" | "announcement" | "alerts";

export function NotificationPanel({
  open,
  onClose,
  meId,
  role,
}: {
  open: boolean;
  onClose: () => void;
  meId?: string;
  role: Role;
}) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // ── Notifications de demandes ──────────────────────────────────────────────
  const { data: apiData } = useQuery({
    queryKey: ["notifications", meId],
    queryFn: () => fetchNotifications({ meId, limit: 50 }),
    enabled: !!meId && open,
    staleTime: 20_000,
    refetchInterval: open ? 30_000 : false,
  });

  const [reqNotifs, setReqNotifs] = useState<PanelNotif[]>([]);
  useEffect(() => {
    if (!apiData?.items) return;
    setReqNotifs(
      apiData.items.map((n) => ({ ...n, source: (n.requestId ? "request" : "announcement") as Source })),
    );
  }, [apiData]);

  // ── Annonces publiées depuis le backend ─────────────────────────────────────
  const { data: annData } = useQuery({
    queryKey: ["announcements-active", role],
    queryFn: () => fetchPublishedAnnouncements({ audience: roleToAnnounceAudience(role), limit: 30 }),
    staleTime: 120_000,
    enabled: open,
  });

  // ── Alertes actives (ex-bandeaux) ───────────────────────────────────────────
  const { data: activeAlertsRaw } = useQuery({
    queryKey: ["active-alerts"],
    queryFn: fetchActiveAlerts,
    staleTime: 60_000,
    enabled: open,
  });
  const activeAlerts: Announcement[] = activeAlertsRaw ?? [];

  const [readAnnIds, setReadAnnIds] = useState<string[]>([]);
  const [hiddenAnnIds, setHiddenAnnIds] = useState<string[]>([]);

  const annNotifs: PanelNotif[] = (annData?.items ?? [])
    .filter((a) => !hiddenAnnIds.includes(a.id))
    .map((a) => ({
      id: `ann_${a.id}`,
      type: (a.priority === "critical" || a.priority === "absolute_emergency" ? "warning" : "info") as NotifType,
      title: a.title,
      body: `${announcementCategoryLabels[a.category] ?? a.category} — ${a.description.slice(0, 100)}${a.description.length > 100 ? "…" : ""}`,
      at: new Date(a.publishedAt).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }),
      read: readAnnIds.includes(a.id),
      source: "announcement" as Source,
    }));

  const allNotifs: PanelNotif[] = [...reqNotifs, ...annNotifs];
  const unread = allNotifs.filter((n) => !n.read).length;

  // Notifications d'alerte liées à des tickets (SLA, escalades, résolutions)
  const alertNotifs = reqNotifs.filter((n) => {
    const t = n.title.toLowerCase();
    return n.type === "warning" || t.includes("sla") || t.includes("escalade") || t.includes("résolue");
  });

  const [tab, setTab] = useState<FilterTab>("all");

  const visible = allNotifs.filter((n) => {
    if (tab === "unread") return !n.read;
    if (tab === "request") return n.source === "request";
    if (tab === "announcement") return n.source === "announcement";
    if (tab === "alerts") return false; // section séparée ci-dessous
    return true;
  });

  const invalidateNotifs = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });

  // onError réinvalide aussi : l'échec optimiste local (setReqNotifs) doit être
  // corrigé par un refetch de l'état réel, sinon le badge de la cloche affiche
  // "lu" en local sans que ce soit jamais persisté côté serveur (l'utilisateur
  // le découvre seulement après un rechargement complet de la page).
  const markReadMut = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: invalidateNotifs,
    onError: () => {
      invalidateNotifs();
      toast.error("Impossible de marquer la notification comme lue — réessaie.");
    },
  });
  const deleteNotifMut = useMutation({
    mutationFn: deleteNotification,
    onSuccess: invalidateNotifs,
    onError: () => {
      invalidateNotifs();
      toast.error("Impossible d'archiver la notification — réessaie.");
    },
  });
  const markAllReadMut = useMutation({
    mutationFn: () => markAllNotificationsRead(meId),
    onSuccess: invalidateNotifs,
    onError: () => {
      invalidateNotifs();
      toast.error("Impossible de marquer toutes les notifications comme lues — réessaie.");
    },
  });

  const closeMut = useMutation({
    mutationFn: (id: string) => closeRequest(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Ticket clôturé.");
    },
    onError: () => toast.error("Impossible de clôturer le ticket."),
  });

  const reopenMut = useMutation({
    // BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : plus d'approbation
    // chef à attendre, le ticket retourne directement en File d'attente.
    mutationFn: (id: string) => reopenRequest(id, "Réouverture demandée depuis les notifications."),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["notifications"] });
      toast.success("Ticket réouvert et replacé dans la File d'attente.");
    },
    onError: () => toast.error("Impossible de rouvrir le ticket."),
  });

  const markRead = (id: string) => {
    if (id.startsWith("ann_")) {
      setReadAnnIds((p) => (p.includes(id.slice(4)) ? p : [...p, id.slice(4)]));
    } else {
      setReqNotifs((p) => p.map((n) => n.id === id ? { ...n, read: true } : n));
      markReadMut.mutate(id);
    }
  };

  const toggleRead = (id: string) => {
    if (id.startsWith("ann_")) {
      const aid = id.slice(4);
      setReadAnnIds((p) => p.includes(aid) ? p.filter((x) => x !== aid) : [...p, aid]);
    } else {
      const current = reqNotifs.find((n) => n.id === id);
      setReqNotifs((p) => p.map((n) => n.id === id ? { ...n, read: !n.read } : n));
      if (current && !current.read) markReadMut.mutate(id);
    }
  };

  const remove = (id: string) => {
    if (id.startsWith("ann_")) {
      setHiddenAnnIds((p) => [...p, id.slice(4)]);
    } else {
      setReqNotifs((p) => p.filter((n) => n.id !== id));
      deleteNotifMut.mutate(id);
    }
    toast.success("Notification archivée");
  };

  const markAll = () => {
    setReqNotifs((p) => p.map((n) => ({ ...n, read: true })));
    setReadAnnIds((annData?.items ?? []).filter((a) => !hiddenAnnIds.includes(a.id)).map((a) => a.id));
    markAllReadMut.mutate();
  };

  const openTicketFromNotification = (n: PanelNotif) => {
    if (!n.requestId) return;
    onClose();
    navigate({
      to: ticketDetailRouteForNotification(n.actionUrl, role),
      params: { id: n.requestId },
      search: isInfoRequestNotification(n) ? { tab: "comments" } : undefined,
    });
  };

  const handleClick = (n: PanelNotif) => {
    markRead(n.id);
    if (isQualificationNotification(n)) {
      onClose();
      navigate({ to: "/app/queue", search: { tab: "qualify" } });
      return;
    }
    if (n.requestId) {
      openTicketFromNotification(n);
    }
  };

  const alertTabCount = activeAlerts.length + alertNotifs.length;
  const TABS: { key: FilterTab; label: string }[] = [
    { key: "all", label: `Toutes (${allNotifs.length})` },
    { key: "unread", label: `Non lues${unread > 0 ? ` (${unread})` : ""}` },
    { key: "request", label: "Tickets" },
    { key: "announcement", label: "Annonces" },
    ...(alertTabCount > 0 ? [{ key: "alerts" as FilterTab, label: `Alertes (${alertTabCount})` }] : []),
  ];

  return (
    <Sheet open={open} onOpenChange={(v) => !v && onClose()}>
      <SheetContent
        side="right"
        className="flex w-full flex-col gap-0 p-0 sm:max-w-[440px]"
      >
        {/* ── En-tête ── */}
        <SheetHeader className="shrink-0 border-b border-border/40 px-5 py-4">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary">
                <Bell className="h-4 w-4" />
              </div>
              <div>
                <SheetTitle className="text-base font-semibold leading-tight">
                  Notifications
                </SheetTitle>
                <p className="text-[11px] text-muted-foreground">
                  {unread > 0
                    ? `${unread} non lue${unread > 1 ? "s" : ""} sur ${allNotifs.length}`
                    : "Toutes lues"}
                </p>
              </div>
            </div>
            {/* Masqué à la demande du métier (2026-08-14). */}
            {false && unread > 0 && (
              <Button
                variant="outline"
                size="sm"
                className="h-7 rounded-full px-3 text-xs"
                onClick={markAll}
              >
                <MailOpen className="mr-1.5 h-3 w-3" />
                Tout marquer lu
              </Button>
            )}
          </div>
        </SheetHeader>

        {/* ── Compteurs rapides — masqués à la demande du métier (2026-08-14) ── */}
        <div className="hidden shrink-0 gap-2 border-b border-border/30 px-5 py-3">
          {[
            { label: "Non lues", value: unread, tone: "bg-primary/10 text-primary" },
            { label: "Alertes délais", value: reqNotifs.filter((n) => n.type === "warning").length, tone: "bg-warning/15 text-warning-foreground dark:text-warning" },
            { label: "Escalades", value: reqNotifs.filter((n) => n.title.toLowerCase().includes("escalade")).length, tone: "bg-destructive/10 text-destructive" },
            { label: "Annonces", value: annNotifs.length, tone: "bg-primary/10 text-primary" },
          ].map(({ label, value, tone }) => (
            <div
              key={label}
              className={cn("flex flex-1 flex-col items-center rounded-xl px-2 py-2", tone)}
            >
              <span className="text-base font-bold leading-none">{value}</span>
              <span className="mt-0.5 text-center text-[9px] font-medium leading-tight">{label}</span>
            </div>
          ))}
        </div>

        {/* ── Tabs de filtre ── */}
        <div className="flex shrink-0 gap-1 border-b border-border/30 px-4 py-2">
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => setTab(t.key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                tab === t.key
                  ? "bg-background/70 text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Alertes actives — section dédiée ── */}
        {activeAlerts.length > 0 && tab !== "request" && tab !== "announcement" && (
          <div className="shrink-0 border-b border-border/30">
            <div className="flex items-center gap-2 px-5 py-2">
              <Zap className="h-3.5 w-3.5 text-destructive" />
              <span className="text-xs font-semibold uppercase tracking-wider text-destructive">
                Alertes en cours
              </span>
              <span className="ml-auto rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-bold text-destructive">
                {activeAlerts.length}
              </span>
            </div>
            <ul className="divide-y divide-border/20">
              {activeAlerts.map((a) => {
                const isCritical = a.priority === "critical" || a.priority === "absolute_emergency";
                return (
                  <li key={a.id} className="flex items-start gap-3 px-5 py-3">
                    <span className={cn(
                      "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl",
                      isCritical ? "bg-destructive/15 text-destructive" : "bg-warning/15 text-warning-foreground dark:text-warning",
                    )}>
                      <AlertTriangle className="h-3.5 w-3.5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={cn(
                          "rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide",
                          isCritical ? "bg-destructive/12 text-destructive" : "bg-warning/15 text-warning-foreground dark:text-warning",
                        )}>
                          {isCritical ? "Critique" : "Avertissement"}
                        </span>
                        <span className="text-xs font-semibold leading-snug">{a.title}</span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {a.description}
                      </p>
                      {a.expiresAt && (
                        <span className="mt-1 block text-[10px] text-muted-foreground/70">
                          Expire le {new Date(a.expiresAt).toLocaleDateString("fr-FR", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" })}
                        </span>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {/* ── Alertes — vue filtrée ── */}
        {tab === "alerts" && (
          <div className="flex-1 overflow-y-auto">
            {alertTabCount === 0 ? (
              <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
                <BellOff className="h-10 w-10 text-muted-foreground/30" />
                <p className="text-sm text-muted-foreground">Aucune alerte active</p>
              </div>
            ) : (
              <>
                {/* Notifications de tickets en alerte (SLA, escalade, résolution) */}
                {alertNotifs.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 border-b border-border/30 px-5 py-2">
                      <ShieldAlert className="h-3.5 w-3.5 text-warning-foreground dark:text-warning" />
                      <span className="text-xs font-semibold uppercase tracking-wider text-warning-foreground dark:text-warning">
                        Alertes tickets ({alertNotifs.length})
                      </span>
                    </div>
                    <ul className="divide-y divide-border/20">
                      {alertNotifs.map((n) => {
                        const t = n.title.toLowerCase();
                        const isEscalade = t.includes("escalade");
                        const isResolved = t.includes("résolue");
                        return (
                          <li key={n.id} className={cn("px-5 py-3", !n.read && "bg-primary/3")}>
                            <div
                              className={cn("flex items-start gap-3", n.requestId && "cursor-pointer")}
                              onClick={() => {
                                markRead(n.id);
                                if (isQualificationNotification(n)) {
                                  onClose();
                                  navigate({ to: "/app/queue", search: { tab: "qualify" } });
                                } else if (n.requestId) {
                                  openTicketFromNotification(n);
                                }
                              }}
                            >
                              <span className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl bg-warning/20 text-warning-foreground dark:text-warning">
                                {isEscalade ? <ShieldAlert className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}
                              </span>
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-semibold leading-snug">{n.title}</p>
                                <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground leading-relaxed">{n.body}</p>
                                <span className="text-[10px] text-muted-foreground/70">{n.at}</span>
                              </div>
                            </div>
                            {/* Boutons d'action */}
                            {n.requestId && (
                              <div className="mt-2 flex flex-wrap gap-1.5 pl-11">
                                {isResolved ? (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="default"
                                      className="h-6 rounded-full px-2.5 text-[11px] gradient-primary text-primary-foreground"
                                      onClick={(e) => { e.stopPropagation(); markRead(n.id); closeMut.mutate(n.requestId!); }}
                                    >
                                      <CheckCircle2 className="mr-1 h-3 w-3" />
                                      Confirmer clôture
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="h-6 rounded-full px-2.5 text-[11px]"
                                      onClick={(e) => { e.stopPropagation(); markRead(n.id); reopenMut.mutate(n.requestId!); }}
                                    >
                                      <RotateCcw className="mr-1 h-3 w-3" />
                                      Rouvrir
                                    </Button>
                                  </>
                                ) : (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      className="h-6 rounded-full px-2.5 text-[11px]"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        markRead(n.id);
                                        openTicketFromNotification(n);
                                      }}
                                    >
                                      <ArrowRight className="mr-1 h-3 w-3" />
                                      Voir
                                    </Button>
                                    {isEscalade && (
                                      <Button
                                        size="sm"
                                        variant="default"
                                        className="h-6 rounded-full px-2.5 text-[11px] gradient-primary text-primary-foreground"
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          markRead(n.id);
                                          openTicketFromNotification(n);
                                        }}
                                      >
                                        <ShieldAlert className="mr-1 h-3 w-3" />
                                        Traiter
                                      </Button>
                                    )}
                                  </>
                                )}
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}

                {/* Alertes système actives */}
                {activeAlerts.length > 0 && (
                  <div>
                    <div className="flex items-center gap-2 border-b border-border/30 px-5 py-2">
                      <Zap className="h-3.5 w-3.5 text-destructive" />
                      <span className="text-xs font-semibold uppercase tracking-wider text-destructive">
                        Alertes système ({activeAlerts.length})
                      </span>
                    </div>
                    <ul className="divide-y divide-border/30">
                      {activeAlerts.map((a) => {
                        const isCritical = a.priority === "critical" || a.priority === "absolute_emergency";
                        return (
                          <li key={a.id} className="flex items-start gap-3 px-5 py-4">
                            <span className={cn(
                              "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl",
                              isCritical ? "bg-destructive/15 text-destructive" : "bg-warning/15 text-warning-foreground dark:text-warning",
                            )}>
                              <AlertTriangle className="h-3.5 w-3.5" />
                            </span>
                            <div className="min-w-0 flex-1">
                              <p className="text-xs font-semibold leading-snug">{a.title}</p>
                              <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">{a.description}</p>
                              {a.expiresAt && (
                                <span className="mt-1 block text-[10px] text-muted-foreground/70">
                                  Expire le {new Date(a.expiresAt).toLocaleDateString("fr-FR", { day: "numeric", month: "short" })}
                                </span>
                              )}
                            </div>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* ── Liste notifications ── */}
        {tab !== "alerts" && <div className="flex-1 overflow-y-auto">
          {visible.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <BellOff className="h-10 w-10 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">
                {tab === "unread" ? "Aucune notification non lue" : "Aucune notification"}
              </p>
              {tab !== "all" && (
                <button
                  onClick={() => setTab("all")}
                  className="text-xs text-primary hover:underline"
                >
                  Voir toutes
                </button>
              )}
            </div>
          ) : (
            <ul className="divide-y divide-border/30">
              {visible.map((n) => {
                const Icon = iconFor(n.type, n.source);
                return (
                  <li
                    key={n.id}
                    className={cn(
                      "group relative flex items-start gap-3 px-5 py-4 transition-colors",
                      !n.read && "bg-primary/3",
                      n.requestId && "cursor-pointer hover:bg-foreground/4",
                    )}
                    onClick={() => handleClick(n)}
                  >
                    {/* Indicateur non lu */}
                    {!n.read && (
                      <span className="absolute left-2 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-primary" />
                    )}

                    {/* Icône */}
                    <span className={cn("mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-xl", iconTone(n.type, n.source))}>
                      <Icon className="h-3.5 w-3.5" />
                    </span>

                    {/* Corps */}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className={cn("rounded-full px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide", badgeTone(n.type, n.source))}>
                          {badgeLabel(n.type, n.source)}
                        </span>
                        <span className="text-xs font-semibold leading-snug">{n.title}</span>
                      </div>
                      <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground leading-relaxed">
                        {n.body}
                      </p>
                      <div className="mt-1 flex items-center justify-between">
                        <span className="text-[10px] text-muted-foreground/70">{n.at}</span>
                        {n.requestId && (
                          <span className="flex items-center gap-0.5 text-[10px] text-primary/70">
                            Voir <ArrowRight className="h-2.5 w-2.5" />
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Actions lu/supprimer */}
                    <div
                      className="flex shrink-0 flex-col gap-0.5 opacity-0 transition-opacity group-hover:opacity-100"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <button
                        onClick={() => toggleRead(n.id)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-foreground/8 hover:text-foreground"
                        title={n.read ? "Marquer non lue" : "Marquer lue"}
                      >
                        {n.read
                          ? <Mail className="h-3 w-3" />
                          : <MailOpen className="h-3 w-3" />}
                      </button>
                      <button
                        onClick={() => remove(n.id)}
                        className="rounded-md p-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                        title="Supprimer"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>}

        {/* ── Pied de page ── */}
        <div className="shrink-0 border-t border-border/40 px-5 py-3">
          <Link
            to="/app/notifications"
            onClick={onClose}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary/8 py-2.5 text-sm font-medium text-primary transition-colors hover:bg-primary/14"
          >
            <Bell className="h-4 w-4" />
            Voir toutes les notifications
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
