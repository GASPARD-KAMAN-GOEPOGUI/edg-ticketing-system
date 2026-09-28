import { cn } from "@/lib/utils";
import type { RequestStatus, Priority } from "@/lib/mock-data";
import { statusLabels, priorityLabels } from "@/lib/mock-data";

const statusStyles: Record<RequestStatus, string> = {
  // ── Entrée dans le système ────────────────────────────────────────────────
  new:         "bg-sky-100 text-sky-700 border-sky-200 dark:bg-sky-950/50 dark:text-sky-300 dark:border-sky-800/50",
  qualifying:  "bg-blue-100 text-blue-700 border-blue-200 dark:bg-blue-950/50 dark:text-blue-300 dark:border-blue-800/50",
  // ── Traitement actif ──────────────────────────────────────────────────────
  assigned:    "bg-violet-100 text-violet-700 border-violet-200 dark:bg-violet-950/50 dark:text-violet-300 dark:border-violet-800/50",
  in_progress: "bg-amber-100 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-300 dark:border-amber-800/50",
  // ── Pause ─────────────────────────────────────────────────────────────────
  // ── Terminé ───────────────────────────────────────────────────────────────
  resolved:    "bg-emerald-100 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-300 dark:border-emerald-800/50",
  closed:      "bg-slate-100 text-slate-500 border-slate-200 dark:bg-slate-800/50 dark:text-slate-400 dark:border-slate-700/50",
  // ── Exceptions ────────────────────────────────────────────────────────────
  rejected:    "bg-red-100 text-red-700 border-red-200 dark:bg-red-950/50 dark:text-red-300 dark:border-red-800/50",
  reopened:    "bg-fuchsia-100 text-fuchsia-700 border-fuchsia-200 dark:bg-fuchsia-950/50 dark:text-fuchsia-300 dark:border-fuchsia-800/50",
  cancelled:   "bg-zinc-100 text-zinc-500 border-zinc-200 dark:bg-zinc-800/50 dark:text-zinc-400 dark:border-zinc-700/50",
};

const priorityStyles: Record<Priority, string> = {
  low:      "bg-slate-100 text-slate-500 dark:bg-slate-800/50 dark:text-slate-400",
  medium:   "bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
  high:     "bg-orange-100 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300",
  critical: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

export function StatusBadge({ status }: { status: RequestStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium",
        statusStyles[status],
      )}
    >
      <span className="mr-1.5 h-1.5 w-1.5 rounded-full bg-current" />
      {statusLabels[status]}
    </span>
  );
}

export function PriorityBadge({ priority }: { priority: Priority }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium",
        priorityStyles[priority],
      )}
    >
      {priorityLabels[priority]}
    </span>
  );
}
