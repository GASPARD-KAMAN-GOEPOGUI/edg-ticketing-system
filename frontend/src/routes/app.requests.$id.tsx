import { createFileRoute, Link } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { WorkflowTimeline } from "@/components/workflow-timeline";
import { useState, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import type { RequestItem, Appreciation } from "@/lib/mock-data";
import { AppreciationForm } from "@/components/appreciation-form";
import {
  EscalationProgressBar,
  buildRequesterStepsFromStatus,
  DEFAULT_LEVELS,
} from "@/components/escalation-progress-bar";
import { cn } from "@/lib/utils";
import { useRole, useUser } from "@/lib/session";
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
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  fetchRequest,
  resolveRequest,
  assignRequest,
  createComment,
  requestReopen,
  reopenRequest,
  rejectReopenRequest,
  closeRequest,
  updateRequest,
  changeRequestPriority,
  cancelRequest,
  escalateRequest,
  uploadAttachment,
  rejectTicket,
  reassignService,
  transferDirection,
  requesterEditRequest,
} from "@/lib/api/requests";
import { fetchRefTable, fetchRequestCategories } from "@/lib/api/admin-config";
import { fetchUser, fetchUsers } from "@/lib/api/accounts";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Direction, Unit } from "@/lib/api/directions-units";
import { submitAppreciation, updateRequestAppreciation } from "@/lib/api/csat";
import {
  fetchRequestWorkflows,
  createAutoCircuit,
  type WorkflowItem,
} from "@/lib/api/workflow";

import {
  ArrowLeft,
  Clock,
  Paperclip,
  User,
  AlertTriangle,
  CheckCircle2,
  ArrowUpRight,
  Building2,
  Mail,
  MapPin,
  Phone,
  BadgeCheck,
  Users,
  UserCheck,
  ChevronDown,
  Lock,
  Loader2,
  GitBranch,
  Plus,
  XCircle,
  RotateCcw,
  Pencil,
  Ban,
  MessageSquare,
  MessageSquareWarning,
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow, format, differenceInDays } from "date-fns";
import { fr } from "date-fns/locale";
import { canTicketAction, isRequester } from "@/lib/capabilities";

export const Route = createFileRoute("/app/requests/$id")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Détail demande — EDG Support" }] }),
  component: RequestDetail,
  notFoundComponent: () => (
    <div className="mx-auto max-w-md p-10 text-center">
      <h2 className="text-lg font-semibold">Demande introuvable</h2>
      <Button asChild variant="outline" className="mt-4 rounded-full">
        <Link to="/app/requests">Retour aux demandes</Link>
      </Button>
    </div>
  ),
});

const DETAIL_CONTEXTS = {
  requests: {
    eyebrow: "Mon espace",
    backLabel: "Toutes les demandes",
    notFoundBackLabel: "Retour aux demandes",
    backTo: "/app/requests",
  },
  supervision: {
    eyebrow: "Supervision",
    backLabel: "Retour à la supervision",
    notFoundBackLabel: "Retour à la supervision",
    backTo: "/app/supervision",
  },
  queue: {
    eyebrow: "File d'attente",
    backLabel: "Retour à la file d'attente",
    notFoundBackLabel: "Retour à la file d'attente",
    backTo: "/app/queue",
  },
  myTickets: {
    eyebrow: "Traitement",
    backLabel: "Retour à mes tickets",
    notFoundBackLabel: "Retour à mes tickets",
    backTo: "/app/my-tickets",
  },
  chiefInbox: {
    eyebrow: "Boîte de traitement",
    backLabel: "Retour à la boîte de traitement",
    notFoundBackLabel: "Retour à la boîte de traitement",
    backTo: "/app/chief-inbox",
  },
  direction: {
    eyebrow: "Vue direction",
    backLabel: "Retour à la vue direction",
    notFoundBackLabel: "Retour à la vue direction",
    backTo: "/app/direction",
  },
  dg: {
    eyebrow: "Vue globale",
    backLabel: "Retour à la vue globale",
    notFoundBackLabel: "Retour à la vue globale",
    backTo: "/app/dg",
  },
  slaCenter: {
    eyebrow: "Centre SLA",
    backLabel: "Retour au centre SLA",
    notFoundBackLabel: "Retour au centre SLA",
    backTo: "/app/sla-center",
  },
  admin: {
    eyebrow: "Administration",
    backLabel: "Retour à l'administration",
    notFoundBackLabel: "Retour à l'administration",
    backTo: "/app/admin/users",
  },
} as const;

export type RequestDetailContext = keyof typeof DETAIL_CONTEXTS;

type RequestDetailPageProps = {
  id: string;
  context?: RequestDetailContext;
};

type Participant = {
  key: string;
  name: string;
  role?: string;
  detail: string;
  lastAt?: string;
};

const PARTICIPANT_ROLE_LABELS: Record<string, string> = {
  user: "Demandeur",
  agent: "Agent",
  chief: "Chef",
  director: "Directeur",
  dg: "Directeur",
  admin: "Admin",
  support: "Support",
};

function participantRoleLabel(role?: string): string | undefined {
  if (!role) return undefined;
  return PARTICIPANT_ROLE_LABELS[role] ?? role;
}

function buildParticipants(
  request: RequestItem,
  visibleComments: RequestItem["comments"],
  assigneeName?: string,
): Participant[] {
  const participants = new Map<string, Participant>();
  const add = (candidate: Participant) => {
    const normalized = candidate.key || `${candidate.name}-${candidate.role ?? ""}`;
    const existing = participants.get(normalized);
    if (!existing) {
      participants.set(normalized, candidate);
      return;
    }
    const shouldReplaceDate = candidate.lastAt && (!existing.lastAt || candidate.lastAt > existing.lastAt);
    participants.set(normalized, {
      ...existing,
      role: existing.role ?? candidate.role,
      detail: shouldReplaceDate ? candidate.detail : existing.detail,
      lastAt: shouldReplaceDate ? candidate.lastAt : existing.lastAt,
    });
  };

  if (request.requesterName) {
    add({
      key: request.requesterId || `requester-${request.requesterName}`,
      name: request.requesterName,
      role: "user",
      detail: "Créateur",
      lastAt: request.createdAt,
    });
  }

  if (request.assigneeId || request.assigneeName || assigneeName) {
    const name = assigneeName ?? request.assigneeName ?? request.assigneeId ?? "Agent assigné";
    add({
      key: request.assigneeId || `assignee-${name}`,
      name,
      role: "agent",
      detail: "Assigné",
      lastAt: request.updatedAt,
    });
  }

  for (const event of request.timeline) {
    if (event.by) {
      add({
        key: event.actorId || `actor-${event.by}`,
        name: event.by,
        role: event.actorRole,
        detail: event.label,
        lastAt: event.at,
      });
    }
    if (event.targetUserName) {
      add({
        key: event.targetUserId || `target-${event.targetUserName}`,
        name: event.targetUserName,
        role: event.targetRole,
        detail: "Destinataire",
        lastAt: event.at,
      });
    }
  }

  for (const comment of visibleComments) {
    add({
      key: comment.authorId || `comment-${comment.author}`,
      name: comment.author,
      detail: "Commentaire",
      lastAt: comment.createdAt,
    });
  }

  return Array.from(participants.values()).sort((a, b) => {
    const aTime = a.lastAt ? new Date(a.lastAt).getTime() : 0;
    const bTime = b.lastAt ? new Date(b.lastAt).getTime() : 0;
    return bTime - aTime;
  });
}

type TimelineItem = RequestItem["timeline"][number];
type ComplianceStepState = "done" | "active" | "pending" | "warning" | "muted";
type EscalationRoleLevel = "chief" | "director";

type ComplianceStep = {
  key: string;
  label: string;
  state: ComplianceStepState;
  actor?: string;
  date?: string;
  detail?: string;
};

const DETAIL_STATUS_LABELS: Record<string, string> = {
  new: "Création",
  qualifying: "Qualification",
  qualified: "Orienté",
  assigned: "Assigné",
  in_progress: "En traitement",
  pending: "En attente",
  escalated: "Escaladé",
  resolved: "Résolu",
  closed: "Clôturé",
  reopened: "Réouvert",
  rejected: "Rejeté",
  cancelled: "Annulé",
};

const STATUS_RANK: Record<string, number> = {
  new: 0,
  qualifying: 1,
  qualified: 2,
  assigned: 3,
  in_progress: 4,
  pending: 4,
  escalated: 5,
  reopened: 4,
  resolved: 6,
  closed: 7,
  rejected: 7,
  cancelled: 7,
};

function normalizeTraceValue(value: unknown): string {
  if (value === undefined || value === null) return "";
  const raw = typeof value === "string" ? value : JSON.stringify(value);
  return raw
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function traceEventText(event: TimelineItem): string {
  return [
    event.type,
    event.label,
    event.comment,
    event.by,
    event.actorRole,
    event.targetRole,
    event.oldStatus,
    event.newStatus,
    event.infos,
  ].map(normalizeTraceValue).join(" ");
}

function traceTime(value?: string): number {
  if (!value) return 0;
  const time = new Date(value).getTime();
  return Number.isFinite(time) ? time : 0;
}

function formatTraceDate(value?: string): string | undefined {
  if (!value || !traceTime(value)) return undefined;
  return format(new Date(value), "dd MMM HH:mm", { locale: fr });
}

function findLatestTraceEvent(
  events: TimelineItem[],
  predicate: (event: TimelineItem) => boolean,
): TimelineItem | undefined {
  return [...events].sort((a, b) => traceTime(b.at) - traceTime(a.at)).find(predicate);
}

function findFirstTraceEvent(
  events: TimelineItem[],
  predicate: (event: TimelineItem) => boolean,
): TimelineItem | undefined {
  return [...events].sort((a, b) => traceTime(a.at) - traceTime(b.at)).find(predicate);
}

function isEscalationTraceEvent(event: TimelineItem): boolean {
  const text = traceEventText(event);
  const type = normalizeTraceValue(event.type);
  return type.includes("escal") || text.includes("escalad") || /\bl[23]\b/.test(text);
}

function isFormalTraceAction(event: TimelineItem): boolean {
  const text = traceEventText(event);
  const type = normalizeTraceValue(event.type);
  return (
    isEscalationTraceEvent(event) ||
    [
      "assign",
      "reassign",
      "transfer",
      "transfere",
      "orient",
      "route",
      "resolve",
      "resolu",
      "resolution",
      "closed",
      "cloture",
      "reopen",
      "reouvert",
      "reouverture",
      "rouvert",
      "reject",
      "rejete",
      "arbitr",
      "validation",
    ].some((term) => type.includes(term) || text.includes(term))
  );
}

function escalationRoleLevel(event: TimelineItem): EscalationRoleLevel | undefined {
  const roleText = normalizeTraceValue([event.actorRole, event.targetRole].filter(Boolean).join(" "));
  if (/\bdg\b/.test(roleText)) return "director";
  if (roleText.includes("director") || roleText.includes("directeur")) return "director";
  if (roleText.includes("chief") || roleText.includes("chef") || roleText.includes("responsable")) {
    return "chief";
  }

  if (!isEscalationTraceEvent(event)) return undefined;

  const text = traceEventText(event);
  if (/\bdg\b/.test(text) || text.includes("direction generale")) return "director";
  if (text.includes("directeur") || text.includes("director") || text.includes("l3")) return "director";
  if (text.includes("chef") || text.includes("chief") || text.includes("responsable") || text.includes("l2")) {
    return "chief";
  }
  return undefined;
}

function latestFormalRoleEvent(
  events: TimelineItem[],
  level: EscalationRoleLevel,
): TimelineItem | undefined {
  return findLatestTraceEvent(events, (event) => (
    isFormalTraceAction(event) && escalationRoleLevel(event) === level
  ));
}

function complianceStepClass(state: ComplianceStepState): string {
  if (state === "done") return "border-emerald-500 bg-emerald-500 text-white shadow-[0_0_18px_rgba(16,185,129,0.35)]";
  if (state === "active") return "border-primary bg-primary text-primary-foreground shadow-[0_0_18px_rgba(34,197,94,0.28)]";
  if (state === "warning") return "border-amber-500 bg-amber-500 text-white shadow-[0_0_18px_rgba(245,158,11,0.25)]";
  if (state === "muted") return "border-border bg-muted text-muted-foreground";
  return "border-border bg-background text-muted-foreground";
}

function buildTicketComplianceTrace(
  request: RequestItem,
  assigneeName?: string,
) {
  const events = request.timeline ?? [];
  const statusRank = STATUS_RANK[request.status] ?? 0;
  const isRejectedOrCancelled = request.status === "rejected" || request.status === "cancelled";

  const creationEvent = findFirstTraceEvent(events, (event) => normalizeTraceValue(event.type).includes("created"));
  const qualificationEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return type.includes("qualif") || type.includes("routed") || text.includes("qualif") || text.includes("orient");
  });
  const assignmentEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return (
      type.includes("assign") ||
      type.includes("in_progress") ||
      text.includes("prise en charge") ||
      event.actorRole === "agent" ||
      event.targetRole === "agent"
    );
  });
  const resolvedEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return type.includes("resolved") || text.includes("resolu") || text.includes("resolution");
  });
  const closedEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return type.includes("closed") || text.includes("cloture") || text.includes("cloturer");
  });
  const reopenEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return (
      type.includes("reopen") ||
      text.includes("rouvert") ||
      text.includes("reouvert") ||
      text.includes("reouverture")
    );
  });
  const finalEvent = closedEvent ?? resolvedEvent;
  const reopenTime = traceTime(reopenEvent?.at);
  const cycleEvents = reopenEvent
    ? events.filter((event) => traceTime(event.at) >= reopenTime)
    : events;
  const isClosed = request.status === "closed";
  const isResolved = request.status === "resolved" || request.status === "closed";

  const chiefEvent = latestFormalRoleEvent(cycleEvents, "chief");
  const directorEvent = latestFormalRoleEvent(cycleEvents, "director");

  if (reopenEvent) {
    const cycleQualificationEvent = findLatestTraceEvent(cycleEvents, (event) => {
      const text = traceEventText(event);
      const type = normalizeTraceValue(event.type);
      return type.includes("qualif") || type.includes("routed") || text.includes("qualif") || text.includes("orient");
    });
    const cycleAssignmentEvent = findLatestTraceEvent(cycleEvents, (event) => {
      const text = traceEventText(event);
      const type = normalizeTraceValue(event.type);
      return (
        type.includes("assign") ||
        type.includes("in_progress") ||
        text.includes("prise en charge") ||
        event.actorRole === "agent" ||
        event.targetRole === "agent"
      );
    });
    const cycleResolvedEvent = findLatestTraceEvent(cycleEvents, (event) => {
      const text = traceEventText(event);
      const type = normalizeTraceValue(event.type);
      return type.includes("resolved") || text.includes("resolu") || text.includes("resolution");
    });
    const cycleClosedEvent = findLatestTraceEvent(cycleEvents, (event) => {
      const text = traceEventText(event);
      const type = normalizeTraceValue(event.type);
      return type.includes("closed") || text.includes("cloture") || text.includes("cloturer");
    });
    const cycleResolvedAt = request.resolvedAt && traceTime(request.resolvedAt) >= reopenTime
      ? request.resolvedAt
      : undefined;
    const cycleClosedAt = request.closedAt && traceTime(request.closedAt) >= reopenTime
      ? request.closedAt
      : undefined;
    const cycleHasResolutionTrace = Boolean(cycleResolvedEvent || cycleResolvedAt || request.status === "resolved");
    const cycleClosedWithoutResolutionTrace = isClosed && !cycleHasResolutionTrace;
    const cycleFinalActor =
      cycleClosedEvent?.by ??
      cycleResolvedEvent?.by ??
      (isResolved ? (request.assigneeName ?? assigneeName) : undefined) ??
      request.assigneeName ??
      assigneeName ??
      "Non renseigné";

    const cycleSteps: ComplianceStep[] = [
      {
        key: "reopen",
        label: "Réouverture",
        state: "done",
        actor: reopenEvent.by,
        date: reopenEvent.at,
        detail: reopenEvent.label ?? "Ticket rouvert",
      },
    ];

    if (cycleQualificationEvent || request.status === "qualifying") {
      cycleSteps.push({
        key: "requalification",
        label: "Réorientation",
        state: cycleQualificationEvent || statusRank >= 2 || request.serviceId ? "done" : "active",
        actor: cycleQualificationEvent?.by,
        date: cycleQualificationEvent?.at,
        detail: cycleQualificationEvent?.label ?? "Réorientation après réouverture",
      });
    }

    cycleSteps.push({
      key: "reopened-treatment",
      label: "Traitement repris",
      state:
        isResolved || request.status === "escalated" ? "done"
        : ["assigned", "in_progress", "pending", "reopened"].includes(request.status) ? "active"
        : request.assigneeId || request.assigneeName || assigneeName ? "done"
        : "pending",
      actor: cycleAssignmentEvent?.targetUserName ?? cycleAssignmentEvent?.by ?? request.assigneeName ?? assigneeName,
      date: cycleAssignmentEvent?.at,
      detail: cycleAssignmentEvent?.label ?? "Cycle repris après réouverture",
    });

    [
      { key: "chief", label: "Chef de service", event: chiefEvent },
      { key: "director", label: "Directeur", event: directorEvent },
    ].forEach((level) => {
      if (!level.event) return;
      cycleSteps.push({
        key: `${level.key}-after-reopen`,
        label: level.label,
        state: "done",
        actor: level.event.by ?? level.event.targetUserName,
        date: level.event.at,
        detail: level.event.label,
      });
    });

    if (isRejectedOrCancelled) {
      const finalLabel = DETAIL_STATUS_LABELS[request.status] ?? request.status;
      cycleSteps.push({
        key: "final-after-reopen",
        label: finalLabel,
        state: "warning",
        actor: cycleFinalActor,
        date: request.updatedAt,
        detail: `Sortie du cycle rouvert : ${finalLabel}`,
      });
    } else {
      cycleSteps.push({
        key: "resolution-after-reopen",
        label: "Nouvelle résolution",
        state: isResolved ? (cycleHasResolutionTrace ? "done" : "warning") : "pending",
        actor: cycleResolvedEvent?.by ?? (isResolved ? cycleFinalActor : undefined),
        date: cycleResolvedEvent?.at ?? cycleResolvedAt,
        detail: cycleHasResolutionTrace ? (cycleResolvedEvent?.label ?? "Résolution après réouverture") : "Résolution en attente",
      });
      cycleSteps.push({
        key: "closure-after-reopen",
        label: "Nouvelle clôture",
        state: isClosed ? (cycleClosedWithoutResolutionTrace ? "warning" : "done") : request.status === "resolved" ? "active" : "pending",
        actor: cycleClosedEvent?.by,
        date: cycleClosedEvent?.at ?? cycleClosedAt,
        detail: isClosed ? (cycleClosedEvent?.label ?? "Clôture après réouverture") : "Clôture en attente",
      });
    }

    return { steps: cycleSteps };
  }

  const hasResolutionTrace = Boolean(resolvedEvent || request.resolvedAt || request.status === "resolved");
  const closedWithoutResolutionTrace = isClosed && !hasResolutionTrace;

  const finalActor =
    finalEvent?.by ??
    (isResolved ? (request.assigneeName ?? assigneeName) : undefined) ??
    request.assigneeName ??
    assigneeName ??
    "Non renseigné";

  const steps: ComplianceStep[] = [
    {
      key: "creation",
      label: "Création",
      state: "done",
      actor: creationEvent?.by ?? request.requesterName,
      date: creationEvent?.at ?? request.createdAt,
      detail: creationEvent?.label ?? "Demande enregistrée",
    },
    {
      key: "qualification",
      label: "Qualification",
      state: qualificationEvent || statusRank >= 2 || request.serviceId ? "done" : request.status === "qualifying" ? "active" : "pending",
      actor: qualificationEvent?.by,
      date: qualificationEvent?.at,
      detail: qualificationEvent?.label ?? (request.serviceId ? "Service orienté" : "Orientation attendue"),
    },
    {
      key: "agent",
      label: "Agent",
      state:
        isResolved || request.status === "escalated" ? "done"
        : ["assigned", "in_progress", "pending", "reopened"].includes(request.status) ? "active"
        : request.assigneeId || request.assigneeName || assigneeName ? "done"
        : "pending",
      actor: assignmentEvent?.targetUserName ?? assignmentEvent?.by ?? request.assigneeName ?? assigneeName,
      date: assignmentEvent?.at,
      detail: assignmentEvent?.label ?? (request.assigneeId || request.assigneeName || assigneeName ? "Agent assigné" : "Aucun agent assigné"),
    },
  ];

  [
    { key: "chief", label: "Chef de service", event: chiefEvent },
    { key: "director", label: "Directeur", event: directorEvent },
  ].forEach((level) => {
    if (!level.event) return;
    steps.push({
      key: level.key,
      label: level.label,
      state: "done",
      actor: level.event.by ?? level.event.targetUserName,
      date: level.event.at,
      detail: level.event.label,
    });
  });

  if (isRejectedOrCancelled) {
    const finalLabel = DETAIL_STATUS_LABELS[request.status] ?? request.status;
    steps.push({
      key: "final",
      label: finalLabel,
      state: "warning",
      actor: finalEvent?.by,
      date: finalEvent?.at ?? request.updatedAt,
      detail: `Sortie du workflow : ${finalLabel}`,
    });
  } else {
    steps.push({
      key: "resolution",
      label: "Résolution",
      state: isResolved ? (hasResolutionTrace ? "done" : "warning") : "pending",
      actor: resolvedEvent?.by ?? (isResolved ? finalActor : undefined),
      date: resolvedEvent?.at ?? request.resolvedAt,
      detail: hasResolutionTrace ? (resolvedEvent?.label ?? "Résolution tracée") : "Résolution non encore tracée",
    });
    steps.push({
      key: "closure",
      label: "Clôture",
      state: isClosed ? (closedWithoutResolutionTrace ? "warning" : "done") : request.status === "resolved" ? "active" : "pending",
      actor: closedEvent?.by,
      date: closedEvent?.at ?? request.closedAt,
      detail: isClosed ? (closedEvent?.label ?? "Clôture enregistrée") : "Clôture en attente",
    });
  }

  return { steps };
}

function TicketComplianceTrace({
  request,
  assigneeName,
}: {
  request: RequestItem;
  assigneeName?: string;
}) {
  const trace = buildTicketComplianceTrace(request, assigneeName);

  return (
    <section className="border-t border-border/40 bg-muted/10 px-5 py-4 sm:px-6">
      <div className="overflow-x-auto rounded-2xl border border-border/60 bg-background/35 px-4 py-4">
        <ol className="flex min-w-max items-start">
          {trace.steps.map((step, index) => {
            const isLast = index === trace.steps.length - 1;
            const StepIcon =
              step.state === "warning" ? AlertTriangle
              : step.state === "active" || step.state === "pending" ? Clock
              : CheckCircle2;
            return (
              <li key={step.key} className="flex items-start">
                <div className="flex w-28 flex-col items-center text-center">
                  <span className={cn("grid h-9 w-9 place-items-center rounded-full border text-sm", complianceStepClass(step.state))}>
                    <StepIcon className="h-4 w-4" />
                  </span>
                  <span className="mt-2 text-xs font-semibold">{step.label}</span>
                  {step.actor && (
                    <span className="mt-1 max-w-24 truncate text-[11px] text-muted-foreground">
                      {step.actor}
                    </span>
                  )}
                  {(step.date || step.detail) && (
                    <span className="mt-0.5 max-w-24 truncate text-[10px] text-muted-foreground">
                      {formatTraceDate(step.date) ?? step.detail}
                    </span>
                  )}
                </div>
                {!isLast && (
                  <span className={cn(
                    "mt-4 h-0.5 w-12 shrink-0 rounded-full",
                    step.state === "done" ? "bg-emerald-500" : step.state === "warning" ? "bg-amber-500" : "bg-border",
                  )} />
                )}
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

function RequestDetail() {
  const { id } = Route.useParams();
  return <RequestDetailPage id={id} context="requests" />;
}

export function RequestDetailPage({ id, context = "requests" }: RequestDetailPageProps) {
  const detailContext = DETAIL_CONTEXTS[context];
  const isPersonalContext = context === "requests";
  const qc = useQueryClient();
  const sessionUser = useUser();
  const authorId = Number(sessionUser?.id ?? 0);
  const authorName = [sessionUser?.firstname, sessionUser?.name].filter(Boolean).join(" ") || "Agent";
  const includeDeleted = context === "admin";
  const requestQueryKey = ["request", id, includeDeleted ? "with-deleted" : "active"] as const;

  const { data: r, isLoading, isError } = useQuery({
    queryKey: requestQueryKey,
    queryFn: () => fetchRequest(id, { includeDeleted }),
    staleTime: 15_000,
  });

  const [comment, setComment] = useState("");
  const [isPublic, setIsPublic] = useState(false);
  const [role] = useRole();
  // Dans "Mes demandes", le propriétaire garde la vue demandeur. Dans les espaces
  // métier, le contexte fonctionnel prime sur la propriété personnelle du ticket.
  const iAmRequester = isRequester(r?.requesterId, sessionUser?.id);
  const isRequesterView = role === "user" || (isPersonalContext && iAmRequester);
  const isAgentOnly = role === "agent" && !iAmRequester;
  const [localAppreciation, setLocalAppreciation] = useState<Appreciation | undefined>(undefined);
  const [showReassign, setShowReassign] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [showReopenForm, setShowReopenForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editCategory, setEditCategory] = useState("");
  const [editPriority, setEditPriority] = useState("");
  const [editDirectionId, setEditDirectionId] = useState("");
  const [editServiceId, setEditServiceId] = useState("");
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [showRequestInfoForm, setShowRequestInfoForm] = useState(false);
  const [infoQuestion, setInfoQuestion] = useState("");
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [resolutionNote, setResolutionNote] = useState("");
  const [showEscalateForm, setShowEscalateForm] = useState(false);
  const [escalateLevel, setEscalateLevel] = useState<string>(DEFAULT_LEVELS[3] ?? "Chef de service");
  const [escalateReason, setEscalateReason] = useState("");
  const attachRef = useRef<HTMLInputElement>(null);
  const commentRef = useRef<HTMLTextAreaElement>(null);
  const [showPriorityPicker, setShowPriorityPicker] = useState(false);
  const [showRejectConfirm, setShowRejectConfirm] = useState(false);
  const [rejectNote, setRejectNote] = useState("");
  const [showRejectReopenConfirm, setShowRejectReopenConfirm] = useState(false);
  const [rejectReopenNote, setRejectReopenNote] = useState("");
  const [showServicePicker, setShowServicePicker] = useState(false);
  const [showDirectionTransfer, setShowDirectionTransfer] = useState(false);
  const [transferDirectionId, setTransferDirectionId] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [showCircuitDialog, setShowCircuitDialog] = useState(false);
  const [circuitDirectionId, setCircuitDirectionId] = useState("");
  const [circuitUnitId, setCircuitUnitId] = useState("");

  const invalidate = () => {
    // Détail du ticket (et sous-queries via préfixe)
    qc.invalidateQueries({ queryKey: requestQueryKey });
    // Toutes les listes/vues qui peuvent contenir ce ticket
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["queue"] });
    qc.invalidateQueries({ queryKey: ["my-tickets"] });
    qc.invalidateQueries({ queryKey: ["my-tickets-stats"] });
    qc.invalidateQueries({ queryKey: ["my-stats", sessionUser?.id] });
    // Stats et tableaux de bord
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
    qc.invalidateQueries({ queryKey: ["sla-center"] });
  };
  const invalidateWorkflows = () => {
    qc.invalidateQueries({ queryKey: ["request", id, "workflows"] });
    qc.invalidateQueries({ queryKey: ["workflow"] });
  };

  const resolveMut = useMutation({
    mutationFn: async () => {
      if (resolutionNote.trim()) {
        await createComment(id, {
          author_id: authorId,
          author_name: authorName,
          body: `[Résolution] ${resolutionNote.trim()}`,
          is_public: false,
        });
      }
      return resolveRequest(id);
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "resolved" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande marquée comme résolue.");
      setShowResolveForm(false);
      setResolutionNote("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de résoudre la demande.");
    },
    onSettled: () => invalidate(),
  });

  const assignMut = useMutation({
    mutationFn: (assigneeId: string) => assignRequest(id, assigneeId),
    onMutate: async (assigneeId) => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, assigneeId, status: "assigned" } : old,
      );
      return { previous };
    },
    onSuccess: (_, assigneeId) => {
      const agent = agentPool.find((u) => u.id === assigneeId);
      toast.success(`Réassigné à ${agent?.name ?? assigneeId}`);
      setShowReassign(false);
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de réassigner la demande.");
    },
    onSettled: () => invalidate(),
  });

  const selfAssignMut = useMutation({
    mutationFn: () => assignRequest(id, String(sessionUser?.id ?? "")),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old
          ? {
              ...old,
              assigneeId: String(sessionUser?.id ?? ""),
              assigneeName: authorName,
              status: "assigned",
            }
          : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Ticket assigné à vous.");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de vous assigner ce ticket.");
    },
    onSettled: () => invalidate(),
  });

  const { data: workflows = [] } = useQuery({
    queryKey: ["request", id, "workflows"],
    queryFn: () => fetchRequestWorkflows(id),
    enabled: !isRequesterView,
    staleTime: 30_000,
  });

  const activeWorkflow = workflows.find((w) => w.workflowStatus === "active") ?? workflows[0];

  // Phase 1 : utilisateur demande la réouverture (motif obligatoire)
  const requestReopenMut = useMutation({
    mutationFn: (reason: string) => requestReopen(id, reason),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, infos: { ...(old.infos ?? {}), reopen_requested: true } } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande de réouverture envoyée — le chef de service sera notifié.");
      setShowReopenForm(false);
      setReopenReason("");
    },
    onError: (err: unknown, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible d'envoyer la demande de réouverture.");
    },
    onSettled: () => invalidate(),
  });

  const approveReopenMut = useMutation({
    mutationFn: () => reopenRequest(id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "reopened", infos: { ...(old.infos ?? {}), reopen_requested: false } } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Réouverture approuvée — le ticket retourne en traitement.");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'approuver la réouverture.");
    },
    onSettled: () => invalidate(),
  });

  const rejectReopenMut = useMutation({
    mutationFn: () => rejectReopenRequest(id, rejectReopenNote.trim()),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) => {
        if (!old) return old;
        const infos = { ...(old.infos ?? {}) };
        delete infos.reopen_requested;
        return { ...old, infos };
      });
      return { previous };
    },
    onSuccess: () => {
      toast.success("Réouverture refusée avec motif.");
      setShowRejectReopenConfirm(false);
      setRejectReopenNote("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de refuser la réouverture.");
    },
    onSettled: () => invalidate(),
  });

  const closeMut = useMutation({
    mutationFn: () => closeRequest(id),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "closed" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande clôturée — merci pour votre retour.");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de clôturer la demande.");
    },
    onSettled: () => invalidate(),
  });

  const editMut = useMutation({
    mutationFn: () => requesterEditRequest(id, {
      title: editTitle.trim() || undefined,
      description: editDescription.trim() || undefined,
      category: editCategory || undefined,
      priority: editPriority || undefined,
      direction_id: editDirectionId || undefined,
      unity_id: editServiceId || undefined,
    }),
    onSuccess: () => {
      toast.success("Demande modifiée — re-routage effectué.");
      setShowEditForm(false);
      invalidate();
    },
    onError: (err: unknown) => {
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible de modifier la demande.");
    },
  });

  const cancelMut = useMutation({
    mutationFn: () => cancelRequest(id, cancelReason.trim()),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "cancelled" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Demande annulée.");
      setShowCancelConfirm(false);
      setCancelReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'annuler la demande.");
    },
    onSettled: () => invalidate(),
  });

  const takeOwnershipMut = useMutation({
    mutationFn: () => updateRequest(id, { request_status: "in_progress" }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Ticket pris en charge — traitement en cours."); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de prendre en charge la demande.");
    },
    onSettled: () => invalidate(),
  });

  const requestInfoMut = useMutation({
    mutationFn: async () => {
      await createComment(id, {
        author_id: authorId,
        author_name: authorName,
        body: infoQuestion.trim(),
        is_public: true,
      });
      return updateRequest(id, { request_status: "pending" });
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "pending" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Le demandeur a été notifié — ticket mis en attente.");
      setShowRequestInfoForm(false);
      setInfoQuestion("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'envoyer la demande d'informations.");
    },
    onSettled: () => invalidate(),
  });

  const resumeMut = useMutation({
    mutationFn: () => updateRequest(id, { request_status: "in_progress" }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Traitement repris."); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de reprendre le traitement.");
    },
    onSettled: () => invalidate(),
  });

  const changePriorityMut = useMutation({
    mutationFn: (priority: string) => changeRequestPriority(id, priority),
    onMutate: async (priority) => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, priority: priority as RequestItem["priority"] } : old,
      );
      return { previous };
    },
    onSuccess: (_, p) => { toast.success(`Priorité changée → ${p}.`); setShowPriorityPicker(false); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de changer la priorité.");
    },
    onSettled: () => invalidate(),
  });

  const rejectMut = useMutation({
    mutationFn: () => rejectTicket(id, rejectNote.trim()),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "rejected" } : old,
      );
      return { previous };
    },
    onSuccess: () => { toast.success("Demande rejetée."); setShowRejectConfirm(false); setRejectNote(""); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de rejeter la demande.");
    },
    onSettled: () => invalidate(),
  });

  const changeServiceMut = useMutation({
    mutationFn: (unit_id: string) => reassignService(id, unit_id, "Réaffectation depuis le détail ticket"),
    onSuccess: (_, s) => { toast.success(`Service changé → ${s}.`); setShowServicePicker(false); invalidate(); },
    onError: () => toast.error("Impossible de changer le service."),
  });

  const transferDirectionMut = useMutation({
    mutationFn: () => transferDirection(id, transferDirectionId, transferReason.trim()),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old
          ? {
              ...old,
              status: "qualifying",
              directionId: transferDirectionId,
              serviceId: transferDirectionId,
              assigneeId: undefined,
              assigneeName: undefined,
            }
          : old,
      );
      return { previous };
    },
    onSuccess: () => {
      const target = directions.find((d) => d.id === transferDirectionId);
      toast.success(`Demande transférée vers ${target?.name ?? "la direction cible"}.`);
      setShowDirectionTransfer(false);
      setTransferDirectionId("");
      setTransferReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de transférer la demande.");
    },
    onSettled: () => invalidate(),
  });

  const createCircuitMut = useMutation({
    mutationFn: () => createAutoCircuit(id, {
      direction_id: circuitDirectionId ? Number(circuitDirectionId) : undefined,
      unit_id: circuitUnitId ? Number(circuitUnitId) : undefined,
    }),
    onSuccess: () => {
      toast.success("Circuit de validation créé avec succès");
      setShowCircuitDialog(false);
      setCircuitDirectionId("");
      setCircuitUnitId("");
      invalidateWorkflows();
    },
    onError: () => toast.error("Impossible de créer le circuit de validation"),
  });

  const escalateMut = useMutation({
    mutationFn: () => escalateRequest(id, {
      level: escalateLevel,
      reason: escalateReason.trim() || "Escalade manuelle",
    }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "escalated" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success(`Demande escaladée vers ${escalateLevel}.`);
      setShowEscalateForm(false);
      setEscalateReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'escalader la demande.");
    },
    onSettled: () => invalidate(),
  });

  const attachCommentMut = useMutation({
    mutationFn: (file: File) => uploadAttachment(id, file),
    onSuccess: () => {
      toast.success("Pièce jointe ajoutée au ticket.");
      if (attachRef.current) attachRef.current.value = "";
      invalidate();
    },
    onError: () => toast.error("Impossible d'ajouter la pièce jointe."),
  });

  const commentMut = useMutation({
    mutationFn: () =>
      createComment(id, {
        author_id: authorId,
        author_name: authorName,
        body: comment.trim(),
        is_public: isRequesterView ? true : isPublic,
      }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      const optimisticComment = {
        id: `temp-${Date.now()}`,
        authorId: String(authorId),
        author: authorName,
        body: comment.trim(),
        isPublic: isRequesterView ? true : isPublic,
        isEdited: false,
        createdAt: new Date().toISOString(),
      };
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, comments: [...(old.comments ?? []), optimisticComment] } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Commentaire ajouté");
      setComment("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'ajouter le commentaire.");
    },
    onSettled: () => invalidate(),
  });

  const { data: assigneeUser } = useQuery({
    queryKey: ["user", r?.assigneeId],
    queryFn: () => fetchUser(r!.assigneeId!),
    enabled: isRequesterView && !!r?.assigneeId,
    staleTime: 300_000,
  });

  const { data: agentsData } = useQuery({
    queryKey: ["agents"],
    queryFn: () => fetchUsers({ role: "agent", limit: 100 }),
    enabled: !isRequesterView,
    staleTime: 120_000,
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: editUnits = [] } = useQuery({
    queryKey: ["units", editDirectionId],
    queryFn: () => fetchUnits(editDirectionId),
    enabled: !!editDirectionId && showEditForm,
    staleTime: 5 * 60_000,
  });

  const { data: units = [] } = useQuery({
    queryKey: ["units-all"],
    queryFn: () => fetchUnits(),
    enabled: !!r?.serviceId,
    staleTime: 5 * 60_000,
  });

  const { data: categoriesRef = [] } = useQuery({
    queryKey: ["ref-request-categories"],
    queryFn: fetchRequestCategories,
    staleTime: 10 * 60_000,
    enabled: isRequesterView,
  });
  const activeCategories = categoriesRef.filter((c) => c.status !== false);

  const escalationLevelsRef: { label: string }[] = [];

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" /> Chargement…
      </div>
    );
  }

  if (isError || !r) {
    return (
      <div className="mx-auto max-w-md py-20 text-center">
        <h2 className="text-lg font-semibold">Demande introuvable</h2>
        <Button asChild variant="outline" className="mt-4 rounded-full">
          <Link to={detailContext.backTo}>{detailContext.notFoundBackLabel}</Link>
        </Button>
      </div>
    );
  }

  const localStatus = localAppreciation ? r.status : r.status;
  const authorType = (r.requesterType === "external" || r.isExternal) ? "external" : "internal";
  const slaPct = r.slaHours > 0 ? Math.min(100, Math.round((r.slaElapsed / r.slaHours) * 100)) : 0;
  const slaOver = r.slaHours > 0 && r.slaElapsed > r.slaHours;
  const assignedUnit = units.find((u) => String(u.id) === String(r.serviceId));
  const unitName = assignedUnit?.name ?? "—";
  const currentDirectionId = assignedUnit?.direction_id ?? r.directionId ?? r.serviceId;
  const directionName = directions.find(
    (d) => String(d.id) === currentDirectionId,
  )?.name ?? "—";
  const transferDirectionOptions = directions.filter(
    (d) => String(d.id) !== String(currentDirectionId),
  );

  const isArchived = Boolean(r.deletedAt || r.isArchived);
  const isFinal = isArchived || (["resolved", "closed", "rejected", "cancelled"] as const).includes(
    r.status as "resolved" | "closed" | "rejected" | "cancelled",
  );

  const agentPool = agentsData?.items ?? [];
  const availableServices = [...new Set(agentPool.map((a) => a.unit_id).filter((u): u is string => !!u))];

  const visibleComments = isRequesterView ? r.comments.filter((c) => c.isPublic) : r.comments;
  const participants = buildParticipants(r, visibleComments, assigneeUser?.name);
  const needsUserResponse = isRequesterView && r.status === "pending";
  const isAssignedToMe = isRequester(r.assigneeId, sessionUser?.id);
  const hasAssignee = Boolean(r.assigneeId);
  const hasReopenRequest = (r.infos as Record<string, unknown> | undefined)?.reopen_requested === true;

  // Compteur fermeture auto (4 jours après résolution)
  const daysUntilAutoClose = r.resolvedAt
    ? Math.max(0, 4 - differenceInDays(new Date(), new Date(r.resolvedAt)))
    : 4;

  // Fenêtre réouverture ticket fermé (7 jours après fermeture)
  const canReopenClosed = r.closedAt
    ? differenceInDays(new Date(), new Date(r.closedAt)) <= 7
    : false;
  const ownershipOptions = { isRequester: iAmRequester };
  const canEdit = !isArchived && iAmRequester && canTicketAction(role, "requester_edit", r.status, ownershipOptions);
  const canCancel = !isArchived && iAmRequester && canTicketAction(role, "cancel", r.status, ownershipOptions);
  const canClose = !isArchived && iAmRequester && canTicketAction(role, "close", r.status, ownershipOptions);
  const canRequestReopen = !isArchived && iAmRequester && canTicketAction(role, "request_reopen", r.status, {
    ...ownershipOptions,
    canReopenClosed,
  });
  const canSelfAssign = !isArchived && isAgentOnly && canTicketAction(role, "self_assign", r.status, {
    ...ownershipOptions,
    hasAssignee,
    isAssignedToMe,
  });
  const canTakeOwnership = !isArchived && isAgentOnly && canTicketAction(role, "take_ownership", r.status, {
    ...ownershipOptions,
    isAssignedToMe,
  });
  const canRequestInfo = !isArchived && isAgentOnly && canTicketAction(role, "request_info", r.status, ownershipOptions);
  const canResumeTreatment = !isArchived && isAgentOnly && canTicketAction(role, "resume", r.status, ownershipOptions);
  const canEscalateTicket = !isArchived
    && !iAmRequester
    && canTicketAction(role, "escalate", r.status, ownershipOptions)
    && (role !== "agent" || isAssignedToMe);
  const canAssignTicket = !isArchived && !iAmRequester && canTicketAction(role, "assign", r.status, ownershipOptions);
  const canResolveTicket = !isArchived && !iAmRequester && canTicketAction(role, "resolve", r.status, ownershipOptions);
  const canCreateCircuit = !isArchived && !iAmRequester && canTicketAction(role, "create_circuit", r.status, ownershipOptions);
  const canChangePriority = !isArchived && !iAmRequester && canTicketAction(role, "change_priority", r.status, ownershipOptions);
  const canChangeService = !isArchived && !iAmRequester && canTicketAction(role, "change_service", r.status, ownershipOptions);
  const canTransferDirection = !isArchived && !iAmRequester && canTicketAction(role, "transfer_direction", r.status, ownershipOptions);
  const canRejectTicket = !isArchived && !iAmRequester && canTicketAction(role, "reject", r.status, ownershipOptions);
  const canApproveReopen = !isArchived && !iAmRequester && canTicketAction(role, "approve_reopen", r.status, {
    ...ownershipOptions,
    hasReopenRequest,
  });
  const canRejectReopen = !isArchived && !iAmRequester && canTicketAction(role, "reject_reopen", r.status, {
    ...ownershipOptions,
    hasReopenRequest,
  });
  const canDecideReopen = canApproveReopen || canRejectReopen;

  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <div>
        <Button asChild variant="ghost" size="sm" className="-ml-2 rounded-full">
          <Link to={detailContext.backTo}>
            <ArrowLeft className="mr-1 h-4 w-4" /> {detailContext.backLabel}
          </Link>
        </Button>
      </div>

      <div className="overflow-hidden rounded-[28px] border border-border/50 bg-card/70 shadow-sm backdrop-blur">
      <header className="flex flex-wrap items-start justify-between gap-4 p-5 sm:p-6">
        <div className="min-w-0">
          <div className="mb-2 inline-flex items-center rounded-full border border-border/60 bg-background/60 px-3 py-1 text-xs font-semibold text-muted-foreground">
            {detailContext.eyebrow}
          </div>
          <motion.div
            layoutId={`req-ref-${r.id}`}
            className="font-mono text-xs text-muted-foreground"
          >
            {r.ref}
          </motion.div>
          <h1 className="mt-1 text-2xl font-bold tracking-tight sm:text-3xl">{r.title}</h1>
          <div className="mt-2 flex flex-wrap gap-2">
            <StatusBadge status={r.status} />
            <PriorityBadge priority={r.priority} />
            <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs text-muted-foreground">
              {r.category}
            </span>
          </div>
        </div>

        {needsUserResponse && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                L'agent vous demande des informations complémentaires
              </p>
              <p className="mt-0.5 text-sm text-amber-600/80 dark:text-amber-400/70">
                Répondez via la section commentaires ci-dessous pour que le traitement de votre demande puisse reprendre.
              </p>
            </div>
          </div>
        )}

        {isArchived && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-amber-700 dark:text-amber-400">
                Ticket archivé
              </p>
              <p className="mt-0.5 text-sm text-amber-600/80 dark:text-amber-400/70">
                Consultation admin en lecture seule. Les actions métier sont désactivées.
              </p>
            </div>
          </div>
        )}

        {isRequesterView && (canEdit || canCancel) && (
          <div className="flex flex-wrap gap-2">
            {canEdit && (
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => {
                  setEditTitle(r.title);
                  setEditDescription(r.description);
                  setEditCategory(r.category ?? "");
                  setEditPriority(r.priority ?? "medium");
                  setEditDirectionId(r.directionId ?? "");
                  setEditServiceId(r.serviceId ?? "");
                  setShowEditForm(true);
                }}
              >
                <Pencil className="mr-1.5 h-4 w-4" /> Modifier
              </Button>
            )}
            {canCancel && (
              <Button
                variant="outline"
                className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60"
                onClick={() => setShowCancelConfirm(true)}
              >
                <Ban className="mr-1.5 h-4 w-4" /> Annuler la demande
              </Button>
            )}
          </div>
        )}

        {!isRequesterView && (
          (isFinal && !canDecideReopen) ? (
            <div className="flex items-center gap-2 rounded-full border border-border/40 bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
              <Lock className="h-3.5 w-3.5" />
              Ticket {isArchived ? "archivé" : r.status === "closed" ? "clôturé" : r.status === "rejected" ? "rejeté" : "résolu"} — aucune action disponible
            </div>
          ) : (
            <div className="flex flex-wrap gap-2">
              {canApproveReopen && (
                <Button
                  className="rounded-full"
                  onClick={() => approveReopenMut.mutate()}
                  disabled={approveReopenMut.isPending}
                >
                  {approveReopenMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <RotateCcw className="mr-1 h-4 w-4" />}
                  Approuver réouverture
                </Button>
              )}
              {canRejectReopen && (
                <Button
                  variant="outline"
                  className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10"
                  onClick={() => setShowRejectReopenConfirm(true)}
                >
                  <XCircle className="mr-1 h-4 w-4" />
                  Refuser réouverture
                </Button>
              )}
              {/* Agent — auto-assignation d'un ticket libre de son périmètre */}
              {canSelfAssign && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => selfAssignMut.mutate()}
                  disabled={selfAssignMut.isPending || !sessionUser?.id}
                >
                  {selfAssignMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <UserCheck className="mr-1 h-4 w-4" />}
                  M'assigner
                </Button>
              )}
              {/* C1/C9 — Prendre en charge : ASSIGNED, agent seulement */}
              {canTakeOwnership && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => takeOwnershipMut.mutate()}
                  disabled={takeOwnershipMut.isPending}
                >
                  {takeOwnershipMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <UserCheck className="mr-1 h-4 w-4" />}
                  Démarrer traitement
                </Button>
              )}
              {/* C2 — Demander des informations : IN_PROGRESS, agent seulement */}
              {canRequestInfo && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowRequestInfoForm((v) => !v)}
                >
                  <MessageSquareWarning className="mr-1 h-4 w-4" />
                  Demander des infos
                </Button>
              )}
              {/* C3 — Reprendre le traitement : PENDING, agent seulement */}
              {canResumeTreatment && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => resumeMut.mutate()}
                  disabled={resumeMut.isPending}
                >
                  {resumeMut.isPending
                    ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                    : <RotateCcw className="mr-1 h-4 w-4" />}
                  Reprendre le traitement
                </Button>
              )}
              {/* C5 — Escalader : agent, chef, directeur, admin seulement */}
              {canEscalateTicket && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowEscalateForm((v) => !v)}
                >
                  <ArrowUpRight className="mr-1 h-4 w-4" /> Escalader
                </Button>
              )}
              {/* C6 — Assigner / réassigner : chef et admin seulement */}
              {canAssignTicket && (
              <div className="relative">
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowReassign((v) => !v)}
                  disabled={assignMut.isPending}
                >
                  <UserCheck className="mr-1 h-4 w-4" />
                  Réassigner
                  <ChevronDown className="ml-1 h-3.5 w-3.5" />
                </Button>
                {showReassign && (
                  <div className="absolute right-0 top-10 z-30 min-w-48 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                    <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">
                      Choisir un agent
                    </p>
                    {agentPool.length === 0 && (
                      <p className="px-3 py-2 text-xs text-muted-foreground">Chargement…</p>
                    )}
                    {agentPool.map((agent) => (
                      <button
                        key={agent.id}
                        className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-foreground/5"
                        onClick={() => assignMut.mutate(agent.id)}
                      >
                        <span className="grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                          {agent.name.slice(0, 2).toUpperCase()}
                        </span>
                        {agent.name}
                        {agent.availability && (
                          <span className="ml-auto text-[10px] text-muted-foreground">{agent.availability}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
              )}
              {/* Créer circuit : agent, chef, admin */}
              {canCreateCircuit && workflows.length === 0 && (
                <Button
                  variant="outline"
                  className="rounded-full"
                  onClick={() => setShowCircuitDialog(true)}
                >
                  <GitBranch className="mr-1 h-4 w-4" /> Créer circuit
                </Button>
              )}
              {/* Chef + Director: Changer priorité */}
              {canChangePriority && (
                <div className="relative">
                  <Button variant="outline" className="rounded-full" onClick={() => setShowPriorityPicker((v) => !v)} disabled={changePriorityMut.isPending}>
                    <ChevronDown className="mr-1 h-4 w-4" /> Priorité
                  </Button>
                  {showPriorityPicker && (
                    <div className="absolute right-0 top-10 z-30 min-w-40 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                      {(["low", "medium", "high", "critical"] as const).map((p) => (
                        <button key={p} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-foreground/5" onClick={() => changePriorityMut.mutate(p)}>
                          <PriorityBadge priority={p} />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}
              {/* Responsables: Rejeter + Changer service + Transfert direction */}
              {(canRejectTicket || canChangeService || canTransferDirection) && (
                <>
                  {canRejectTicket && (
                    <Button variant="outline" className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60" onClick={() => setShowRejectConfirm((v) => !v)}>
                      <Ban className="mr-1 h-4 w-4" /> Rejeter
                    </Button>
                  )}
                  {canChangeService && (
                    <div className="relative">
                      <Button variant="outline" className="rounded-full" onClick={() => setShowServicePicker((v) => !v)} disabled={changeServiceMut.isPending}>
                        <Building2 className="mr-1 h-4 w-4" /> Service
                      </Button>
                      {showServicePicker && (
                        <div className="absolute right-0 top-10 z-30 min-w-52 rounded-xl border border-border/50 bg-card shadow-xl p-1.5">
                          <p className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/60">Choisir un service</p>
                          {availableServices.length === 0 ? (
                            <p className="px-3 py-2 text-xs text-muted-foreground">Aucun service disponible</p>
                          ) : availableServices.map((svc) => (
                            <button key={svc} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs hover:bg-foreground/5" onClick={() => changeServiceMut.mutate(svc)}>
                              {svc}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  {canTransferDirection && (
                    <Button
                      variant="outline"
                      className="rounded-full"
                      onClick={() => {
                        setTransferDirectionId("");
                        setTransferReason("");
                        setShowDirectionTransfer(true);
                      }}
                      disabled={transferDirectionMut.isPending}
                    >
                      <Building2 className="mr-1 h-4 w-4" /> Transférer direction
                    </Button>
                  )}
                </>
              )}
              {/* C4 — Marquer résolue : 1 clic direct, ou avec note optionnelle */}
              {canResolveTicket && (
                <>
                  <Button
                    variant="outline"
                    className="rounded-full"
                    disabled={resolveMut.isPending}
                    onClick={() => setShowResolveForm((v) => !v)}
                  >
                    <MessageSquare className="mr-1 h-4 w-4" />
                    Ajouter une note
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={resolveMut.isPending}
                    onClick={() => resolveMut.mutate()}
                  >
                    {resolveMut.isPending
                      ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                      : <CheckCircle2 className="mr-1 h-4 w-4" />}
                    Marquer résolue
                  </Button>
                </>
              )}
            </div>
          )
        )}
      </header>

      {!isRequesterView && (
        <TicketComplianceTrace
          request={r}
          assigneeName={assigneeUser?.name}
        />
      )}

      {isRequesterView && (
        <section className="border-t border-border/40 bg-muted/10 px-5 py-4 sm:px-6">
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Avancement de votre demande
          </h3>
          <EscalationProgressBar
            steps={buildRequesterStepsFromStatus(r.status, { rejected: r.status === "rejected" })}
          />
        </section>
      )}

      <div className="grid border-t border-border/40 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-5 p-4 sm:p-5 lg:p-6">

          {/* P10 — Bandeau PENDING */}
          {isRequesterView && r.status === "pending" && (
            <GlassCard className="border-amber-500/30 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-amber-600 dark:text-amber-400">
                    Votre retour est attendu
                  </h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    L'agent en charge de votre demande attend des informations complémentaires.
                    Répondez dès que possible pour débloquer le traitement.
                  </p>
                  <Button
                    size="sm"
                    className="mt-3 rounded-full gradient-primary"
                    onClick={() => {
                      commentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                      commentRef.current?.focus();
                    }}
                  >
                    Répondre
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {/* P7 — Formulaire de modification (demandeur, status=new uniquement) */}
          {showEditForm && canEdit && (
            <GlassCard className="border-primary/30 bg-primary/5">
              <h3 className="mb-1 font-semibold">Modifier la demande</h3>
              <p className="mb-4 text-xs text-muted-foreground">
                Si vous changez la catégorie, la demande sera automatiquement re-routée vers le service concerné.
              </p>
              <div className="space-y-3">
                <div>
                  <Label className="text-sm">Titre</Label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="mt-1.5 w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label className="text-sm">Catégorie</Label>
                    <Select value={editCategory} onValueChange={setEditCategory}>
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une catégorie" />
                      </SelectTrigger>
                      <SelectContent>
                        {activeCategories.map((c) => (
                          <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm">Priorité</Label>
                    <Select value={editPriority} onValueChange={setEditPriority}>
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une priorité" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="low">Basse</SelectItem>
                        <SelectItem value="medium">Moyenne</SelectItem>
                        <SelectItem value="high">Haute</SelectItem>
                        <SelectItem value="critical">Critique</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <Label className="text-sm">Direction destinataire</Label>
                    <Select
                      value={editDirectionId}
                      onValueChange={(v) => {
                        setEditDirectionId(v);
                        setEditServiceId("");
                      }}
                    >
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue placeholder="Sélectionner une direction" />
                      </SelectTrigger>
                      <SelectContent>
                        {directions.filter((d) => d.status).map((d) => (
                          <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label className="text-sm">Service destinataire</Label>
                    <Select
                      value={editServiceId}
                      onValueChange={setEditServiceId}
                      disabled={!editDirectionId || editUnits.filter((u) => u.status).length === 0}
                    >
                      <SelectTrigger className="mt-1.5 h-11">
                        <SelectValue
                          placeholder={
                            !editDirectionId
                              ? "Choisissez une direction"
                              : "Service optionnel"
                          }
                        />
                      </SelectTrigger>
                      <SelectContent>
                        {editUnits.filter((u) => u.status).map((u) => (
                          <SelectItem key={u.id} value={String(u.id)}>{u.name}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div>
                  <Label className="text-sm">Description détaillée</Label>
                  <textarea
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={4}
                    className="mt-1.5 w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-1">
                  <Button size="sm" variant="ghost" className="rounded-full"
                    onClick={() => setShowEditForm(false)}>
                    Annuler
                  </Button>
                  <Button
                    size="sm"
                    className="rounded-full gradient-primary"
                    disabled={
                      !editTitle.trim() ||
                      !editCategory ||
                      !editPriority ||
                      !editDirectionId ||
                      editDescription.trim().length < 10 ||
                      editMut.isPending
                    }
                    onClick={() => editMut.mutate()}
                  >
                    {editMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-1.5 h-4 w-4" />}
                    Enregistrer &amp; re-router
                  </Button>
                </div>
              </div>
            </GlassCard>
          )}

          {/* P7 — Confirmation annulation */}
          {showCancelConfirm && (
            <GlassCard className="border-destructive/30 bg-destructive/5">
              <div className="flex items-start gap-3">
                <Ban className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0 flex-1 space-y-3">
                  <h3 className="font-semibold text-destructive">Annuler cette demande ?</h3>
                  <p className="text-sm text-muted-foreground">
                    Cette action est irréversible. La demande sera marquée comme annulée et ne sera plus traitée.
                  </p>
                  <textarea
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Motif de l'annulation…"
                    rows={2}
                    className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive/40"
                  />
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" className="rounded-full"
                      onClick={() => { setShowCancelConfirm(false); setCancelReason(""); }}>
                      Garder la demande
                    </Button>
                    <Button
                      size="sm"
                      variant="destructive"
                      className="rounded-full"
                      disabled={!cancelReason.trim() || cancelMut.isPending}
                      onClick={() => cancelMut.mutate()}
                    >
                      {cancelMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Ban className="mr-1.5 h-4 w-4" />}
                      Confirmer l'annulation
                    </Button>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* C2 — Formulaire demande d'informations */}
          {!isRequesterView && showRequestInfoForm && (
            <GlassCard className="border-amber-500/30 bg-amber-500/5">
              <div className="flex items-start gap-3">
                <MessageSquareWarning className="mt-0.5 h-5 w-5 shrink-0 text-amber-500" />
                <div className="min-w-0 flex-1 space-y-3">
                  <h3 className="font-semibold text-amber-600 dark:text-amber-400">
                    Demander des informations complémentaires
                  </h3>
                  <p className="text-sm text-muted-foreground">
                    Le demandeur recevra une notification. Le ticket passera en attente jusqu'à sa réponse.
                  </p>
                  <textarea
                    value={infoQuestion}
                    onChange={(e) => setInfoQuestion(e.target.value)}
                    placeholder="Posez votre question ou décrivez les informations manquantes…"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-amber-500/30 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/40"
                  />
                  <div className="flex justify-end gap-2">
                    <Button size="sm" variant="ghost" className="rounded-full"
                      onClick={() => { setShowRequestInfoForm(false); setInfoQuestion(""); }}>
                      Annuler
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-full bg-amber-500 text-white hover:bg-amber-600"
                      disabled={!infoQuestion.trim() || requestInfoMut.isPending}
                      onClick={() => requestInfoMut.mutate()}
                    >
                      {requestInfoMut.isPending
                        ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                        : <MessageSquareWarning className="mr-1.5 h-4 w-4" />}
                      Envoyer la demande
                    </Button>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {/* C5 — Modal escalade */}
          {!isRequesterView && (
            <Dialog
              open={showEscalateForm}
              onOpenChange={(open) => {
                if (!open) { setShowEscalateForm(false); setEscalateReason(""); }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <ArrowUpRight className="h-5 w-5" />
                    Escalader la demande
                  </DialogTitle>
                  <DialogDescription>
                    Transférez cette demande à un niveau hiérarchique supérieur.
                    Le motif sera enregistré dans l'historique.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">Niveau cible</label>
                    <Select value={escalateLevel} onValueChange={setEscalateLevel}>
                      <SelectTrigger className="h-10">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(escalationLevelsRef.length > 0
                          ? escalationLevelsRef.map((l) => l.label)
                          : DEFAULT_LEVELS.slice(3, 6)
                        ).map((l) => (
                          <SelectItem key={l} value={l}>{l}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Motif <span className="text-destructive">*</span>
                    </label>
                    <textarea
                      value={escalateReason}
                      onChange={(e) => setEscalateReason(e.target.value)}
                      placeholder="Décrivez la raison de l'escalade…"
                      rows={3}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive/40"
                    />
                  </div>
                </div>

                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowEscalateForm(false); setEscalateReason(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="destructive"
                    className="rounded-full"
                    disabled={!escalateReason.trim() || escalateMut.isPending}
                    onClick={() => escalateMut.mutate()}
                  >
                    {escalateMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <ArrowUpRight className="mr-1.5 h-4 w-4" />}
                    Confirmer l'escalade
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* C4 — Note de résolution optionnelle */}
          {showResolveForm && (
            <div className="space-y-2 rounded-2xl border border-primary/20 bg-primary/5 px-4 py-3">
              <Label htmlFor="resolution-note" className="text-sm font-medium">
                Note de résolution (optionnelle)
              </Label>
              <Textarea
                id="resolution-note"
                value={resolutionNote}
                onChange={(e) => setResolutionNote(e.target.value)}
                placeholder="Décrivez comment la demande a été résolue…"
                className="min-h-20 bg-background"
              />
              <p className="text-xs text-muted-foreground">
                Cette note sera ajoutée à l'historique des commentaires (visible en interne uniquement).
              </p>
              <div className="flex justify-end gap-2">
                <Button size="sm" variant="ghost" className="h-8 rounded-full px-3 text-xs"
                  onClick={() => { setShowResolveForm(false); setResolutionNote(""); }}>
                  Annuler
                </Button>
                <Button size="sm" className="h-8 rounded-full gradient-primary px-4 text-xs"
                  disabled={resolveMut.isPending} onClick={() => resolveMut.mutate()}>
                  {resolveMut.isPending
                    ? <Loader2 className="mr-1 h-3 w-3 animate-spin" />
                    : <CheckCircle2 className="mr-1 h-3 w-3" />}
                  Confirmer la résolution
                </Button>
              </div>
            </div>
          )}

          {/* Director — Confirmation rejet inline (1 clic) */}
          {canRejectTicket && showRejectConfirm && (
            <div className="space-y-3 rounded-2xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm">
              <div className="flex items-center gap-2">
                <Ban className="h-4 w-4 shrink-0 text-destructive" />
                <span className="font-medium text-destructive">Motif du rejet de cette demande</span>
              </div>
              <Textarea
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                placeholder="Expliquez clairement pourquoi cette demande est rejetée…"
                className="min-h-20 bg-background"
              />
              <div className="flex justify-end gap-2">
                <Button size="sm" variant="ghost" className="h-8 rounded-full px-3 text-xs"
                  onClick={() => { setShowRejectConfirm(false); setRejectNote(""); }}>
                  Annuler
                </Button>
                <Button size="sm" variant="destructive" className="h-8 rounded-full px-3 text-xs"
                  disabled={!rejectNote.trim() || rejectMut.isPending} onClick={() => rejectMut.mutate()}>
                  {rejectMut.isPending ? <Loader2 className="mr-1 h-3 w-3 animate-spin" /> : null}
                  Rejeter
                </Button>
              </div>
            </div>
          )}

          {canRejectReopen && (
            <Dialog
              open={showRejectReopenConfirm}
              onOpenChange={(open) => {
                if (!open) {
                  setShowRejectReopenConfirm(false);
                  setRejectReopenNote("");
                }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <XCircle className="h-5 w-5" />
                    Refuser la réouverture
                  </DialogTitle>
                  <DialogDescription>
                    Le ticket restera dans son état actuel. Le motif sera visible dans l'historique.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  <Label htmlFor="reject-reopen-note" className="text-sm font-medium">
                    Motif du refus <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="reject-reopen-note"
                    value={rejectReopenNote}
                    onChange={(e) => setRejectReopenNote(e.target.value)}
                    placeholder="Expliquez pourquoi la réouverture est refusée…"
                    className="min-h-24 bg-background"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => {
                      setShowRejectReopenConfirm(false);
                      setRejectReopenNote("");
                    }}
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="destructive"
                    className="rounded-full"
                    disabled={!rejectReopenNote.trim() || rejectReopenMut.isPending}
                    onClick={() => rejectReopenMut.mutate()}
                  >
                    {rejectReopenMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <XCircle className="mr-1.5 h-4 w-4" />}
                    Refuser la réouverture
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}


          <div className="overflow-hidden rounded-2xl border border-border/40 bg-background/35">
            <section className="p-5">
              <h3 className="mb-2 font-semibold">Description</h3>
              <p className="text-sm leading-6 text-muted-foreground">{r.description}</p>
            </section>

            <section className="border-t border-border/40 p-5">
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <h3 className="font-semibold">Journal complet</h3>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
                  Actions · commentaires · statuts
                </span>
              </div>
              <WorkflowTimeline events={r.timeline} />
            </section>

            <section className="border-t border-border/40 p-5">
            <h3 className="mb-4 font-semibold">Commentaires</h3>
            {visibleComments.length === 0 && (
              <p className="text-sm text-muted-foreground">Aucun commentaire pour l'instant.</p>
            )}
            <ul className="space-y-3">
              {visibleComments.map((c) => (
                <li
                  key={c.id}
                  className="rounded-2xl border border-border/50 bg-background/60 p-4"
                >
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    <span>
                      <strong className="text-foreground">{c.author}</strong> ·{" "}
                      {formatDistanceToNow(new Date(c.createdAt), { addSuffix: true, locale: fr })}
                    </span>
                    {!isRequesterView && (
                      c.isPublic ? (
                        <span className="rounded-full bg-info/15 px-2 py-0.5 text-[10px] text-info">
                          Visible public
                        </span>
                      ) : (
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px]">Interne</span>
                      )
                    )}
                  </div>
                  <p className="mt-2 text-sm">{c.body}</p>
                </li>
              ))}
            </ul>

            {isArchived || r.status === "closed" || r.status === "rejected" ? (
              <div className="mt-5 flex items-center gap-2 rounded-xl border border-border/30 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
                <Lock className="h-3.5 w-3.5 shrink-0" />
                Les commentaires sont désactivés — ticket {isArchived ? "archivé" : r.status === "closed" ? "clôturé" : "rejeté"}.
              </div>
            ) : (
              <div className="mt-5 space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                <Textarea
                  ref={commentRef}
                  placeholder={isRequesterView ? "Ajouter une réponse ou un commentaire…" : "Ajouter un commentaire…"}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  className="min-h-24"
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  {!isRequesterView ? (
                    <div className="flex items-center gap-2">
                      <Switch id="public" checked={isPublic} onCheckedChange={setIsPublic} />
                      <Label htmlFor="public" className="text-sm">
                        Visible par le demandeur
                      </Label>
                    </div>
                  ) : <div />}
                  <div className="flex gap-2">
                    <input
                      ref={attachRef}
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,.heic,.pdf"
                      className="hidden"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) attachCommentMut.mutate(f);
                      }}
                    />
                    <Button
                      variant="ghost"
                      size="sm"
                      className="rounded-full"
                      disabled={attachCommentMut.isPending}
                      onClick={() => attachRef.current?.click()}
                    >
                      {attachCommentMut.isPending
                        ? <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                        : <Paperclip className="mr-1 h-4 w-4" />}
                      Joindre
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-full gradient-primary"
                      disabled={!comment.trim() || commentMut.isPending}
                      onClick={() => commentMut.mutate()}
                    >
                      {commentMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Publier"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
            </section>
          </div>


          {/* ── Panneau rejet (demandeur uniquement) ── */}
          {iAmRequester && r.status === "rejected" && (
            <GlassCard className="space-y-4 border-destructive/30 bg-destructive/5">
              <div className="flex items-start gap-3">
                <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-destructive">Demande rejetée</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Votre demande a été examinée et n'a pas pu être traitée dans son état actuel.
                    Consultez l'historique ci-dessus pour connaître le motif précis du rejet.
                  </p>
                  {/* Dernier événement du timeline = motif du rejet */}
                  {r.timeline.length > 0 && (
                    <div className="mt-3 rounded-xl border border-destructive/20 bg-background/50 px-4 py-3 text-sm">
                      <span className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Motif
                      </span>
                      <p className="mt-1 text-foreground">
                        {r.timeline[r.timeline.length - 1].label}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              <div className="border-t border-border/30 pt-4 space-y-3">
                <p className="text-xs text-muted-foreground">
                  Si votre situation a évolué ou si vous pensez que ce rejet est injustifié,
                  vous pouvez réouvrir cette demande. L'historique complet sera conservé.
                </p>

                {!showReopenForm ? (
                  <Button
                    variant="outline"
                    className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60"
                    onClick={() => setShowReopenForm(true)}
                  >
                    <RotateCcw className="mr-1.5 h-4 w-4" />
                    Réouvrir la demande
                  </Button>
                ) : (
                  <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                    <p className="text-sm font-medium">
                      Motif de la réouverture <span className="text-destructive">*</span>
                    </p>
                    <textarea
                      value={reopenReason}
                      onChange={(e) => setReopenReason(e.target.value)}
                      placeholder="Décrivez ce qui a changé ou pourquoi vous contestez le rejet…"
                      rows={3}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                    <div className="flex justify-end gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="rounded-full"
                        onClick={() => { setShowReopenForm(false); setReopenReason(""); }}
                      >
                        Annuler
                      </Button>
                      <Button
                        size="sm"
                        className="rounded-full gradient-primary"
                        disabled={requestReopenMut.isPending || !reopenReason.trim()}
                        onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                      >
                        {requestReopenMut.isPending
                          ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                          : <RotateCcw className="mr-1.5 h-4 w-4" />
                        }
                        Demander la réouverture
                      </Button>
                    </div>
                  </div>
                )}
              </div>
            </GlassCard>
          )}

          {iAmRequester && r.status === "resolved" && (
            <GlassCard className={
              (r.infos as Record<string, unknown>)?.reopen_requested
                ? "border-warning/30 bg-warning/5"
                : "border-success/30 bg-success/5"
            }>
              <div className="flex items-start gap-3">
                {(r.infos as Record<string, unknown>)?.reopen_requested
                  ? <RotateCcw className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                  : <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-success" />
                }
                <div className="min-w-0 flex-1 space-y-3">
                  {(r.infos as Record<string, unknown>)?.reopen_requested ? (
                    /* Réouverture déjà demandée — en attente chef */
                    <div>
                      <h3 className="font-semibold text-warning">Réouverture en attente d'approbation</h3>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Votre demande de réouverture a été transmise au chef de service.
                        Vous serez notifié dès qu'une décision sera prise.
                      </p>
                    </div>
                  ) : (
                    <>
                      <div>
                        <h3 className="font-semibold text-success">Demande résolue</h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          L'agent a marqué votre demande comme résolue. Confirmez si le problème est
                          bien réglé, ou contestez la résolution en précisant le motif.
                        </p>
                        <div className={`mt-2 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
                          daysUntilAutoClose <= 1
                            ? "bg-destructive/10 text-destructive"
                            : "bg-warning/10 text-warning-foreground"
                        }`}>
                          <Clock className="h-3 w-3" />
                          {daysUntilAutoClose === 0
                            ? "Fermeture automatique aujourd'hui"
                            : `Fermeture automatique dans ${daysUntilAutoClose} jour${daysUntilAutoClose > 1 ? "s" : ""}`}
                        </div>
                      </div>
                      {!showReopenForm ? (
                        <div className="flex flex-wrap gap-2">
                          {canClose && (
                            <Button
                              size="sm"
                              className="rounded-full"
                              disabled={closeMut.isPending}
                              onClick={() => closeMut.mutate()}
                            >
                              {closeMut.isPending
                                ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                : <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />}
                              Confirmer la résolution
                            </Button>
                          )}
                          {canRequestReopen && (
                            <Button
                              size="sm"
                              variant="outline"
                              className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10"
                              onClick={() => setShowReopenForm(true)}
                            >
                              <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                              Le problème persiste — contester
                            </Button>
                          )}
                        </div>
                      ) : (
                        <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                          <div>
                            <p className="text-sm font-medium">
                              Motif de contestation <span className="text-destructive">*</span>
                            </p>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              Obligatoire — décrivez précisément ce qui n'a pas été résolu.
                            </p>
                          </div>
                          <textarea
                            value={reopenReason}
                            onChange={(e) => setReopenReason(e.target.value)}
                            placeholder="Ex : La panne a repris le lendemain, le problème n'est pas résolu…"
                            rows={3}
                            className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                          />
                          <div className="flex justify-end gap-2">
                            <Button size="sm" variant="ghost" className="rounded-full"
                              onClick={() => { setShowReopenForm(false); setReopenReason(""); }}>
                              Annuler
                            </Button>
                            <Button
                              size="sm"
                              className="rounded-full gradient-primary"
                              disabled={requestReopenMut.isPending || !reopenReason.trim()}
                              onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                            >
                              {requestReopenMut.isPending
                                ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                                : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                              Demander la réouverture
                            </Button>
                          </div>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            </GlassCard>
          )}

          {/* ── Carte fermeture (demandeur uniquement) ── */}
          {iAmRequester && r.status === "closed" && (
            <GlassCard className="border-muted/40 bg-muted/5">
              <div className="flex items-start gap-3">
                <Lock className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1 space-y-3">
                  <div>
                    <h3 className="font-semibold">Demande clôturée</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {canReopenClosed
                        ? "Cette demande a été fermée. Si votre problème persiste, vous pouvez encore la rouvrir."
                        : "Cette demande est archivée. La fenêtre de réouverture (7 jours) est expirée — créez une nouvelle demande si nécessaire."}
                    </p>
                  </div>
                  {canRequestReopen && (
                    !showReopenForm ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="rounded-full"
                        onClick={() => setShowReopenForm(true)}
                      >
                        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                        Rouvrir la demande
                      </Button>
                    ) : (
                      <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                        <p className="text-sm font-medium">
                          Motif de réouverture <span className="text-destructive">*</span>
                        </p>
                        <textarea
                          value={reopenReason}
                          onChange={(e) => setReopenReason(e.target.value)}
                          placeholder="Décrivez précisément ce qui n'a pas été résolu…"
                          rows={3}
                          className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                        />
                        <div className="flex justify-end gap-2">
                          <Button size="sm" variant="ghost" className="rounded-full"
                            onClick={() => { setShowReopenForm(false); setReopenReason(""); }}>
                            Annuler
                          </Button>
                          <Button
                            size="sm"
                            className="rounded-full gradient-primary"
                            disabled={requestReopenMut.isPending || !reopenReason.trim()}
                            onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                          >
                            {requestReopenMut.isPending
                              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              : <RotateCcw className="mr-1.5 h-3.5 w-3.5" />}
                            Demander la réouverture
                          </Button>
                        </div>
                      </div>
                    )
                  )}
                </div>
              </div>
            </GlassCard>
          )}

          {isRequesterView && (r.status === "resolved" || r.status === "closed") && (
            <div>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
                Votre avis
              </h3>
              <AppreciationForm
                requestId={r.id}
                authorType={authorType}
                existing={localAppreciation ?? r.appreciation}
                isClosed={r.status === "closed"}
                onSubmit={(appr) => {
                  setLocalAppreciation(appr);
                  invalidate();
                }}
                onReopen={() => {
                  toast.success("Demande rouverte — un agent va la reprendre en charge.");
                  invalidate();
                }}
                onSave={async (data) => {
                  const hasExisting = !!(localAppreciation ?? r.appreciation);
                  if (hasExisting) {
                    await updateRequestAppreciation(r.id, data);
                  } else {
                    await submitAppreciation(r.id, data);
                  }
                }}
              />
            </div>
          )}

          {/* Dialog — Transfert inter-direction */}
          {!isRequesterView && (
            <Dialog
              open={showDirectionTransfer}
              onOpenChange={(open) => {
                setShowDirectionTransfer(open);
                if (!open) {
                  setTransferDirectionId("");
                  setTransferReason("");
                }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />
                    Transférer vers une direction
                  </DialogTitle>
                  <DialogDescription>
                    La demande entrera dans la direction cible comme un ticket à qualifier.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <Label>Direction cible</Label>
                    <select
                      value={transferDirectionId}
                      onChange={(e) => setTransferDirectionId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Choisir une direction</option>
                      {transferDirectionOptions.map((direction) => (
                        <option key={direction.id} value={direction.id}>
                          {direction.name}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>
                      Motif <span className="text-destructive">*</span>
                    </Label>
                    <Textarea
                      value={transferReason}
                      onChange={(e) => setTransferReason(e.target.value)}
                      placeholder="Expliquez pourquoi la demande sort de votre direction…"
                      rows={4}
                    />
                  </div>
                </div>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => setShowDirectionTransfer(false)}
                  >
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={
                      !transferDirectionId ||
                      !transferReason.trim() ||
                      transferDirectionMut.isPending
                    }
                    onClick={() => transferDirectionMut.mutate()}
                  >
                    {transferDirectionMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <Building2 className="mr-1.5 h-4 w-4" />}
                    Transférer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* Dialog — Créer circuit de validation */}
          {!isRequesterView && (
            <Dialog
              open={showCircuitDialog}
              onOpenChange={(open) => { if (!open) { setShowCircuitDialog(false); setCircuitDirectionId(""); setCircuitUnitId(""); } }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <GitBranch className="h-5 w-5 text-primary" />
                    Créer un circuit de validation
                  </DialogTitle>
                  <DialogDescription>
                    Un circuit de validation automatique sera créé pour cette demande.
                    Laissez les champs vides pour utiliser la configuration par défaut.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Direction cible <span className="text-muted-foreground">(optionnel)</span>
                    </label>
                    <select
                      value={circuitDirectionId}
                      onChange={(e) => setCircuitDirectionId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Configuration automatique</option>
                      {directions.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Service cible <span className="text-muted-foreground">(optionnel)</span>
                    </label>
                    <select
                      value={circuitUnitId}
                      onChange={(e) => setCircuitUnitId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Configuration automatique</option>
                      {units
                        .filter((u) => !circuitDirectionId || u.direction_id === circuitDirectionId)
                        .map((u) => (
                          <option key={u.id} value={u.id}>{u.name}</option>
                        ))}
                    </select>
                  </div>
                </div>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowCircuitDialog(false); setCircuitDirectionId(""); setCircuitUnitId(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={createCircuitMut.isPending}
                    onClick={() => createCircuitMut.mutate()}
                  >
                    {createCircuitMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <><GitBranch className="mr-1.5 h-4 w-4" /> Créer le circuit</>
                    }
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}
        </div>

        <aside className="border-t border-border/40 bg-muted/10 lg:border-l lg:border-t-0">
          <div className="divide-y divide-border/40">
          <section className="p-5">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Suivi SLA
            </h3>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-2xl font-bold">{slaPct}%</div>
                <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {r.slaHours > 0
                    ? `${r.slaElapsed}h / ${r.slaHours}h`
                    : "SLA non configuré"}
                </div>
              </div>
              <span
                className={
                  "rounded-full px-2.5 py-0.5 text-xs font-medium " +
                  (slaOver
                    ? "bg-destructive/15 text-destructive"
                    : "bg-success/15 text-success")
                }
              >
                {slaOver ? "Dépassé" : "Dans les temps"}
              </span>
            </div>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={"h-full rounded-full " + (slaOver ? "bg-destructive" : "gradient-primary")}
                style={{ width: slaPct + "%" }}
              />
            </div>
          </section>

          {!isRequesterView && <RequesterCard r={r} directions={directions} />}

          <section className="p-5">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Intervenants
            </h3>
            {participants.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun intervenant enregistré.</p>
            ) : (
              <ul className="space-y-3">
                {participants.map((participant) => (
                  <li key={participant.key} className="flex items-start gap-3">
                    <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {participant.name
                        .split(" ")
                        .map((part) => part[0])
                        .join("")
                        .slice(0, 2)
                        .toUpperCase()}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium" title={participant.name}>
                        {participant.name}
                      </div>
                      <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                        {participant.role && (
                          <span className="rounded-full bg-muted px-2 py-0.5">
                            {participantRoleLabel(participant.role)}
                          </span>
                        )}
                        <span className="truncate" title={participant.detail}>
                          {participant.detail}
                        </span>
                      </div>
                      {participant.lastAt && (
                        <div className="mt-0.5 text-[10px] text-muted-foreground">
                          {formatDistanceToNow(new Date(participant.lastAt), { addSuffix: true, locale: fr })}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="p-5">
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
              Traitement
            </h3>
            <dl className="space-y-3 text-sm">

              {/* Direction + Service côte à côte */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-xs text-muted-foreground flex items-center gap-1">
                    <Building2 className="h-3 w-3" /> Direction
                  </dt>
                  <dd className="mt-0.5 font-medium truncate" title={directionName}>{directionName}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted-foreground">Service</dt>
                  <dd className="mt-0.5 font-medium truncate" title={unitName}>{unitName}</dd>
                </div>
              </div>

              <div className="border-t border-border/30" />

              {/* Catégorie */}
              <div>
                <dt className="text-xs text-muted-foreground">Catégorie</dt>
                <dd className="mt-0.5">{r.category}</dd>
              </div>

              {/* Agent en charge */}
              {isRequesterView && (
                <div>
                  <dt className="text-xs text-muted-foreground">Agent en charge</dt>
                  <dd className="mt-0.5 flex items-center gap-1.5">
                    <UserCheck className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                    {r.assigneeId
                      ? (assigneeUser?.name ?? "En cours d'assignation")
                      : <span className="italic text-muted-foreground">En attente d'assignation</span>}
                  </dd>
                </div>
              )}

              <div className="border-t border-border/30" />

              {/* Dates : création + fin */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <dt className="text-xs text-muted-foreground flex items-center gap-1">
                    <Clock className="h-3 w-3" /> Créé le
                  </dt>
                  <dd className="mt-0.5 text-xs font-medium">
                    {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                  </dd>
                  <dd className="text-[10px] text-muted-foreground">
                    {format(new Date(r.createdAt), "HH:mm", { locale: fr })}
                  </dd>
                </div>
                {["resolved", "closed", "rejected", "cancelled"].includes(r.status) ? (
                  <div>
                    <dt className="text-xs text-muted-foreground flex items-center gap-1">
                      <CheckCircle2 className="h-3 w-3 text-success" />
                      {r.status === "rejected" ? "Rejeté le" : r.status === "cancelled" ? "Annulé le" : "Résolu le"}
                    </dt>
                    <dd className="mt-0.5 text-xs font-medium text-success">
                      {format(new Date(r.updatedAt), "d MMM yyyy", { locale: fr })}
                    </dd>
                    <dd className="text-[10px] text-muted-foreground">
                      {format(new Date(r.updatedAt), "HH:mm", { locale: fr })}
                    </dd>
                  </div>
                ) : (
                  <div>
                    <dt className="text-xs text-muted-foreground flex items-center gap-1">
                      <Clock className="h-3 w-3" /> Mis à jour
                    </dt>
                    <dd className="mt-0.5 text-xs font-medium">
                      {format(new Date(r.updatedAt), "d MMM yyyy", { locale: fr })}
                    </dd>
                    <dd className="text-[10px] text-muted-foreground">
                      {format(new Date(r.updatedAt), "HH:mm", { locale: fr })}
                    </dd>
                  </div>
                )}
              </div>
            </dl>
          </section>

          {slaOver && (
            <section className="bg-destructive/5 p-5">
              <div className="flex items-start gap-3">
                <AlertTriangle className="mt-0.5 h-5 w-5 text-destructive" />
                <div>
                  <div className="font-semibold text-destructive">SLA dépassé</div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Cette demande nécessite une attention immédiate ou une escalade.
                  </p>
                </div>
              </div>
            </section>
          )}
          </div>
        </aside>
      </div>
      </div>
    </div>
  );
}

function RequesterCard({ r: req, directions }: { r: RequestItem; directions: Direction[] }) {
  const [role] = useRole();
  const isAgent = role !== "user";
  const isInternal = req.requesterType === "internal" || !req.isExternal;
  const isExternal = req.requesterType === "external" || req.isExternal;

  return (
    <section className="p-5">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        Fiche demandeur
      </h3>

      <div className="mb-3 flex items-center gap-2">
        <span className="grid h-8 w-8 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary">
          {req.requesterName.split(" ").map((p: string) => p[0]).join("").slice(0, 2)}
        </span>
        <div className="min-w-0">
          <div className="font-semibold leading-none">{req.requesterName}</div>
          <div className="mt-0.5 flex items-center gap-1.5">
            {isInternal ? (
              <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                <BadgeCheck className="h-3 w-3" /> Employé EDG
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground dark:text-accent">
                <Users className="h-3 w-3" /> Client externe / citoyen
              </span>
            )}
          </div>
        </div>
      </div>

      <dl className="space-y-2.5 text-sm">
        {req.requesterPhone && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Phone className="h-3.5 w-3.5 shrink-0" />
            <a href={`tel:${req.requesterPhone}`} className="hover:text-foreground">
              {req.requesterPhone}
            </a>
          </div>
        )}
        {req.requesterEmail && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Mail className="h-3.5 w-3.5 shrink-0" />
            <a href={`mailto:${req.requesterEmail}`} className="truncate hover:text-foreground">
              {req.requesterEmail}
            </a>
          </div>
        )}
        {req.requesterAddress && (
          <div className="flex items-start gap-2 text-muted-foreground">
            <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{req.requesterAddress}</span>
          </div>
        )}

        {isInternal && req.employeeMatricule && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <BadgeCheck className="h-3.5 w-3.5 shrink-0 text-primary" />
            <span>Matricule : <span className="font-mono font-medium text-foreground">{req.employeeMatricule}</span></span>
          </div>
        )}
        {isInternal && req.requesterJob && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <User className="h-3.5 w-3.5 shrink-0" />
            <span>{req.requesterJob}</span>
          </div>
        )}
        {isInternal && req.requesterDirectionId && (
          <div className="flex items-center gap-2 text-muted-foreground">
            <Building2 className="h-3.5 w-3.5 shrink-0" />
            <span>{directions.find((d) => String(d.id) === String(req.requesterDirectionId))?.name ?? req.requesterDirectionId}</span>
          </div>
        )}

        {isExternal && req.meterNumber && (
          <div className="text-xs font-mono text-muted-foreground">
            Compteur : <span className="font-medium text-foreground">{req.meterNumber}</span>
          </div>
        )}
        {isExternal && req.clientRef && (
          <div className="text-xs font-mono text-muted-foreground">
            Réf. client : <span className="font-medium text-foreground">{req.clientRef}</span>
          </div>
        )}
        {isExternal && req.siteType && (
          <div className="text-xs text-muted-foreground">
            Site :{" "}
            <span className="font-medium text-foreground">
              {req.siteType === "domicile" ? "Domicile"
                : req.siteType === "commerce" ? "Commerce / entreprise"
                : "Administration / école"}
            </span>
          </div>
        )}

        {isExternal && isAgent && (req.lat != null || req.locationLabel) && (
          <div className="mt-1 rounded-xl border border-primary/20 bg-primary/5 p-2.5">
            <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
              <MapPin className="h-3 w-3" /> Localisation GPS (confidentiel)
            </div>
            {req.locationLabel && (
              <div className="text-xs text-foreground">{req.locationLabel}</div>
            )}
            {req.lat != null && req.lng != null && (
              <div className="mt-0.5 font-mono text-[10px] text-muted-foreground/70">
                {req.lat.toFixed(5)}, {req.lng.toFixed(5)}
              </div>
            )}
          </div>
        )}
      </dl>
    </section>
  );
}

