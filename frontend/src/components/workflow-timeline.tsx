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
  Circle,
  type LucideIcon,
} from "lucide-react";

type TimelineEvent = {
  id: string;
  type: string;
  label: string;
  at: string;
  by?: string;
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
  in_progress:        { icon: Play,                color: "text-emerald-500",       bg: "bg-emerald-500/15",      ring: "ring-emerald-500/25" },
  pending:            { icon: PauseCircle,         color: "text-amber-500",         bg: "bg-amber-500/15",        ring: "ring-amber-500/25" },
  resolved:           { icon: CheckCircle2,        color: "text-emerald-600",       bg: "bg-emerald-600/15",      ring: "ring-emerald-600/25" },
  reopen_requested:   { icon: RotateCcw,           color: "text-amber-500",         bg: "bg-amber-500/15",        ring: "ring-amber-500/25" },
  reopened:           { icon: RotateCcw,           color: "text-primary",           bg: "bg-primary/15",          ring: "ring-primary/25" },
  rejected:           { icon: XCircle,             color: "text-destructive",       bg: "bg-destructive/15",      ring: "ring-destructive/25" },
  closed:             { icon: Lock,                color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  cancelled:          { icon: Ban,                 color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
  escalation_manual:  { icon: ArrowUpRight,        color: "text-orange-600",        bg: "bg-orange-600/15",       ring: "ring-orange-600/25" },
  escalated:          { icon: ArrowUpRight,        color: "text-orange-600",        bg: "bg-orange-600/15",       ring: "ring-orange-600/25" },
  comment:            { icon: MessageCircle,       color: "text-muted-foreground",  bg: "bg-muted",               ring: "ring-border" },
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

type WorkflowTimelineProps = {
  events: TimelineEvent[];
};

export function WorkflowTimeline({ events }: WorkflowTimelineProps) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Aucun événement enregistré.</p>
    );
  }

  return (
    <ol className="relative space-y-0">
      {events.map((event, index) => {
        const cfg = EVENT_CONFIG[event.type] ?? DEFAULT_CONFIG;
        const Icon = cfg.icon;
        const isLast = index === events.length - 1;

        return (
          <li key={event.id} className="flex gap-4">
            {/* connector column */}
            <div className="flex flex-col items-center">
              <div
                className={`
                  flex h-8 w-8 shrink-0 items-center justify-center rounded-full
                  ring-2 ${cfg.bg} ${cfg.ring}
                `}
              >
                <Icon className={`h-4 w-4 ${cfg.color}`} />
              </div>
              {!isLast && (
                <div className="mt-1 w-px grow bg-border" />
              )}
            </div>

            {/* content */}
            <div className={`pb-6 min-w-0 flex-1 ${isLast ? "pb-0" : ""}`}>
              <p className={`text-sm font-medium leading-8 ${cfg.color}`}>
                {event.label}
              </p>
              <p className="text-xs text-muted-foreground">
                {formatEventDate(event.at)}
                {event.by && (
                  <span className="ml-1 before:content-['·'] before:mr-1">
                    {event.by}
                  </span>
                )}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
