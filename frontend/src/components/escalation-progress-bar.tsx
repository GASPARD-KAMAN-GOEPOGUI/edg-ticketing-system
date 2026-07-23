import { cn } from "@/lib/utils";
import { Check, X, RotateCcw } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export type EscalationStepStatus =
  | "done"
  | "active"
  | "pending"
  | "rejected"
  | "reopened";

export type EscalationStep = {
  level: string;
  status: EscalationStepStatus;
  date?: string;
  actor?: string;
  comment?: string;
};

export const DEFAULT_LEVELS = [
  "Création",
  "Qualification",
  "Agent",
  "Chef de service",
  "Directeur",
  "Résolution",
  "Clôture",
] as const;

/** Vue simplifiée côté demandeur — 4 étapes lisibles */
export const REQUESTER_LEVELS = [
  "Soumis",
  "Redirigé",
  "Traitement",
  "Validé",
] as const;

export function buildStepsFromStatus(
  status: string,
  meta?: { reopened?: boolean; rejected?: boolean; escalationLevel?: "L2" | "L3" },
): EscalationStep[] {
  // Index 0=Création 1=Qualification 2=Agent 3=Chef 4=Directeur 5=Résolution 6=Clôture
  const escalatedIndex =
    meta?.escalationLevel === "L3" ? 4
    : 3; // L2 par défaut → Chef de service

  const order: Record<string, number> = {
    new: 0,
    qualifying: 1,
    qualified: 2,   // attendant assignation → niveau Agent
    assigned: 2,    // assigné à un agent → niveau Agent
    in_progress: 2, // en traitement agent → niveau Agent
    pending: 2,     // en attente d'info → niveau Agent
    escalated: escalatedIndex,
    resolved: 5,
    closed: 6,
    reopened: 1,
    rejected: 1,
  };
  const isRejected = status === "rejected" || meta?.rejected;
  const isReopened = status === "reopened" || meta?.reopened;
  const current = order[status] ?? 0;
  return DEFAULT_LEVELS.map((level, i) => {
    let st: EscalationStepStatus = "pending";
    if (i < current) st = "done";
    else if (i === current) st = "active";
    if (isRejected && i === current) st = "rejected";
    if (isReopened && i === current) st = "reopened";
    return { level, status: st };
  });
}

/** Mapping statut → étape simplifiée du demandeur */
export function buildRequesterStepsFromStatus(
  status: string,
  meta?: { reopened?: boolean; rejected?: boolean },
): EscalationStep[] {
  const LAST = REQUESTER_LEVELS.length - 1; // index 3 = "Validé"

  const order: Record<string, number> = {
    new: 0,
    qualifying: 1,
    qualified: 1,
    assigned: 1,
    escalated: 1,
    in_progress: 2,
    pending: 2,
    reopened: 1,
    rejected: LAST, // dernière étape → affichée comme "Échec"
    resolved: LAST,
    closed: LAST,
  };
  const isRejected = status === "rejected" || meta?.rejected;
  const isReopened = status === "reopened" || meta?.reopened;
  const current = order[status] ?? 0;

  return REQUESTER_LEVELS.map((level, i) => {
    let st: EscalationStepStatus = "pending";
    if (i < current) st = "done";
    else if (i === current) {
      if (status === "closed" || status === "resolved") st = "done";
      else st = "active";
    }
    if (isRejected && i === current) st = "rejected";
    if (isReopened && i === current) st = "reopened";

    // Renommer la dernière étape "Validé" → "Échec" pour les tickets rejetés
    const displayLevel = isRejected && i === LAST ? "Échec" : level;
    return { level: displayLevel, status: st };
  });
}


type Props = {
  steps: EscalationStep[];
  onStepClick?: (step: EscalationStep, index: number) => void;
  compact?: boolean;
  showLabels?: boolean;
  className?: string;
};

export function EscalationProgressBar({
  steps,
  onStepClick,
  compact = false,
  showLabels = true,
  className,
}: Props) {
  return (
    <TooltipProvider delayDuration={150}>
      <div
        className={cn(
          "glass-subtle relative rounded-2xl px-4 py-5 backdrop-blur-md",
          "border border-white/15 shadow-[0_8px_32px_-12px_rgba(0,0,0,0.25)]",
          className,
        )}
      >
        <div className="overflow-x-auto">
          <ol
            className={cn(
              "flex min-w-max items-start justify-between gap-0",
              compact ? "px-1" : "px-2",
            )}
          >
            {steps.map((step, i) => {
              const isLast = i === steps.length - 1;
              return (
                <li
                  key={i}
                  className="flex flex-1 items-start"
                  style={{ minWidth: compact ? 72 : 96 }}
                >
                  <div className="flex flex-1 flex-col items-center">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          onClick={() => onStepClick?.(step, i)}
                          className={cn(
                            "relative grid place-items-center rounded-full transition-all duration-300",
                            "border backdrop-blur-xl",
                            compact ? "h-5 w-5" : "h-7 w-7",
                            (step.status === "active" || step.status === "rejected") &&
                              (compact ? "h-6 w-6" : "h-9 w-9"),
                            stepRing(step.status),
                          )}
                          aria-label={step.level}
                        >
                          {step.status === "active" && (
                            <span className="absolute inset-0 animate-ping rounded-full bg-amber-400/40" />
                          )}
                          {step.status === "done" && (
                            <Check
                              className={cn(
                                "text-white",
                                compact ? "h-3 w-3" : "h-3.5 w-3.5",
                              )}
                              strokeWidth={3}
                            />
                          )}
                          {step.status === "rejected" && (
                            <X
                              className={cn(
                                "text-white",
                                compact ? "h-3 w-3" : "h-3.5 w-3.5",
                              )}
                              strokeWidth={3}
                            />
                          )}
                          {step.status === "reopened" && (
                            <RotateCcw
                              className={cn(
                                "text-white",
                                compact ? "h-3 w-3" : "h-3.5 w-3.5",
                              )}
                              strokeWidth={2.5}
                            />
                          )}
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="top" className="text-xs">
                        <div className="font-medium">{step.level}</div>
                        {step.actor && (
                          <div className="text-muted-foreground">
                            {step.actor}
                          </div>
                        )}
                        {step.date && (
                          <div className="text-muted-foreground">
                            {new Date(step.date).toLocaleString("fr-FR")}
                          </div>
                        )}
                        {step.comment && (
                          <div className="mt-1 max-w-[200px] italic">
                            "{step.comment}"
                          </div>
                        )}
                      </TooltipContent>
                    </Tooltip>
                    {showLabels && (
                      <div
                        className={cn(
                          "mt-2 text-center text-[10px] leading-tight",
                          step.status === "active"
                            ? "font-semibold text-amber-500 dark:text-amber-300"
                            : step.status === "done"
                              ? "text-foreground/80"
                              : step.status === "rejected"
                                ? "text-destructive"
                                : "text-muted-foreground",
                        )}
                        style={{ maxWidth: 80 }}
                      >
                        {step.level}
                      </div>
                    )}
                  </div>
                  {!isLast && (
                    <div
                      className={cn(
                        "mt-3 h-[2px] flex-1 rounded-full",
                        compact ? "min-w-[24px]" : "min-w-[32px]",
                        connectorClass(step.status, steps[i + 1]?.status),
                      )}
                      style={{ filter: "blur(0.3px)" }}
                    />
                  )}
                </li>
              );
            })}
          </ol>
        </div>
      </div>
    </TooltipProvider>
  );
}

function stepRing(status: EscalationStepStatus) {
  switch (status) {
    case "done":
      return "bg-gradient-to-br from-emerald-400 to-emerald-600 border-emerald-300/60 shadow-[0_0_12px_-2px_rgba(16,185,129,0.6)]";
    case "active":
      return "bg-gradient-to-br from-amber-300 to-amber-500 border-amber-200/70 shadow-[0_0_16px_-2px_rgba(251,191,36,0.7)]";
    case "rejected":
      return "bg-gradient-to-br from-rose-400 to-rose-600 border-rose-300/60 shadow-[0_0_14px_-2px_rgba(244,63,94,0.65)]";
    case "reopened":
      return "bg-gradient-to-br from-amber-400 to-orange-500 border-amber-200/70 shadow-[0_0_14px_-2px_rgba(251,146,60,0.7)]";
    default:
      return "bg-white/5 border-white/30";
  }
}

function connectorClass(
  prev: EscalationStepStatus,
  next?: EscalationStepStatus,
) {
  if (prev === "done" && (next === "done" || next === "active")) {
    return "bg-gradient-to-r from-emerald-500/80 to-emerald-400/60";
  }
  if (prev === "done") {
    return "bg-gradient-to-r from-emerald-500/70 to-white/15";
  }
  if (prev === "rejected") {
    return "bg-gradient-to-r from-rose-400/60 to-white/10";
  }
  return "bg-white/15";
}
