import { useState } from "react";
import { formatDistanceToNow, differenceInHours, format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  PlusCircle,
  Navigation,
  Headphones,
  SlidersHorizontal,
  CheckSquare,
  UserCheck,
  ArrowRightLeft,
  Play,
  PauseCircle,
  CheckCircle2,
  RotateCcw,
  XCircle,
  Lock,
  Ban,
  ArrowUpRight,
  MessageCircle,
  Paperclip,
  Trash2,
  GitBranch,
  Circle,
  Send,
  type LucideIcon,
} from "lucide-react";

type TimelineEvent = {
  id: string;
  type: string;
  label: string;
  at: string;
  by?: string;
  actorRole?: string;
  targetUserName?: string;
  targetRole?: string;
  oldStatus?: string;
  newStatus?: string;
  comment?: string;
  isPublic?: boolean;
  infos?: Record<string, unknown>;
};

type EventConfig = {
  icon: LucideIcon;
  color: string;
  bg: string;
  ring: string;
};

const EVENT_CONFIG: Record<string, EventConfig> = {
  created:            { icon: PlusCircle,        color: "text-primary",           bg: "bg-primary/15",          ring: "ring-primary/25" },
  routed_to_service:  { icon: Navigation,         color: "text-violet-500",        bg: "bg-violet-500/15",       ring: "ring-violet-500/25" },
  routed_to_support:  { icon: Headphones,          color: "text-orange-500",        bg: "bg-orange-500/15",       ring: "ring-orange-500/25" },
  qualifying:         { icon: SlidersHorizontal,   color: "text-sky-500",           bg: "bg-sky-500/15",          ring: "ring-sky-500/25" },
  qualified:          { icon: CheckSquare,         color: "text-teal-500",          bg: "bg-teal-500/15",         ring: "ring-teal-500/25" },
  assigned:           { icon: UserCheck,           color: "text-blue-500",          bg: "bg-blue-500/15",         ring: "ring-blue-500/25" },
  reassigned_service: { icon: ArrowRightLeft,      color: "text-indigo-500",        bg: "bg-indigo-500/15",       ring: "ring-indigo-500/25" },
  transferred_direction: { icon: ArrowRightLeft,   color: "text-violet-600",        bg: "bg-violet-600/15",       ring: "ring-violet-600/25" },
  in_progress:        { icon: Play,                color: "text-emerald-500",       bg: "bg-emerald-500/15",      ring: "ring-emerald-500/25" },
  pending:            { icon: PauseCircle,         color: "text-amber-500",         bg: "bg-amber-500/15",        ring: "ring-amber-500/25" },
  resolved:           { icon: CheckCircle2,        color: "text-emerald-600",       bg: "bg-emerald-600/15",      ring: "ring-emerald-600/25" },
  reopen_requested:   { icon: RotateCcw,           color: "text-amber-500",         bg: "bg-amber-500/15",        ring: "ring-amber-500/25" },
  reopened:           { icon: RotateCcw,           color: "text-primary",           bg: "bg-primary/15",          ring: "ring-primary/25" },
  reopen_rejected:    { icon: XCircle,             color: "text-destructive",       bg: "bg-destructive/15",      ring: "ring-destructive/25" },
  rejected:           { icon: XCircle,             color: "text-destructive",       bg: "bg-destructive/15",      ring: "ring-destructive/25" },
  closed:             { icon: Lock,                color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  cancelled:          { icon: Ban,                 color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  escalation_manual:  { icon: ArrowUpRight,        color: "text-orange-600",        bg: "bg-orange-600/15",       ring: "ring-orange-600/25" },
  escalated:          { icon: ArrowUpRight,        color: "text-orange-600",        bg: "bg-orange-600/15",       ring: "ring-orange-600/25" },
  comment:            { icon: MessageCircle,       color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  comment_added:      { icon: MessageCircle,       color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  priority_changed:   { icon: SlidersHorizontal,   color: "text-amber-600",         bg: "bg-amber-600/15",        ring: "ring-amber-600/25" },
  request_updated:    { icon: SlidersHorizontal,   color: "text-sky-500",           bg: "bg-sky-500/15",          ring: "ring-sky-500/25" },
  requester_edit:     { icon: SlidersHorizontal,   color: "text-sky-500",           bg: "bg-sky-500/15",          ring: "ring-sky-500/25" },
  attachment_added:   { icon: Paperclip,           color: "text-cyan-600",          bg: "bg-cyan-600/15",         ring: "ring-cyan-600/25" },
  attachment_deleted: { icon: Trash2,              color: "text-destructive",       bg: "bg-destructive/15",      ring: "ring-destructive/25" },
  workflow_started:   { icon: GitBranch,           color: "text-indigo-600",        bg: "bg-indigo-600/15",       ring: "ring-indigo-600/25" },
  workflow_step_accepted: { icon: CheckCircle2,    color: "text-emerald-600",       bg: "bg-emerald-600/15",      ring: "ring-emerald-600/25" },
  workflow_step_rejected: { icon: XCircle,         color: "text-destructive",       bg: "bg-destructive/15",      ring: "ring-destructive/25" },
  workflow_completed: { icon: CheckCircle2,        color: "text-emerald-600",       bg: "bg-emerald-600/15",      ring: "ring-emerald-600/25" },
  workflow_suspended: { icon: PauseCircle,         color: "text-amber-600",         bg: "bg-amber-600/15",        ring: "ring-amber-600/25" },
  // BR-TRANSMIT-001 — workflow collaboratif dynamique post-file d'attente.
  treatment_transmitted: { icon: Send,             color: "text-sky-600",           bg: "bg-sky-600/15",          ring: "ring-sky-600/25" },
  treatment_completed:   { icon: CheckCircle2,     color: "text-emerald-600",       bg: "bg-emerald-600/15",      ring: "ring-emerald-600/25" },
};

const DEFAULT_CONFIG: EventConfig = {
  icon: Circle,
  color: "text-muted-foreground",
  bg: "bg-muted",
  ring: "ring-border",
};

function formatEventDate(isoDate: string): string {
  const date = new Date(isoDate);
  const hoursAgo = differenceInHours(new Date(), date);
  if (hoursAgo < 24) {
    return formatDistanceToNow(date, { addSuffix: true, locale: fr });
  }
  return format(date, "d MMM yyyy 'à' HH:mm", { locale: fr });
}

function infoString(event: TimelineEvent, key: string): string | undefined {
  const value = event.infos?.[key];
  if (value === null || value === undefined || value === "") return undefined;
  if (typeof value === "string" || typeof value === "number") return String(value);
  return undefined;
}

// BR-TRANSMIT-001 — durée du cycle d'intervention clôturé par une transmission ou
// une terminaison de traitement (infos.duration_seconds, calculé côté backend).
function formatCycleDuration(event: TimelineEvent): string | undefined {
  const raw = event.infos?.duration_seconds;
  if (typeof raw !== "number" || raw < 0) return undefined;
  const hours = Math.floor(raw / 3600);
  const minutes = Math.floor((raw % 3600) / 60);
  if (hours === 0 && minutes === 0) return "moins d'une minute";
  const parts: string[] = [];
  if (hours > 0) parts.push(`${hours} h`);
  if (minutes > 0) parts.push(`${minutes} min`);
  return parts.join(" ");
}

function primaryEventLabel(event: TimelineEvent): string {
  let label = event.label;
  const filename = infoString(event, "filename");

  if (event.targetUserName && /\bun agent\b/i.test(label)) {
    label = label.replace(/\bun agent\b/i, event.targetUserName);
  }

  if (filename && !label.includes(filename) && (event.type.includes("attachment") || event.type === "comment_added")) {
    label = `${label} - ${filename}`;
  }

  return label;
}

type WorkflowTimelineProps = {
  events: TimelineEvent[];
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
};

function TimelineItem({
  event,
  isLast,
  onOpenAttachment,
}: {
  event: TimelineEvent;
  isLast: boolean;
  onOpenAttachment?: WorkflowTimelineProps["onOpenAttachment"];
}) {
  const cfg = EVENT_CONFIG[event.type] ?? DEFAULT_CONFIG;
  const Icon = cfg.icon;
  const label = primaryEventLabel(event);
  const reason = !event.comment && event.type !== "comment_added"
    ? infoString(event, "reason")
    : undefined;
  const attachmentId = infoString(event, "attachment_id") ?? infoString(event, "attachmentId");
  const attachmentFilename = infoString(event, "filename");
  // BR-TRANSMIT-001 — cycle d'intervention : travail effectué + durée du cycle clos.
  const isCycleEvent = event.type === "treatment_transmitted" || event.type === "treatment_completed";
  const workDone = isCycleEvent ? infoString(event, "work_done") : undefined;
  const cycleDuration = isCycleEvent ? formatCycleDuration(event) : undefined;
  const isAutoRoutedToSupport = event.type === "routed_to_support";
  const canOpenAttachment = Boolean(
    onOpenAttachment &&
    !event.type.includes("deleted") &&
    (attachmentId || attachmentFilename),
  );
  const openAttachment = () => {
    if (!canOpenAttachment) return;
    onOpenAttachment?.({ id: attachmentId, filename: attachmentFilename });
  };

  return (
    <li className="group flex gap-3">
      <div className="flex w-9 shrink-0 flex-col items-center">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/25 shadow-sm ring-2 transition-transform group-hover:scale-105 ${cfg.bg} ${cfg.ring}`}
        >
          <Icon className={`h-3.5 w-3.5 ${cfg.color}`} />
        </div>
        {!isLast && <div className="mt-1.5 w-px grow bg-gradient-to-b from-border via-border/70 to-border/20" />}
      </div>
      <div className={`min-w-0 flex-1 ${isLast ? "pb-0" : "pb-4"}`}>
        <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-3">
          <div className="min-w-0">
            {canOpenAttachment ? (
              <button
                type="button"
                className={`min-w-0 text-left text-sm font-semibold leading-5 underline-offset-4 transition hover:underline ${cfg.color}`}
                onClick={openAttachment}
              >
                {label}
              </button>
            ) : (
              <p className={`min-w-0 text-sm font-semibold leading-5 ${cfg.color}`}>{label}</p>
            )}
          </div>
          {!isAutoRoutedToSupport && (
            <p className="shrink-0 text-left text-[11px] leading-5 text-muted-foreground sm:text-right">
              {event.by && <span className="font-medium">{event.by}</span>}
              {event.by && <span className="mx-1">·</span>}
              <span>{formatEventDate(event.at)}</span>
            </p>
          )}
        </div>
        {event.comment && (
          <p className="mt-2 rounded-xl border border-border/40 bg-background/45 px-3 py-2 text-sm leading-5 text-foreground">
            {event.comment}
          </p>
        )}
        {reason && (
          <p className="mt-2 rounded-xl border border-border/40 bg-background/45 px-3 py-2 text-sm leading-5 text-foreground">
            <span className="mr-1 font-medium text-muted-foreground">Motif:</span>
            {reason}
          </p>
        )}
        {workDone && (
          <p className="mt-2 rounded-xl border border-border/40 bg-background/45 px-3 py-2 text-sm leading-5 text-foreground">
            <span className="mr-1 font-medium text-muted-foreground">Travail effectué:</span>
            {workDone}
          </p>
        )}
        {cycleDuration && (
          <p className="mt-1.5 text-[11px] leading-5 text-muted-foreground">
            <span className="font-medium">Durée du cycle:</span> {cycleDuration}
          </p>
        )}
      </div>
    </li>
  );
}

export function WorkflowTimeline({ events, onOpenAttachment }: WorkflowTimelineProps) {
  const [showAll, setShowAll] = useState(false);

  if (events.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border/60 bg-background/30 px-4 py-6 text-sm text-muted-foreground">
        Aucun événement enregistré.
      </div>
    );
  }

  const visibleEvents = events.slice(0, 3);

  return (
    <div>
      <ol className="relative space-y-0">
        {visibleEvents.map((event, index) => (
          <TimelineItem
            key={event.id}
            event={event}
            isLast={index === visibleEvents.length - 1}
            onOpenAttachment={onOpenAttachment}
          />
        ))}
      </ol>

      {events.length > 3 && (
        <div className="mt-1 flex justify-center">
          <button
            type="button"
            className="inline-flex items-center gap-2 rounded-xl border border-border/50 bg-background/45 px-4 py-2 text-xs font-medium text-foreground shadow-sm transition hover:bg-background/70"
            onClick={() => setShowAll(true)}
          >
            Voir tout
            <ArrowUpRight className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      <Dialog open={showAll} onOpenChange={setShowAll}>
        <DialogContent className="flex max-h-[80vh] flex-col overflow-hidden sm:max-w-lg">
          <DialogHeader className="shrink-0">
            <DialogTitle>Journaux ({events.length})</DialogTitle>
            <DialogDescription>Historique complet des événements de ce ticket.</DialogDescription>
          </DialogHeader>
          <ol className="relative min-h-0 flex-1 space-y-0 overflow-y-auto pr-1">
            {events.map((event, index) => (
              <TimelineItem
                key={event.id}
                event={event}
                isLast={index === events.length - 1}
                onOpenAttachment={onOpenAttachment}
              />
            ))}
          </ol>
        </DialogContent>
      </Dialog>
    </div>
  );
}
