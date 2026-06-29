import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useUser } from "@/lib/session";
import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  fetchQueue,
  assignRequest,
  reopenRequest,
  rejectTicket,
  reassignService,
} from "@/lib/api/requests";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchUnits } from "@/lib/api/directions-units";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import {
  ClipboardList, UserPlus, RotateCcw, XCircle,
  ArrowRightLeft, Clock, Loader2, Inbox,
  CheckCircle2, AlertTriangle,
} from "lucide-react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { AsyncSwap } from "@/components/async-states";
import type { RequestItem } from "@/lib/mock-data";

export const Route = createFileRoute("/app/chief-inbox")({
  beforeLoad: () => requireRole("chief", "admin"),
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

type ModalType = "assign" | "reassign" | "reject" | "reopen" | null;
interface ModalState { type: ModalType; ticket: RequestItem | null }

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

function TicketRow({
  r,
  onAssign,
  onReassign,
  onReject,
  onReopen,
}: {
  r: RequestItem;
  onAssign: () => void;
  onReassign: () => void;
  onReject: () => void;
  onReopen?: () => void;
}) {
  const slaOver = r.slaElapsed > r.slaHours;
  const slaLeft = Math.max(0, r.slaHours - r.slaElapsed);
  const showReopen = r.infos?.reopen_requested === true;

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      className={cn(
        "flex flex-col gap-3 border-b px-5 py-4 last:border-0 transition-colors hover:bg-background/50 sm:flex-row sm:items-start",
        r.priority === "critical" ? "border-destructive/30 bg-destructive/3" :
        showReopen               ? "border-amber-500/30 bg-amber-500/3"    :
        r.status === "escalated" ? "border-orange-400/30 bg-orange-500/3" :
        "border-border/30",
      )}
    >
      {/* Infos principales */}
      <div className="min-w-0 flex-1 space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to="/app/requests/$id"
            params={{ id: r.id }}
            className="font-mono text-[11px] text-primary hover:underline"
          >
            {r.ref}
          </Link>
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
        <Link
          to="/app/requests/$id"
          params={{ id: r.id }}
          className="block font-semibold leading-snug hover:text-primary"
        >
          {r.title}
        </Link>
        <div className="text-xs text-muted-foreground">
          {r.requesterName} · {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
        </div>
      </div>

      {/* Actions */}
      <div className="flex shrink-0 flex-col items-end gap-2">
        <div className={cn("flex items-center gap-1 text-xs font-medium", slaOver ? "text-destructive" : "text-muted-foreground")}>
          <Clock className="h-3.5 w-3.5" />
          {slaOver ? "SLA dépassé" : `${slaLeft}h restantes`}
        </div>
        <div className="flex flex-wrap justify-end gap-1.5">
          {showReopen && onReopen && (
            <Button size="sm" className="h-7 rounded-full px-3 text-xs gradient-primary" onClick={onReopen}>
              <CheckCircle2 className="mr-1 h-3 w-3" /> Approuver
            </Button>
          )}
          {!showReopen && (
            <Button size="sm" className="h-7 rounded-full px-3 text-xs gradient-primary" onClick={onAssign}>
              <UserPlus className="mr-1 h-3 w-3" /> Affecter
            </Button>
          )}
          <Button size="sm" variant="outline" className="h-7 rounded-full px-3 text-xs" onClick={onReassign}>
            <ArrowRightLeft className="mr-1 h-3 w-3" /> Réaffecter
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="h-7 rounded-full px-3 text-xs text-destructive border-destructive/40 hover:bg-destructive/10"
            onClick={onReject}
          >
            <XCircle className="mr-1 h-3 w-3" /> Rejeter
          </Button>
        </div>
      </div>
    </motion.div>
  );
}

// ── Composant principal ────────────────────────────────────────────────────────

function ChiefInbox() {
  const sessionUser = useUser();
  const queryClient = useQueryClient();

  const [activeTab, setActiveTab] = useState<Tab>("assign");
  const [modal, setModal] = useState<ModalState>({ type: null, ticket: null });

  // ── Données service ──────────────────────────────────────────────────────────
  const { data: queueData, isLoading, isError } = useQuery({
    queryKey: ["chief-inbox", sessionUser?.id, sessionUser?.unit_id],
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

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading" : isError || displayed.length === 0 ? "empty" : "ready";

  // ── Agents du service (pour M1) ──────────────────────────────────────────────
  const { data: agentsData } = useQuery({
    queryKey: ["service-agents", sessionUser?.direction_id],
    queryFn: () => fetchUsers({ role: "agent", direction_id: sessionUser!.direction_id!, limit: 100 }),
    staleTime: 120_000,
    enabled: !!sessionUser?.direction_id,
  });
  const serviceAgents = agentsData?.items ?? [];

  // ── Unités (pour M2) ─────────────────────────────────────────────────────────
  const { data: unitsData } = useQuery({
    queryKey: ["units-all"],
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });
  const allUnits = (unitsData ?? []).filter((u) => u.status && u.id !== sessionUser?.unit_id);

  // ── États formulaires modals ──────────────────────────────────────────────────
  const [assignAgentId, setAssignAgentId]   = useState("");
  const [reassignUnitId, setReassignUnitId] = useState("");
  const [reassignReason, setReassignReason] = useState("");
  const [rejectReason, setRejectReason]     = useState("");

  const closeModal = () => {
    setModal({ type: null, ticket: null });
    setAssignAgentId("");
    setReassignUnitId("");
    setReassignReason("");
    setRejectReason("");
  };

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["chief-inbox"] });
    queryClient.invalidateQueries({ queryKey: ["queue"] });
    queryClient.invalidateQueries({ queryKey: ["requests"] });
    queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
    queryClient.invalidateQueries({ queryKey: ["my-tickets-stats"] });
    queryClient.invalidateQueries({ queryKey: ["escalations"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };

  // ── M1 — Affecter ─────────────────────────────────────────────────────────────
  const assignMut = useMutation({
    mutationFn: () => assignRequest(modal.ticket!.id, assignAgentId, sessionUser?.id),
    onSuccess: () => { toast.success("Ticket affecté"); invalidate(); closeModal(); },
    onError: () => toast.error("Erreur lors de l'affectation"),
  });

  // ── M2 — Réaffecter service ───────────────────────────────────────────────────
  const reassignMut = useMutation({
    mutationFn: () => reassignService(modal.ticket!.id, reassignUnitId, reassignReason || undefined),
    onSuccess: () => { toast.success("Ticket réaffecté au nouveau service"); invalidate(); closeModal(); },
    onError: () => toast.error("Erreur lors de la réaffectation"),
  });

  // ── M3 — Rejeter ──────────────────────────────────────────────────────────────
  const rejectMut = useMutation({
    mutationFn: () => rejectTicket(modal.ticket!.id, rejectReason),
    onSuccess: () => { toast.success("Ticket rejeté"); invalidate(); closeModal(); },
    onError: () => toast.error("Erreur lors du rejet"),
  });

  // ── M4 — Approuver réouverture ────────────────────────────────────────────────
  const reopenMut = useMutation({
    mutationFn: () => reopenRequest(modal.ticket!.id, undefined, sessionUser?.id),
    onSuccess: () => { toast.success("Réouverture approuvée"); invalidate(); closeModal(); },
    onError: () => toast.error("Erreur lors de l'approbation"),
  });

  const openModal = (type: ModalType, ticket: RequestItem) =>
    setModal({ type, ticket });

  const emptyMessages: Record<Tab, string> = {
    assign:   "Aucun ticket en attente d'affectation.",
    reopen:   "Aucune demande de réouverture en attente.",
    escalated:"Aucune escalade reçue pour votre service.",
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
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Boîte de traitement</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Tickets de votre service nécessitant une action de votre part.
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

      {/* ── Liste ────────────────────────────────────────────────────────────── */}
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
        <GlassCard className="overflow-hidden p-0">
          <AnimatePresence mode="popLayout" initial={false}>
            {displayed.map((r) => (
              <TicketRow
                key={r.id}
                r={r}
                onAssign={()   => openModal("assign",   r)}
                onReassign={()  => openModal("reassign", r)}
                onReject={()   => openModal("reject",   r)}
                onReopen={r.infos?.reopen_requested ? () => openModal("reopen", r) : undefined}
              />
            ))}
          </AnimatePresence>
        </GlassCard>
      </AsyncSwap>

      {/* ── M1 — Affecter à un agent ─────────────────────────────────────────── */}
      <Dialog open={modal.type === "assign"} onOpenChange={(o) => !o && closeModal()}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <UserPlus className="h-4 w-4 text-primary" /> Affecter le ticket
            </DialogTitle>
            <DialogDescription>
              Sélectionnez un agent de votre service pour ce ticket.
            </DialogDescription>
          </DialogHeader>
          {modal.ticket && (
            <div className="rounded-xl bg-muted/40 px-4 py-3 text-sm">
              <p className="font-semibold line-clamp-1">{modal.ticket.title}</p>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">{modal.ticket.ref}</p>
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Agent <span className="text-destructive">*</span></Label>
            <Select value={assignAgentId} onValueChange={setAssignAgentId}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder={serviceAgents.length === 0 ? "Aucun agent disponible" : "Choisir un agent"} />
              </SelectTrigger>
              <SelectContent>
                {serviceAgents.map((a) => (
                  <SelectItem key={a.id} value={a.id}>
                    <span className="font-medium">{a.name}</span>
                    {a.job && <span className="ml-1 text-muted-foreground">— {a.job}</span>}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={closeModal}>Annuler</Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={!assignAgentId || assignMut.isPending}
              onClick={() => assignMut.mutate()}
            >
              {assignMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── M2 — Réaffecter à un autre service ───────────────────────────────── */}
      <Dialog open={modal.type === "reassign"} onOpenChange={(o) => !o && closeModal()}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <ArrowRightLeft className="h-4 w-4 text-primary" /> Réaffecter à un autre service
            </DialogTitle>
            <DialogDescription>
              Ce ticket sera transféré au chef du service cible.
            </DialogDescription>
          </DialogHeader>
          {modal.ticket && (
            <div className="rounded-xl bg-muted/40 px-4 py-3 text-sm">
              <p className="font-semibold line-clamp-1">{modal.ticket.title}</p>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">{modal.ticket.ref}</p>
            </div>
          )}
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label>Service cible <span className="text-destructive">*</span></Label>
              <Select value={reassignUnitId} onValueChange={setReassignUnitId}>
                <SelectTrigger className="h-11">
                  <SelectValue placeholder="Choisir un service" />
                </SelectTrigger>
                <SelectContent>
                  {allUnits.map((u) => (
                    <SelectItem key={u.id} value={u.id}>{u.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Motif</Label>
              <Textarea
                className="resize-none"
                rows={3}
                placeholder="Expliquer pourquoi ce ticket est réaffecté…"
                value={reassignReason}
                onChange={(e) => setReassignReason(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={closeModal}>Annuler</Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={!reassignUnitId || reassignMut.isPending}
              onClick={() => reassignMut.mutate()}
            >
              {reassignMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Réaffecter
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── M3 — Rejeter ─────────────────────────────────────────────────────── */}
      <Dialog open={modal.type === "reject"} onOpenChange={(o) => !o && closeModal()}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <XCircle className="h-4 w-4" /> Rejeter le ticket
            </DialogTitle>
            <DialogDescription>
              Le demandeur sera notifié avec le motif de rejet.
            </DialogDescription>
          </DialogHeader>
          {modal.ticket && (
            <div className="rounded-xl bg-muted/40 px-4 py-3 text-sm">
              <p className="font-semibold line-clamp-1">{modal.ticket.title}</p>
              <p className="mt-0.5 font-mono text-xs text-muted-foreground">{modal.ticket.ref}</p>
            </div>
          )}
          <div className="space-y-1.5">
            <Label>Motif de rejet <span className="text-destructive">*</span></Label>
            <Textarea
              className="resize-none"
              rows={4}
              placeholder="Expliquer la raison du rejet pour informer le demandeur…"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={closeModal}>Annuler</Button>
            <Button
              variant="destructive"
              className="rounded-full"
              disabled={!rejectReason.trim() || rejectMut.isPending}
              onClick={() => rejectMut.mutate()}
            >
              {rejectMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Rejeter le ticket
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── M4 — Approuver réouverture ───────────────────────────────────────── */}
      <AlertDialog open={modal.type === "reopen"} onOpenChange={(o) => !o && closeModal()}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <RotateCcw className="h-4 w-4 text-amber-500" /> Approuver la réouverture
            </AlertDialogTitle>
            <AlertDialogDescription>
              {modal.ticket && (
                <>
                  Le ticket <strong>{modal.ticket.ref}</strong> sera réouvert et réaffecté pour traitement.
                  Le demandeur sera notifié.
                </>
              )}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={closeModal}>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="gradient-primary"
              disabled={reopenMut.isPending}
              onClick={() => reopenMut.mutate()}
            >
              {reopenMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Approuver
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
