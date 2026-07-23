import { formatDistanceToNow, differenceInHours, format } from "date-fns";
import { fr } from "date-fns/locale";
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

const ROLE_LABELS: Record<string, string> = {
  user: "Demandeur",
  agent: "Agent",
  chief: "Chef",
  director: "Directeur",
  dg: "Directeur",
  admin: "Admin",
  support: "Support",
};

function roleLabel(role?: string): string | undefined {
  if (!role) return undefined;
  return ROLE_LABELS[role] ?? role;
}

function infoString(event: TimelineEvent, key: string): string | undefined {
  const value = event.infos?.[key];
  if (value === null || value === undefined || value === "") return undefined;
  if (typeof value === "string" || typeof value === "number") return String(value);
  return undefined;
}

function eventDetails(event: TimelineEvent): string[] {
  const details: string[] = [];
  const actorRole = roleLabel(event.actorRole);
  const targetRole = roleLabel(event.targetRole);
  const filename = infoString(event, "filename");
  const targetDirectionName = infoString(event, "target_direction_name");

  if (actorRole) details.push(`Acteur: ${actorRole}`);
  if (targetDirectionName) details.push(`Direction: ${targetDirectionName}`);
  if (event.targetUserName) {
    details.push(`Vers ${event.targetUserName}${targetRole ? ` (${targetRole})` : ""}`);
  } else if (targetRole) {
    details.push(`Vers ${targetRole}`);
  }
  if (event.oldStatus && event.newStatus && event.oldStatus !== event.newStatus) {
    details.push(`${event.oldStatus} -> ${event.newStatus}`);
  } else if (event.newStatus) {
    details.push(event.newStatus);
  }
  if (event.type === "comment_added") {
    details.push(event.isPublic ? "Visible demandeur" : "Interne");
  }
  if (filename && !event.label.includes(filename)) {
    details.push(filename);
  }

  return details;
}

type WorkflowTimelineProps = {
  events: TimelineEvent[];
};

function TimelineItem({
  event,
  isLast,
}: {
  event: TimelineEvent;
  isLast: boolean;
}) {
  const cfg = EVENT_CONFIG[event.type] ?? DEFAULT_CONFIG;
  const Icon = cfg.icon;
  const details = eventDetails(event);
  const reason = !event.comment && event.type !== "comment_added"
    ? infoString(event, "reason")
    : undefined;
  return (
    <li className="flex gap-4">
      <div className="flex flex-col items-center">
        <div
          className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ring-2 ${cfg.bg} ${cfg.ring}`}
        >
          <Icon className={`h-4 w-4 ${cfg.color}`} />
        </div>
        {!isLast && <div className="mt-1 w-px grow bg-border" />}
      </div>
      <div className={`min-w-0 flex-1 ${isLast ? "pb-0" : "pb-6"}`}>
        <p className={`text-sm font-medium leading-8 ${cfg.color}`}>{event.label}</p>
        {event.comment && (
          <p className="mb-1 rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm text-foreground">
            {event.comment}
          </p>
        )}
        {reason && (
          <p className="mb-1 rounded-lg border border-border/40 bg-background/60 px-3 py-2 text-sm text-foreground">
            <span className="mr-1 font-medium text-muted-foreground">Motif:</span>
            {reason}
          </p>
        )}
        {details.length > 0 && (
          <div className="mb-1 flex flex-wrap gap-1.5">
            {details.map((detail) => (
              <span
                key={detail}
                className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground"
              >
                {detail}
              </span>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">
          {formatEventDate(event.at)}
          {event.by && (
            <span className="ml-1 before:mr-1 before:content-['·']">{event.by}</span>
          )}
        </p>
      </div>
    </li>
  );
}

export function WorkflowTimeline({ events }: WorkflowTimelineProps) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Aucun événement enregistré.</p>
    );
  }

  const pinned = events.slice(0, 2);
  const rest = events.slice(2);
  const hasMore = rest.length > 0;

  return (
    <ol className="relative space-y-0">
      {/* Les 2 premiers toujours visibles */}
      {pinned.map((event, index) => {
        const isLastPinned = !hasMore && index === pinned.length - 1;
        return (
          <TimelineItem key={event.id} event={event} isLast={isLastPinned} />
        );
      })}

      {/* Reste scrollable */}
      {hasMore && (
        <li className="flex gap-4">
          {/* Ligne de connexion continue sur toute la hauteur du scroll */}
          <div className="flex w-8 shrink-0 flex-col items-center">
            <div className="w-px flex-1 bg-border" />
          </div>
          <div className="min-w-0 flex-1 pb-0">
            <ol
              className="max-h-52 space-y-0 overflow-y-auto pr-1 [scrollbar-width:thin]"
            >
              {rest.map((event, index) => (
                <TimelineItem
                  key={event.id}
                  event={event}
                  isLast={index === rest.length - 1}
                />
              ))}
            </ol>
          </div>
        </li>
      )}
    </ol>
  );
}
