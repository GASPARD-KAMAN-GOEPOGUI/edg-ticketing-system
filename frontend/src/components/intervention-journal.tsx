import { useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  User,
  Clock,
  MessageCircle,
  Paperclip,
  Send,
  CheckCircle2,
  RotateCcw,
  Layers,
  Users,
  Timer,
  AlertTriangle,
  Eye,
} from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn, initialsFor } from "@/lib/utils";
import type { Intervention, TimelineEvent } from "@/lib/mock-data";
import {
  formatInterventionDateTime,
  formatInterventionDuration,
  interventionRoleLabel,
  interventionStatus,
  INTERVENTION_STATUS_LABEL,
  type InterventionStatus,
} from "@/lib/intervention-utils";
import { InterventionFilters, type InterventionFilterState, DEFAULT_INTERVENTION_FILTERS } from "@/components/intervention-filters";
import { InterventionDetailsModal } from "@/components/intervention-details-modal";
import { InterventionDetailBody } from "@/components/intervention-detail-body";

// ── En-tête résumé compact ──────────────────────────────────────────────────

function InterventionSummary({ interventions }: { interventions: Intervention[] }) {
  const stats = useMemo(() => {
    const cycles = new Set(interventions.map((iv) => iv.cycleNumber));
    const agents = new Set(interventions.map((iv) => iv.actorId).filter(Boolean));
    const totalSeconds = interventions.reduce((sum, iv) => sum + (iv.durationSeconds ?? 0), 0);
    const transmissions = interventions.filter((iv) => iv.decision === "transmission").length;
    const breached = interventions.filter((iv) => iv.slaBreached === true).length;
    return {
      cycles: cycles.size,
      total: interventions.length,
      agents: agents.size,
      duration: totalSeconds,
      transmissions,
      breached,
    };
  }, [interventions]);

  const items: { icon: typeof Layers; label: string; tone?: string }[] = [
    { icon: Layers, label: `${stats.cycles} cycle${stats.cycles > 1 ? "s" : ""}` },
    { icon: CheckCircle2, label: `${stats.total} intervention${stats.total > 1 ? "s" : ""}` },
    { icon: Users, label: `${stats.agents} intervenant${stats.agents > 1 ? "s" : ""}` },
    { icon: Timer, label: `${formatInterventionDuration(stats.duration)} de traitement` },
    { icon: Send, label: `${stats.transmissions} transmission${stats.transmissions > 1 ? "s" : ""}` },
  ];
  if (stats.breached > 0) {
    items.push({ icon: AlertTriangle, label: `${stats.breached} SLA dépassé${stats.breached > 1 ? "s" : ""}`, tone: "destructive" });
  }

  return (
    <div className="mb-4 flex flex-wrap items-center gap-1.5" role="list" aria-label="Résumé du journal d'intervention">
      {items.map((item, i) => (
        <span
          key={i}
          role="listitem"
          className={cn(
            "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
            item.tone === "destructive"
              ? "border-destructive/30 bg-destructive/5 text-destructive"
              : "border-border/50 bg-background/60 text-foreground",
          )}
        >
          <item.icon className="h-3.5 w-3.5 shrink-0" />
          {item.label}
        </span>
      ))}
    </div>
  );
}

// ── Journal ──────────────────────────────────────────────────────────────────

export function InterventionJournal({
  interventions,
  events,
  currentAssigneeId,
  requestRef,
  onOpenAttachment,
}: {
  interventions: Intervention[];
  events: TimelineEvent[];
  currentAssigneeId?: string;
  requestRef?: string;
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
}) {
  const [filters, setFilters] = useState<InterventionFilterState>(DEFAULT_INTERVENTION_FILTERS);
  const [modalIntervention, setModalIntervention] = useState<Intervention | null>(null);

  // event.id peut être renvoyé par l'API comme nombre alors que iv.eventIds
  // contient des chaînes (coercion Pydantic v1) — normaliser en string des
  // deux côtés pour que la correspondance Map fonctionne dans tous les cas.
  const eventsById = useMemo(() => new Map(events.map((e) => [String(e.id), e])), [events]);

  const eventsByIntervention = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const iv of interventions) {
      map.set(
        iv.interventionId,
        iv.eventIds.map((id) => eventsById.get(String(id))).filter((e): e is TimelineEvent => !!e),
      );
    }
    return map;
  }, [interventions, eventsById]);

  const filtered = useMemo(
    () => filterInterventions(interventions, eventsByIntervention, filters),
    [interventions, eventsByIntervention, filters],
  );

  const cycles = useMemo(() => {
    const map = new Map<number, Intervention[]>();
    for (const iv of filtered) {
      const list = map.get(iv.cycleNumber) ?? [];
      list.push(iv);
      map.set(iv.cycleNumber, list);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [filtered]);

  const lastClosedCycle = useMemo(() => {
    const closed = cycles.filter(([, ivs]) => ivs.every((iv) => interventionStatus(iv) !== "ongoing"));
    return closed.length > 0 ? closed[closed.length - 1][0] : undefined;
  }, [cycles]);
  const activeCycle = useMemo(() => {
    const ongoing = cycles.find(([, ivs]) => ivs.some((iv) => interventionStatus(iv) === "ongoing"));
    return ongoing?.[0];
  }, [cycles]);

  if (interventions.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-background/30 px-4 py-6 text-sm text-muted-foreground">
        Aucune intervention enregistrée pour le moment.
      </div>
    );
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <InterventionSummary interventions={interventions} />
        <InterventionFilters
          interventions={interventions}
          filters={filters}
          onChange={setFilters}
        />
      </div>

      {cycles.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-border/60 bg-background/30 px-4 py-6 text-sm text-muted-foreground">
          Aucune intervention ne correspond aux filtres sélectionnés.
        </div>
      ) : (
        <div className="space-y-4">
          {cycles.map(([cycleNumber, ivs], idx) => (
            <CycleSection
              key={cycleNumber}
              cycleNumber={cycleNumber}
              interventions={ivs}
              eventsByIntervention={eventsByIntervention}
              events={events}
              isFirst={idx === 0}
              defaultOpen={cycleNumber === activeCycle || cycleNumber === lastClosedCycle}
              currentAssigneeId={currentAssigneeId}
              onOpenAttachment={onOpenAttachment}
              onConsult={setModalIntervention}
            />
          ))}
        </div>
      )}

      <InterventionDetailsModal
        intervention={modalIntervention}
        events={modalIntervention ? (eventsByIntervention.get(modalIntervention.interventionId) ?? []) : []}
        requestRef={requestRef}
        onOpenChange={(open) => !open && setModalIntervention(null)}
        onOpenAttachment={onOpenAttachment}
      />
    </div>
  );
}

function filterInterventions(
  interventions: Intervention[],
  eventsByIntervention: Map<string, TimelineEvent[]>,
  filters: InterventionFilterState,
): Intervention[] {
  const search = filters.search.trim().toLowerCase();
  return interventions.filter((iv) => {
    if (filters.cycle !== "all" && iv.cycleNumber !== filters.cycle) return false;
    if (filters.actorId !== "all" && iv.actorId !== filters.actorId) return false;
    if (filters.service !== "all" && iv.actorServiceLabel !== filters.service) return false;
    if (filters.decision !== "all" && interventionStatus(iv) !== filters.decision) return false;
    if (filters.withAttachments && iv.attachmentCount === 0) return false;
    if (filters.slaBreached && iv.slaBreached !== true) return false;
    if (search) {
      const haystack = [
        iv.actorName, iv.actorMatricule, iv.workDone, iv.transmissionReason,
        iv.instruction, iv.solution, iv.summary,
      ].filter(Boolean).join(" ").toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

// ── Section de cycle ─────────────────────────────────────────────────────────

function CycleSection({
  cycleNumber,
  interventions,
  eventsByIntervention,
  events,
  isFirst,
  defaultOpen,
  currentAssigneeId,
  onOpenAttachment,
  onConsult,
}: {
  cycleNumber: number;
  interventions: Intervention[];
  eventsByIntervention: Map<string, TimelineEvent[]>;
  events: TimelineEvent[];
  isFirst: boolean;
  defaultOpen: boolean;
  currentAssigneeId?: string;
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
  onConsult: (iv: Intervention) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = `cycle-panel-${cycleNumber}`;

  const displayOrder = useMemo(() => [...interventions].reverse(), [interventions]);

  const last = interventions[interventions.length - 1];
  const status = interventionStatus(last);
  const first = interventions[0];
  const cycleStart = first?.startedAt;
  const cycleEnd = status !== "ongoing" ? last?.endedAt : undefined;
  const slaBreachedInCycle = interventions.some((iv) => iv.slaBreached === true);
  const slaEvaluated = interventions.some((iv) => iv.slaBreached != null);

  const reopenEvent = events.find(
    (e) => e.type === "reopened" && Number(e.infos?.intervention_cycle_number) === cycleNumber,
  );

  return (
    <div>
      {!isFirst && <ReopenSeparator event={reopenEvent} />}
      <div className="overflow-hidden rounded-2xl border border-border/50 bg-background/40">
        <button
          type="button"
          className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left transition-colors hover:bg-foreground/3 sm:px-4"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={panelId}
        >
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-sm font-semibold">Cycle {cycleNumber}</span>
            <span className="text-xs text-muted-foreground">
              {cycleNumber === 1 ? "Traitement initial" : "Après réouverture"}
            </span>
            <StatusPill status={status} />
            {slaEvaluated && (
              <span className={cn("text-xs font-medium", slaBreachedInCycle ? "text-destructive" : "text-success")}>
                {slaBreachedInCycle ? "SLA dépassé" : "SLA respecté"}
              </span>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-3">
            <span className="hidden text-xs text-muted-foreground sm:inline">
              {formatInterventionDateTime(cycleStart)} → {cycleEnd ? formatInterventionDateTime(cycleEnd) : "en cours"}
            </span>
            <span className="text-xs text-muted-foreground">
              {interventions.length} intervention{interventions.length > 1 ? "s" : ""}
            </span>
            {open ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
          </div>
        </button>

        {open && (
          <div id={panelId} className="space-y-2.5 border-t border-border/40 p-2.5 sm:p-3">
            {/* Affichage décroissant : intervenant actuel (le plus récent) en premier,
                jusqu'au plus ancien en dernier. Les calculs de cycle (cycleStart/cycleEnd)
                restent basés sur l'ordre chronologique réel via `interventions`. */}
            {displayOrder.map((iv, i) => (
              <div key={iv.interventionId}>
                <InterventionCard
                  intervention={iv}
                  events={eventsByIntervention.get(iv.interventionId) ?? []}
                  isCurrent={!!currentAssigneeId && iv.actorId === currentAssigneeId && interventionStatus(iv) === "ongoing"}
                  onOpenAttachment={onOpenAttachment}
                  onConsult={() => onConsult(iv)}
                />
                {i < displayOrder.length - 1 && <TransferLink intervention={displayOrder[i + 1]} direction="from" />}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function StatusPill({ status }: { status: InterventionStatus }) {
  const styles: Record<InterventionStatus, string> = {
    ongoing: "bg-amber-500/15 text-amber-600",
    transmitted: "bg-sky-500/15 text-sky-600",
    resolved: "bg-success/15 text-success",
  };
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider", styles[status])}>
      {INTERVENTION_STATUS_LABEL[status]}
    </span>
  );
}

function ReopenSeparator({ event }: { event?: TimelineEvent }) {
  const reason = event?.comment;
  const requestedBy = typeof event?.infos?.reopen_requested_by_name === "string" ? event.infos.reopen_requested_by_name : undefined;
  return (
    <div
      className="mb-3 flex items-start gap-2.5 rounded-xl border border-fuchsia-200 bg-fuchsia-50 px-4 py-2.5 text-sm dark:border-fuchsia-800/50 dark:bg-fuchsia-950/30"
      role="separator"
    >
      <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-fuchsia-600 dark:text-fuchsia-400" />
      <div className="min-w-0 text-fuchsia-800 dark:text-fuchsia-300">
        <p className="font-medium">Ticket réouvert</p>
        {reason && <p className="mt-0.5">Motif : {reason}</p>}
        <p className="mt-0.5 text-xs opacity-80">
          {requestedBy && <>Demandée par {requestedBy} · </>}
          {event?.by && <>Approuvée par {event.by} · </>}
          {event?.at && formatInterventionDateTime(event.at)}
        </p>
        <p className="mt-0.5 text-xs opacity-80">Retour dans la File d'attente — nouveau cycle ouvert.</p>
      </div>
    </div>
  );
}

function TransferLink({ intervention, direction = "to" }: { intervention: Intervention; direction?: "to" | "from" }) {
  if (intervention.decision !== "transmission") return null;
  return (
    <div className="flex items-center gap-2 py-1.5 pl-4 text-xs text-muted-foreground">
      <div className="h-4 w-px bg-border" />
      <Send className="h-3 w-3 shrink-0" />
      {direction === "from" ? (
        <span>
          Reçu de <span className="font-medium text-foreground">{intervention.actorName ?? "—"}</span>
          {intervention.transmissionReason && <span> · {intervention.transmissionReason}</span>}
        </span>
      ) : (
        <span>
          Transmis à <span className="font-medium text-foreground">{intervention.destinationName ?? "—"}</span>
          {intervention.transmissionReason && <span> · {intervention.transmissionReason}</span>}
        </span>
      )}
    </div>
  );
}

// ── Carte d'intervention ─────────────────────────────────────────────────────

function InterventionCard({
  intervention,
  events,
  isCurrent,
  onOpenAttachment,
  onConsult,
}: {
  intervention: Intervention;
  events: TimelineEvent[];
  isCurrent: boolean;
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
  onConsult: () => void;
}) {
  const [open, setOpen] = useState(false);
  const iv = intervention;
  const panelId = `intervention-panel-${iv.interventionId}`;
  const status = interventionStatus(iv);

  return (
    <div
      className={cn(
        "overflow-hidden rounded-2xl border bg-background/55",
        isCurrent ? "border-primary/50 ring-1 ring-primary/20" : "border-border/50",
      )}
    >
      <div className="flex items-start gap-3 p-3 sm:p-3.5">
        <button
          type="button"
          className="flex min-w-0 flex-1 items-start gap-3 text-left"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-controls={panelId}
        >
          <Avatar className="h-9 w-9 shrink-0">
            <AvatarFallback className="bg-primary/10 text-xs font-semibold text-primary">
              {iv.actorName ? initialsFor(iv.actorName) : <User className="h-4 w-4" />}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="font-semibold">{iv.actorName ?? "Intervenant"}</span>
              {iv.interventionOrder != null && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                  Intervention {iv.interventionOrder}
                </span>
              )}
              {isCurrent && (
                <span className="rounded-full bg-primary px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary-foreground">
                  Intervenant actuel
                </span>
              )}
              <StatusPill status={status} />
            </div>
            <p className="mt-0.5 truncate text-xs text-muted-foreground">
              {interventionRoleLabel(iv.actorRole) ?? "—"}
              {iv.actorServiceLabel && <> · {iv.actorServiceLabel}</>}
            </p>
            {!open && (
              <p className="mt-1 truncate text-sm text-foreground/90">
                {iv.workDone ?? (status === "ongoing" ? "Intervention en cours…" : "—")}
              </p>
            )}
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
              <span className="flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {formatInterventionDuration(iv.durationSeconds)}
              </span>
              {iv.commentCount > 0 && (
                <span className="flex items-center gap-1"><MessageCircle className="h-3 w-3" /> {iv.commentCount}</span>
              )}
              {iv.attachmentCount > 0 && (
                <span className="flex items-center gap-1"><Paperclip className="h-3 w-3" /> {iv.attachmentCount}</span>
              )}
              {!open && iv.decision === "transmission" && (
                <span className="flex items-center gap-1 text-sky-600">
                  <Send className="h-3 w-3" /> Vers {iv.destinationName ?? "—"}
                </span>
              )}
            </div>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
            onClick={onConsult}
            aria-label={`Consulter la fiche complète de l'intervention ${iv.interventionOrder ?? ""}`}
            title="Consulter la fiche complète"
          >
            <Eye className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={open ? "Replier l'intervention" : "Déplier l'intervention"}
          >
            {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {open && (
        <div id={panelId} className="border-t border-border/40 px-3 pb-3 pt-3 sm:px-3.5 sm:pb-3.5">
          <InterventionDetailBody intervention={iv} events={events} onOpenAttachment={onOpenAttachment} />
        </div>
      )}
    </div>
  );
}
