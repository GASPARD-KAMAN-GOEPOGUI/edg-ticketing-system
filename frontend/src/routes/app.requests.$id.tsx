import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { WorkflowTimeline } from "@/components/workflow-timeline";
import { InterventionJournal } from "@/components/intervention-journal";
import { useState, useRef, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient, useQueries } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import type { RequestItem, Appreciation } from "@/lib/mock-data";
import { roleLabels } from "@/lib/mock-data";
import { AppreciationForm } from "@/components/appreciation-form";
import { cn } from "@/lib/utils";
import { useRole, useUser } from "@/lib/session";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  fetchRequest,
  resolveRequest,
  transmitTreatment,
  assignRequest,
  createComment,
  deleteComment,
  requestReopen,
  reopenRequest,
  rejectReopenRequest,
  closeRequest,
  updateRequest,
  changeRequestPriority,
  cancelRequest,
  escalateRequest,
  escalateToDirectorRequest,
  uploadAttachment,
  fetchAttachments,
  fetchAttachmentFile,
  rejectTicket,
  reassignService,
  transferDirection,
  requesterEditRequest,
  type RawAttachment,
} from "@/lib/api/requests";
import { fetchRefTable } from "@/lib/api/admin-config";
import { buildAvatarUrl, fetchUser, fetchUsers, type AccountUser } from "@/lib/api/accounts";
import { fetchDirections, fetchDepartments, fetchUnits } from "@/lib/api/directions-units";
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
  Download,
  ExternalLink,
  FileText,
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
  Wrench,
  MessageSquare,
  MessageSquareWarning,
  MoreVertical,
  Smile,
  Star,
  Copy,
  Trash2,
  Tag,
  ZoomIn,
  ZoomOut,
  UserCog,
  Send,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow, format, differenceInDays } from "date-fns";
import { fr } from "date-fns/locale";
import { canTicketAction, isRequester } from "@/lib/capabilities";

export const Route = createFileRoute("/app/requests/$id")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Détail ticket — EDG Support" }] }),
  component: RequestDetail,
  notFoundComponent: () => (
    <div className="mx-auto max-w-md p-10 text-center">
      <h2 className="text-lg font-semibold">Ticket introuvable</h2>
      <Button asChild variant="outline" className="mt-4 rounded-full">
        <Link to="/app/requests">Retour aux tickets</Link>
      </Button>
    </div>
  ),
});

const DETAIL_CONTEXTS = {
  requests: {
    eyebrow: "Mon espace",
    backLabel: "Tous les tickets",
    notFoundBackLabel: "Retour aux tickets",
    backTo: "/app/requests",
  },
  history: {
    eyebrow: "Historique",
    backLabel: "Retour à l'historique",
    notFoundBackLabel: "Retour à l'historique",
    backTo: "/app/history",
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
  transmitted: {
    eyebrow: "Tickets transmis",
    backLabel: "Retour aux tickets transmis",
    notFoundBackLabel: "Retour aux tickets transmis",
    backTo: "/app/transmitted",
  },
  myTickets: {
    eyebrow: "Traitement",
    backLabel: "Retour à mes tickets",
    notFoundBackLabel: "Retour à mes tickets",
    backTo: "/app/my-tickets",
  },
  chiefInbox: {
    eyebrow: "Centre de répartition",
    backLabel: "Retour au centre de répartition",
    notFoundBackLabel: "Retour au centre de répartition",
    backTo: "/app/chief-inbox",
  },
  departmentInbox: {
    eyebrow: "Centre de pilotage",
    backLabel: "Retour au centre de pilotage",
    notFoundBackLabel: "Retour au centre de pilotage",
    backTo: "/app/department-inbox",
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
type DetailTab = "description" | "journal" | "comments" | "files" | "sla" | "treatment";
type DirectTreatmentAction =
  | "approveReopen"
  | "selfAssign"
  | "takeOwnership"
  | "resume"
  | "close";

// BR-TRANSMIT-001 — rôles pouvant devenir/rester "intervenant actuel" d'un ticket
// (cible valide pour une transmission). Doit rester aligné avec TREATING_ROLES
// côté backend (ticket_actions.py).
const TREATING_ROLES = new Set(["agent-support", "chief-service", "chief-departement", "director"]);

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

const COMMENT_EMOJIS = [
  "😀", "😃", "😄", "😁", "😊", "🙂", "😉", "😍", "🤩", "😘",
  "😅", "😂", "🤣", "😇", "🙃", "😜", "🤔", "😐", "😴", "😪",
  "😢", "😭", "😡", "😱", "😳", "🥳", "😷", "🤒", "🤕", "🤗",
  "👍", "👎", "👏", "🙏", "💪", "👌", "✌️", "🤝", "🙌", "🤞",
  "❤️", "🔥", "⭐", "✅", "❌", "⚠️", "❓", "❗", "💡", "📌",
] as const;

const PARTICIPANT_ROLE_LABELS: Record<string, string> = {
  user: "Demandeur",
  "agent-support": "Agent Support",
  "chief-service": "Chef de Service",
  "chief-departement": "Chef de Département",
  director: "Directeur",
  admin: "Admin",
  support: "Support",
};

function participantRoleLabel(role?: string): string | undefined {
  if (!role) return undefined;
  return PARTICIPANT_ROLE_LABELS[role] ?? role;
}

function ParticipantRow({ participant }: { participant: Participant }) {
  return (
    <li className="flex items-start gap-3 rounded-2xl bg-background/30 p-3 transition hover:bg-background/50">
      <span className="relative grid h-10 w-10 shrink-0 place-items-center rounded-full bg-primary/10 text-xs font-bold text-primary ring-2 ring-primary/10">
        {initialsFor(participant.name)}
        <span className="absolute bottom-0 right-0 h-2.5 w-2.5 rounded-full border-2 border-background bg-primary" />
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
  );
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
      role: "agent-support",
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

function formatAttachmentSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "Taille inconnue";
  const units = ["o", "Ko", "Mo", "Go"];
  let value = bytes;
  let index = 0;
  while (value >= 1024 && index < units.length - 1) {
    value /= 1024;
    index += 1;
  }
  const precision = index === 0 || value >= 10 ? 0 : 1;
  return `${value.toFixed(precision)} ${units[index]}`;
}

function attachmentTypeLabel(mimeType: string): string {
  if (mimeType.startsWith("image/")) return "Image";
  if (mimeType === "application/pdf") return "PDF";
  return mimeType || "Fichier";
}

function formatAttachmentDate(value?: string): string {
  if (!value) return "Date inconnue";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date inconnue";
  return format(date, "d MMM yyyy HH:mm", { locale: fr });
}

function initialsFor(value?: string): string {
  if (!value?.trim()) return "??";
  return value
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatCommentDate(value?: string): string {
  if (!value) return "Date inconnue";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date inconnue";
  return format(date, "d MMM yyyy 'à' HH:mm", { locale: fr });
}

function formatTicketDateTime(value?: string): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return format(date, "d MMM yyyy HH:mm", { locale: fr });
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

const FIXED_LIFECYCLE_STEPS = [
  { key: "opening", label: "Ouverture" },
  { key: "qualification", label: "Qualification" },
  { key: "treatment", label: "Traitement" },
  { key: "validation", label: "Valider" },
  { key: "closure", label: "Fermeture" },
] as const;

type FixedStepState = "done" | "active" | "pending" | "warning";

// Position (0-4) du statut courant dans le cycle de vie fixe CDC
// Ouverture -> Qualification -> Traitement -> Validation -> Fermeture.
const STATUS_STEP_INDEX: Record<string, number> = {
  new: 0,
  qualifying: 1,
  qualified: 2,
  assigned: 2,
  in_progress: 2,
  pending: 2,
  escalated: 2,
  reopened: 2,
  resolved: 3,
  closed: 4,
  rejected: 2,
  cancelled: 2,
};

function buildFixedLifecycleSteps(request: RequestItem) {
  const events = request.timeline ?? [];
  const status = request.status;
  const isRejectedOrCancelled = status === "rejected" || status === "cancelled";

  const creationEvent = findFirstTraceEvent(events, (event) => normalizeTraceValue(event.type).includes("created"));
  const qualificationEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return type.includes("qualif") || type.includes("routed") || text.includes("qualif") || text.includes("orient");
  });
  const treatmentEvent = findLatestTraceEvent(events, (event) => {
    const text = traceEventText(event);
    const type = normalizeTraceValue(event.type);
    return type.includes("assign") || type.includes("in_progress") || text.includes("prise en charge");
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

  const stepDates = [
    creationEvent?.at ?? request.createdAt,
    qualificationEvent?.at,
    treatmentEvent?.at,
    resolvedEvent?.at ?? request.resolvedAt,
    closedEvent?.at ?? request.closedAt,
  ];
  const currentIndex = STATUS_STEP_INDEX[status] ?? 0;
  const isTerminalDone = status === "closed";

  return FIXED_LIFECYCLE_STEPS.map((step, index) => {
    let state: FixedStepState;
    if (index < currentIndex || (isTerminalDone && index === currentIndex)) state = "done";
    else if (index === currentIndex) state = isRejectedOrCancelled ? "warning" : "active";
    else state = "pending";

    const dateLabel =
      state === "done" ? (formatTraceDate(stepDates[index]) ?? "—")
      : state === "warning" ? (DETAIL_STATUS_LABELS[status] ?? status)
      : state === "active" ? "En cours"
      : "—";

    return { ...step, state, dateLabel };
  });
}

function TicketLifecycleStepper({ request }: { request: RequestItem }) {
  const steps = buildFixedLifecycleSteps(request);

  return (
    <section className="px-3 pb-3 sm:px-5 sm:pb-4">
      <div className="overflow-hidden rounded-[16px] border border-border/50 bg-background/35 px-2 py-3 shadow-inner sm:px-4 sm:py-3.5">
        <ol className="grid w-full grid-cols-5 items-start">
          {steps.map((step, index) => {
            const isLast = index === steps.length - 1;
            return (
              <li key={step.key} className="relative min-w-0">
                {!isLast && (
                  <span className={cn(
                    "absolute left-[calc(50%+0.875rem)] right-[calc(-50%+0.875rem)] top-3.5 h-0 border-t-2 sm:left-[calc(50%+1rem)] sm:right-[calc(-50%+1rem)] sm:top-4",
                    step.state === "done" ? "border-solid border-emerald-500" : "border-dashed border-border",
                  )} />
                )}
                <div className="relative z-10 flex min-w-0 flex-col items-center text-center">
                  <span className={cn(
                    "grid h-7 w-7 place-items-center rounded-full border text-[11px] font-semibold shadow-sm sm:h-8 sm:w-8 sm:text-xs",
                    step.state === "done" && "border-emerald-500 bg-emerald-500 text-white shadow-emerald-500/25",
                    step.state === "active" && "border-primary bg-primary text-primary-foreground shadow-primary/25",
                    step.state === "warning" && "border-amber-500 bg-amber-500 text-white shadow-amber-500/25",
                    step.state === "pending" && "border-border/70 bg-background/60 text-muted-foreground",
                  )}>
                    {step.state === "done" ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className="mt-1.5 max-w-[3.25rem] text-[8px] font-semibold leading-tight text-foreground min-[420px]:max-w-[4.5rem] min-[420px]:text-[9px] sm:max-w-24 sm:text-[11px]">
                    {step.label}
                  </span>
                  <span className="mt-0.5 max-w-[3.25rem] truncate text-[8px] leading-tight text-muted-foreground min-[420px]:max-w-[4.5rem] min-[420px]:text-[9px] sm:max-w-24 sm:text-[10px]">
                    {step.dateLabel}
                  </span>
                </div>
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
  const deepLinkSearch = useSearch({ strict: false }) as { tab?: string };
  const wantsCommentsDeepLink = deepLinkSearch.tab === "comments";
  const qc = useQueryClient();
  const sessionUser = useUser();
  const authorId = Number(sessionUser?.id ?? 0);
  const authorName = [sessionUser?.firstname, sessionUser?.name].filter(Boolean).join(" ") || "Agent";
  const includeDeleted = context === "admin";
  const requestQueryKey = ["request", id, includeDeleted ? "with-deleted" : "active"] as const;
  const attachmentsQueryKey = [...requestQueryKey, "attachments"] as const;

  const { data: r, isLoading, isError } = useQuery({
    queryKey: requestQueryKey,
    queryFn: () => fetchRequest(id, { includeDeleted }),
    staleTime: 15_000,
  });

  const { data: attachments = [], isLoading: attachmentsLoading } = useQuery({
    queryKey: attachmentsQueryKey,
    queryFn: () => fetchAttachments(id),
    enabled: !!r?.id,
    staleTime: 30_000,
  });

  const [comment, setComment] = useState("");
  const [replyTarget, setReplyTarget] = useState<string | null>(null);
  const [replyToId, setReplyToId] = useState<string | null>(null);
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [isPublic, setIsPublic] = useState(false);
  const [isDirective, setIsDirective] = useState(false);
  const [role] = useRole();
  // Dans "Mes demandes", le propriétaire garde la vue demandeur. Dans les espaces
  // métier, le contexte fonctionnel prime sur la propriété personnelle du ticket.
  const iAmRequester = isRequester(r?.requesterId, sessionUser?.id);
  const isRequesterView = role === "user" || (isPersonalContext && iAmRequester);
  const isAgentOnly = role === "agent-support" && !iAmRequester;
  const [localAppreciation, setLocalAppreciation] = useState<Appreciation | undefined>(undefined);
  const [showReassign, setShowReassign] = useState(false);
  const [reopenReason, setReopenReason] = useState("");
  const [showReopenForm, setShowReopenForm] = useState(false);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);
  const [cancelReason, setCancelReason] = useState("");
  const [showRequestInfoForm, setShowRequestInfoForm] = useState(false);
  const [infoQuestion, setInfoQuestion] = useState("");
  // BR-TRANSMIT-001 — "Terminer le traitement" : résumé/solution/travail réalisé
  // obligatoires pour tout intervenant actuel (remplace l'ancienne note optionnelle).
  const [showResolveForm, setShowResolveForm] = useState(false);
  const [resolveSummary, setResolveSummary] = useState("");
  const [resolveSolution, setResolveSolution] = useState("");
  const [resolveWorkDone, setResolveWorkDone] = useState("");
  const [resolveRecommendations, setResolveRecommendations] = useState("");
  // BR-TRANSMIT-001 — "Transmettre le traitement" : annuaire libre (direction/
  // département/service/recherche), motif + travail effectué obligatoires.
  const [showTransmitForm, setShowTransmitForm] = useState(false);
  const [transmitDirectionId, setTransmitDirectionId] = useState("");
  const [transmitDepartmentId, setTransmitDepartmentId] = useState("");
  const [transmitUnitId, setTransmitUnitId] = useState("");
  const [transmitSearch, setTransmitSearch] = useState("");
  const [transmitTargetId, setTransmitTargetId] = useState("");
  const [transmitWorkDone, setTransmitWorkDone] = useState("");
  const [transmitReason, setTransmitReason] = useState("");
  const [transmitInstruction, setTransmitInstruction] = useState("");
  const resetTransmitForm = () => {
    setTransmitDirectionId("");
    setTransmitDepartmentId("");
    setTransmitUnitId("");
    setTransmitSearch("");
    setTransmitTargetId("");
    setTransmitWorkDone("");
    setTransmitReason("");
    setTransmitInstruction("");
  };
  const [showEscalateForm, setShowEscalateForm] = useState(false);
  const [escalateReason, setEscalateReason] = useState("");
  // Lot 3.3 — "Escalade exceptionnelle" (chief-departement uniquement).
  const [showEscalateToDirectorForm, setShowEscalateToDirectorForm] = useState(false);
  const [escalateToDirectorReason, setEscalateToDirectorReason] = useState("");
  const attachRef = useRef<HTMLInputElement>(null);
  const commentRef = useRef<HTMLTextAreaElement>(null);
  const commentsPanelRef = useRef<HTMLElement>(null);
  const insertEmoji = (emoji: string) => {
    const textarea = commentRef.current;
    const start = textarea?.selectionStart ?? comment.length;
    const end = textarea?.selectionEnd ?? comment.length;
    setComment((prev) => `${prev.slice(0, start)}${emoji}${prev.slice(end)}`);
    setEmojiPickerOpen(false);
    requestAnimationFrame(() => {
      textarea?.focus();
      const caret = start + emoji.length;
      textarea?.setSelectionRange(caret, caret);
    });
  };
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
  const [showClosedRequestDialog, setShowClosedRequestDialog] = useState(false);
  const [showAppreciationDialog, setShowAppreciationDialog] = useState(false);
  const [directTreatmentAction, setDirectTreatmentAction] =
    useState<DirectTreatmentAction | null>(null);
  const [circuitDirectionId, setCircuitDirectionId] = useState("");
  const [circuitUnitId, setCircuitUnitId] = useState("");
  // Espaces de traitement (queue, boîtes de chef, supervision, direction…) :
  // on ouvre directement sur "Traitement" puisque c'est là que se trouvent
  // désormais les actions (déplacées depuis les boutons de la card liste).
  // Le contexte personnel ("Mes demandes") reste sur la description.
  const [activeDetailTab, setActiveDetailTab] = useState<DetailTab>(
    wantsCommentsDeepLink ? "comments" : isPersonalContext ? "journal" : "treatment",
  );
  const [showAllParticipants, setShowAllParticipants] = useState(false);
  const [showAllDetails, setShowAllDetails] = useState(false);
  // BR-TRACE-001 — journal hiérarchique (Cycle -> Intervention) par défaut,
  // avec bascule vers la vue chronologique événement par événement existante.
  const [journalView, setJournalView] = useState<"interventions" | "events">("interventions");
  const [attachmentAction, setAttachmentAction] = useState<{
    id: string;
    mode: "open" | "download";
  } | null>(null);
  const [previewFile, setPreviewFile] = useState<{
    url: string;
    filename: string;
    mimeType: string;
  } | null>(null);
  const [previewZoom, setPreviewZoom] = useState(1);

  useEffect(() => {
    return () => {
      if (previewFile) URL.revokeObjectURL(previewFile.url);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!wantsCommentsDeepLink || !r) return;
    setActiveDetailTab("comments");
    const frame = requestAnimationFrame(() => {
      commentsPanelRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      commentRef.current?.focus();
    });
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantsCommentsDeepLink, r]);

  const closePreview = () => {
    setPreviewFile((current) => {
      if (current) URL.revokeObjectURL(current.url);
      return null;
    });
    setPreviewZoom(1);
  };

  const invalidate = () => {
    // Détail du ticket (et sous-queries via préfixe)
    qc.invalidateQueries({ queryKey: requestQueryKey });
    qc.invalidateQueries({ queryKey: attachmentsQueryKey });
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

  const handleAttachmentFile = async (
    attachment: RawAttachment,
    mode: "open" | "download",
  ) => {
    setAttachmentAction({ id: attachment.id, mode });

    try {
      const { blob, filename, contentType } = await fetchAttachmentFile(attachment);
      const url = URL.createObjectURL(blob);

      if (mode === "open") {
        setPreviewZoom(1);
        setPreviewFile({ url, filename, mimeType: contentType ?? attachment.mime_type });
        return;
      }

      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1_000);
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      toast.error(message ? `Impossible d'accéder à la pièce jointe : ${message}` : "Impossible d'accéder à la pièce jointe.");
    } finally {
      setAttachmentAction(null);
    }
  };

  const handleTimelineAttachmentOpen = (attachmentRef: { id?: string; filename?: string }) => {
    setActiveDetailTab("files");

    const attachment =
      attachments.find((item) => item.id === attachmentRef.id) ??
      attachments.find((item) => item.filename === attachmentRef.filename);

    if (!attachment) {
      toast.error(
        attachmentsLoading
          ? "Les pièces jointes sont encore en cours de chargement."
          : "Pièce jointe introuvable dans l'onglet Fichiers.",
      );
      return;
    }

    void handleAttachmentFile(attachment, "open");
  };

  const resolveMut = useMutation({
    // BR-TRANSMIT-001 — "Terminer le traitement" : résumé/solution/travail réalisé
    // obligatoires pour tout intervenant actuel, quel que soit son rôle.
    mutationFn: () => resolveRequest(id, {
      summary: resolveSummary.trim(),
      solution: resolveSolution.trim(),
      work_done: resolveWorkDone.trim(),
      recommendations: resolveRecommendations.trim() || undefined,
    }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "resolved" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Traitement terminé — le ticket est résolu.");
      setShowResolveForm(false);
      setResolveSummary("");
      setResolveSolution("");
      setResolveWorkDone("");
      setResolveRecommendations("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de terminer le traitement.");
    },
    onSettled: () => invalidate(),
  });

  const transmitMut = useMutation({
    // BR-TRANSMIT-001 — "Transmettre le traitement" : cible libre dans toute
    // l'organisation, motif + travail effectué obligatoires, statut préservé.
    mutationFn: () => transmitTreatment(id, {
      to_user_id: transmitTargetId,
      work_done: transmitWorkDone.trim(),
      reason: transmitReason.trim(),
      instruction: transmitInstruction.trim() || undefined,
    }),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      return { previous };
    },
    onSuccess: () => {
      toast.success("Traitement transmis avec succès.");
      setShowTransmitForm(false);
      resetTransmitForm();
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de transmettre le traitement.");
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
      toast.error("Impossible de réassigner le ticket.");
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
      setDirectTreatmentAction(null);
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
      setShowClosedRequestDialog(false);
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
      setDirectTreatmentAction(null);
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
      toast.success("Ticket clôturé — merci pour votre retour.");
      setDirectTreatmentAction(null);
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de clôturer le ticket.");
    },
    onSettled: () => invalidate(),
  });

  const editMut = useMutation({
    mutationFn: () => requesterEditRequest(id, {
      title: editTitle.trim() || undefined,
      description: editDescription.trim() || undefined,
    }),
    onSuccess: () => {
      toast.success("Ticket modifié.");
      setShowEditForm(false);
      invalidate();
    },
    onError: (err: unknown) => {
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible de modifier le ticket.");
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
      toast.success("Ticket annulé.");
      setShowCancelConfirm(false);
      setCancelReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'annuler le ticket.");
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
    onSuccess: () => {
      toast.success("Ticket pris en charge — traitement en cours.");
      setDirectTreatmentAction(null);
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de prendre en charge le ticket.");
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
      return updateRequest(id, { request_status: "pending", status_reason: "info_request" });
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
    onSuccess: () => {
      toast.success("Traitement repris.");
      setDirectTreatmentAction(null);
    },
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
    onSuccess: () => { toast.success("Ticket rejeté."); setShowRejectConfirm(false); setRejectNote(""); },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de rejeter le ticket.");
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
      toast.success(`Ticket transféré vers ${target?.name ?? "la direction cible"}.`);
      setShowDirectionTransfer(false);
      setTransferDirectionId("");
      setTransferReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de transférer le ticket.");
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
      toast.success("Ticket escaladé au chef hiérarchique.");
      setShowEscalateForm(false);
      setEscalateReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'escalader le ticket.");
    },
    onSettled: () => invalidate(),
  });

  const escalateToDirectorMut = useMutation({
    mutationFn: () => escalateToDirectorRequest(id, {
      reason: escalateToDirectorReason.trim(),
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
      toast.success("Ticket escaladé directement au directeur.");
      setShowEscalateToDirectorForm(false);
      setEscalateToDirectorReason("");
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'escalader le ticket au directeur.");
    },
    onSettled: () => invalidate(),
  });

  const commentMut = useMutation({
    mutationFn: async () => {
      // Envoi combine — le fichier joint (si present) est uploade d'abord, puis
      // le commentaire est cree en referencant son attachment_id, en un seul
      // geste utilisateur (comme une pièce jointe + legende sur WhatsApp).
      let attachmentId: string | undefined;
      if (stagedFile) {
        const uploaded = await uploadAttachment(
          id,
          stagedFile,
          sessionUser?.id ? String(sessionUser.id) : undefined,
          true, // skip l'événement "Pièce jointe ajoutée" — le commentaire portera déjà l'info de la pièce jointe
        );
        attachmentId = uploaded.id;
      }
      const finalBody = replyTarget ? `@${replyTarget} ${comment.trim()}` : comment.trim();
      return createComment(id, {
        author_id: authorId,
        author_name: authorName,
        body: finalBody,
        is_public: isRequesterView ? true : isPublic,
        attachment_id: attachmentId,
        is_directive: canSendDirective ? isDirective : false,
        reply_to_id: replyToId ?? undefined,
      });
    },
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      const optimisticComment = {
        id: `temp-${Date.now()}`,
        authorId: String(authorId),
        author: authorName,
        body: replyTarget ? `@${replyTarget} ${comment.trim()}` : comment.trim(),
        isPublic: isRequesterView ? true : isPublic,
        replyToId: replyToId ?? undefined,
        isEdited: false,
        createdAt: new Date().toISOString(),
        attachmentName: stagedFile?.name,
      };
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, comments: [...(old.comments ?? []), optimisticComment] } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success(
        canSendDirective && isDirective
          ? "Directive envoyée à l'agent"
          : stagedFile ? "Commentaire et pièce jointe envoyés" : "Commentaire ajouté",
      );
      setComment("");
      setReplyTarget(null);
      setReplyToId(null);
      setStagedFile(null);
      setIsDirective(false);
      if (attachRef.current) attachRef.current.value = "";
    },
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible d'ajouter le commentaire.");
    },
    onSettled: () => invalidate(),
  });

  const deleteCommentMut = useMutation({
    mutationFn: (commentId: string) => deleteComment(id, commentId),
    onMutate: async (commentId: string) => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, comments: old.comments.filter((c) => c.id !== commentId) } : old,
      );
      return { previous };
    },
    onSuccess: () => toast.success("Commentaire supprimé."),
    onError: (_err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error("Impossible de supprimer le commentaire.");
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
    queryFn: () => fetchUsers({ role: "agent-support", limit: 100 }),
    enabled: !isRequesterView,
    staleTime: 120_000,
  });

  const commentAuthorIds = useMemo(() => {
    const ids = new Set<string>();
    if (r?.requesterId) ids.add(String(r.requesterId));
    if (r?.assigneeId) ids.add(String(r.assigneeId));
    for (const item of r?.comments ?? []) {
      if (item.authorId) ids.add(String(item.authorId));
    }
    return Array.from(ids).slice(0, 20);
  }, [r?.requesterId, r?.assigneeId, r?.comments]);

  const commentAuthorQueries = useQueries({
    queries: commentAuthorIds.map((authorId) => ({
      queryKey: ["user", authorId],
      queryFn: () => fetchUser(authorId),
      enabled: !!r?.id && !!authorId,
      staleTime: 300_000,
    })),
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: units = [] } = useQuery({
    queryKey: ["units-all"],
    queryFn: () => fetchUnits(),
    enabled: !!r?.serviceId,
    staleTime: 5 * 60_000,
  });

  // BR-TRANSMIT-001 — annuaire libre pour "Transmettre le traitement" : cascade
  // Direction -> Département -> Service (facultative, pour affiner) + recherche
  // libre dans toute l'organisation, restreinte aux rôles traitants côté client
  // (le backend revérifie de toute façon existence/statut actif/rôle habilité).
  const { data: transmitDirections = [] } = useQuery({
    queryKey: ["directions", "active"],
    queryFn: () => fetchDirections({ status: "active" }),
    enabled: showTransmitForm,
    staleTime: 5 * 60_000,
  });
  const { data: transmitDepartments = [] } = useQuery({
    queryKey: ["departments", transmitDirectionId, "active"],
    queryFn: () => fetchDepartments({ directionId: transmitDirectionId, status: "active" }),
    enabled: showTransmitForm && !!transmitDirectionId,
    staleTime: 5 * 60_000,
  });
  const { data: transmitUnits = [] } = useQuery({
    queryKey: ["units", transmitDepartmentId, "active"],
    queryFn: () => fetchUnits({ departmentId: transmitDepartmentId, status: "active" }),
    enabled: showTransmitForm && !!transmitDepartmentId,
    staleTime: 5 * 60_000,
  });
  const currentUserId = String(sessionUser?.id ?? "");
  const filterCurrentUser = (users: AccountUser[]) =>
    users.filter((user) => String(user.id) !== currentUserId);
  const { data: transmitPeople = [], isFetching: transmitPeopleLoading } = useQuery({
    queryKey: ["transmit-people", transmitSearch, transmitUnitId, transmitDepartmentId, transmitDirectionId, currentUserId],
    queryFn: async () => {
      if (transmitSearch.trim()) {
        const res = await fetchUsers({ search: transmitSearch.trim(), limit: 50 });
        return filterCurrentUser(res.items.filter((u) => TREATING_ROLES.has(u.role)));
      }
      if (transmitUnitId) {
        const [agents, chiefs] = await Promise.all([
          fetchUsers({ role: "agent-support", unit_id: transmitUnitId, limit: 100 }),
          fetchUsers({ role: "chief-service", unit_id: transmitUnitId, limit: 100 }),
        ]);
        const byId = new Map([...agents.items, ...chiefs.items].map((p) => [p.id, p]));
        return filterCurrentUser(Array.from(byId.values()));
      }
      if (transmitDepartmentId) {
        const res = await fetchUsers({ role: "chief-departement", unit_id: transmitDepartmentId, limit: 50 });
        return filterCurrentUser(res.items);
      }
      if (transmitDirectionId) {
        const res = await fetchUsers({ role: "director", unit_id: transmitDirectionId, limit: 50 });
        return filterCurrentUser(res.items);
      }
      return [];
    },
    enabled: showTransmitForm,
    staleTime: 30_000,
  });
  const selectedTransmitPerson = useMemo(
    () => transmitPeople.find((person) => person.id === transmitTargetId),
    [transmitPeople, transmitTargetId],
  );

  useEffect(() => {
    if (!transmitTargetId || !selectedTransmitPerson) return;
    if (selectedTransmitPerson.direction_id && transmitDirectionId !== selectedTransmitPerson.direction_id) {
      setTransmitDirectionId(selectedTransmitPerson.direction_id);
    }
    if (selectedTransmitPerson.department_id && transmitDepartmentId !== selectedTransmitPerson.department_id) {
      setTransmitDepartmentId(selectedTransmitPerson.department_id);
    }
    if (selectedTransmitPerson.unit_id && transmitUnitId !== selectedTransmitPerson.unit_id) {
      setTransmitUnitId(selectedTransmitPerson.unit_id);
    }
  }, [selectedTransmitPerson, transmitTargetId, transmitDirectionId, transmitDepartmentId, transmitUnitId]);

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
        <h2 className="text-lg font-semibold">Ticket introuvable</h2>
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
  const departmentName = assignedUnit?.department_name ?? "—";
  const currentDirectionId = assignedUnit?.direction_id ?? r.directionId ?? r.serviceId;
  const directionName = directions.find(
    (d) => String(d.id) === currentDirectionId,
  )?.name ?? "—";
  const transferDirectionOptions = directions.filter(
    (d) => String(d.id) !== String(currentDirectionId),
  );
  const requesterUnit = units.find((u) => String(u.id) === String(r.requesterServiceId));
  const requesterUnitName = requesterUnit?.name ?? "—";
  const requesterDepartmentName = requesterUnit?.department_name ?? "—";
  const requesterDirectionId = requesterUnit?.direction_id ?? r.requesterDirectionId;
  const requesterDirectionName = directions.find(
    (d) => String(d.id) === String(requesterDirectionId),
  )?.name ?? "—";

  const isArchived = Boolean(r.deletedAt || r.isArchived);
  const isFinal = isArchived || (["resolved", "closed", "rejected", "cancelled"] as const).includes(
    r.status as "resolved" | "closed" | "rejected" | "cancelled",
  );

  const agentPool = agentsData?.items ?? [];
  const availableServices = [...new Set(agentPool.map((a) => a.unit_id).filter((u): u is string => !!u))];

  const visibleComments = isRequesterView ? r.comments.filter((c) => c.isPublic) : r.comments;
  const participants = buildParticipants(r, visibleComments, assigneeUser?.name);
  const commentAuthorProfiles = new Map<string, AccountUser>();
  commentAuthorQueries.forEach((query, index) => {
    const authorId = commentAuthorIds[index];
    if (authorId && query.data) commentAuthorProfiles.set(authorId, query.data);
  });
  for (const account of agentPool) {
    commentAuthorProfiles.set(String(account.id), account);
  }
  if (assigneeUser) {
    commentAuthorProfiles.set(String(assigneeUser.id), assigneeUser);
  }

  const profileForComment = (item: RequestItem["comments"][number]) =>
    item.authorId ? commentAuthorProfiles.get(String(item.authorId)) : undefined;
  const avatarForComment = (item: RequestItem["comments"][number]) => {
    const profile = profileForComment(item);
    const sessionAvatar =
      item.authorId && isRequester(item.authorId, sessionUser?.id)
        ? sessionUser?.avatar
        : undefined;
    return buildAvatarUrl(profile?.avatar ?? sessionAvatar);
  };
  const roleForComment = (item: RequestItem["comments"][number]) => {
    if (item.authorId && r.requesterId && String(item.authorId) === String(r.requesterId)) {
      return "Demandeur";
    }
    const profile = profileForComment(item);
    return (
      participantRoleLabel(profile?.role) ??
      participantRoleLabel(item.authorRole) ??
      "Intervenant"
    );
  };
  const canDeleteComment = (item: RequestItem["comments"][number]) => {
    if (isArchived || r.status === "closed" || r.status === "rejected") return false;
    if (!sessionUser?.id || !item.authorId) return false;
    if (String(item.authorId) === String(sessionUser.id)) return true;
    const isOwnerView = Boolean(r.requesterId && String(sessionUser.id) === String(r.requesterId));
    return sessionUser.role !== "user" && !isOwnerView;
  };
  const lastVisibleComment = visibleComments[visibleComments.length - 1];
  // Badge "reponse attendue" bidirectionnel par camp (demandeur <-> personnel) :
  // s'allume pour le viewer dont ce n'est pas le camp qui a parle en dernier,
  // tant que le ticket reste actif (meme garde que le bouton "Repondre" ci-dessous).
  const isDiscussionLocked = isArchived || r.status === "closed" || r.status === "rejected";
  const lastCommentFromRequesterSide = isRequester(r.requesterId, lastVisibleComment?.authorId);
  const needsUserResponse =
    !isDiscussionLocked &&
    Boolean(lastVisibleComment) &&
    (isRequesterView ? !lastCommentFromRequesterSide : lastCommentFromRequesterSide);
  const isAssignedToMe = isRequester(r.assigneeId, sessionUser?.id);
  const hasAssignee = Boolean(r.assigneeId);
  const hasReopenRequest = (r.infos as Record<string, unknown> | undefined)?.reopen_requested === true;

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
    && (role !== "agent-support" || isAssignedToMe);
  // Lot 3.3 — "Escalade exceptionnelle" : distincte de l'escalade générique ci-dessus,
  // réservée à chief-departement, cible directement le directeur.
  const canEscalateToDirector = !isArchived
    && !iAmRequester
    && canTicketAction(role, "escalate_to_director", r.status, ownershipOptions);
  const canAssignTicket = !isArchived && !iAmRequester && canTicketAction(role, "assign", r.status, ownershipOptions);
  // BR-TRANSMIT-001 : "Terminer le traitement" et "Transmettre le traitement" sont
  // réservés à l'intervenant actuel (assignee_id == moi), quel que soit le rôle parmi
  // les rôles traitants — le rôle n'est plus qu'un filtre de sécurité général.
  const canResolveTicket = !isArchived && !iAmRequester && isAssignedToMe
    && canTicketAction(role, "resolve", r.status, { ...ownershipOptions, isAssignedToMe });
  const canTransmitTreatment = !isArchived && !iAmRequester && isAssignedToMe
    && canTicketAction(role, "transmit_treatment", r.status, { ...ownershipOptions, isAssignedToMe });
  // Lot 2.7 — "Directive" : commentaire dédié chef -> agent assigné, réservé aux chefs
  // et impossible tant que le ticket n'a pas d'agent assigné (rien à cibler sinon).
  const canSendDirective = !isRequesterView
    && (role === "chief-service" || role === "chief-departement")
    && !!r.assigneeId;
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
  const canShowClosedRequestAction = isRequesterView && r.status === "closed";
  const canOpenAppreciation = isRequesterView && (r.status === "resolved" || r.status === "closed");
  const assigneeDisplayName = assigneeUser?.name ?? r.assigneeName ?? (r.assigneeId ? "Agent assigné" : "Non assigné");
  const createdAtLabel = formatTicketDateTime(r.createdAt);
  const updatedAtLabel = formatTicketDateTime(r.updatedAt);
  const canShowQuickActions = canEdit || canCancel || canClose || canRequestReopen || canShowClosedRequestAction || canOpenAppreciation;
  const hasRequestActions = canShowQuickActions;
  const hasTreatmentActions = !isRequesterView && (
    (r.status === "reopened" && !r.assigneeId) ||
    canApproveReopen ||
    canRejectReopen ||
    canSelfAssign ||
    canTakeOwnership ||
    canRequestInfo ||
    canResumeTreatment ||
    canEscalateTicket ||
    canEscalateToDirector ||
    canAssignTicket ||
    canCreateCircuit ||
    canChangePriority ||
    canRejectTicket ||
    canChangeService ||
    canTransferDirection ||
    canTransmitTreatment ||
    canResolveTicket
  );
  const detailTabs: Array<{ key: DetailTab; label: string; count?: number; icon: LucideIcon }> = [
    { key: "description", label: "Description", icon: FileText },
    { key: "journal", label: "Journals", count: r.timeline.length, icon: GitBranch },
    { key: "comments", label: "Discussions", count: visibleComments.length, icon: MessageSquare },
    { key: "files", label: "Fichiers", count: attachments.length, icon: Paperclip },
    { key: "sla", label: "Délais de traitement", icon: Clock },
    { key: "treatment", label: "Traitement", icon: Wrench },
  ];
  const sideParticipants = participants.slice(0, 4);
  const canToggleParticipants = participants.length > sideParticipants.length;
  const sideCardClass = "glass-strong rounded-[18px] p-4 sm:p-5";
  const directTreatmentActionConfig = (() => {
    switch (directTreatmentAction) {
      case "approveReopen":
        return {
          icon: RotateCcw,
          title: "Approuver la réouverture",
          description: "Le ticket retournera en traitement et le demandeur sera notifié.",
          confirmLabel: "Approuver",
          isPending: approveReopenMut.isPending,
        };
      case "selfAssign":
        return {
          icon: UserCheck,
          title: "Vous assigner ce ticket",
          description: "Le ticket vous sera attribué pour prise en charge.",
          confirmLabel: "M'assigner",
          isPending: selfAssignMut.isPending,
        };
      case "takeOwnership":
        return {
          icon: UserCheck,
          title: "Démarrer le traitement",
          description: "Le ticket passera en cours de traitement.",
          confirmLabel: "Démarrer",
          isPending: takeOwnershipMut.isPending,
        };
      case "resume":
        return {
          icon: RotateCcw,
          title: "Reprendre le traitement",
          description: "Le ticket quittera l'attente et repassera en cours de traitement.",
          confirmLabel: "Reprendre",
          isPending: resumeMut.isPending,
        };
      case "close":
        return {
          icon: CheckCircle2,
          title: "Confirmer la résolution",
          description: "Le ticket sera clôturé et le traitement sera considéré comme terminé.",
          confirmLabel: "Confirmer",
          isPending: closeMut.isPending,
        };
      default:
        return null;
    }
  })();
  const confirmDirectTreatmentAction = () => {
    switch (directTreatmentAction) {
      case "approveReopen":
        approveReopenMut.mutate();
        break;
      case "selfAssign":
        selfAssignMut.mutate();
        break;
      case "takeOwnership":
        takeOwnershipMut.mutate();
        break;
      case "resume":
        resumeMut.mutate();
        break;
      case "close":
        closeMut.mutate();
        break;
    }
  };

  const treatmentActionsPanel = (
    !isRequesterView && (isFinal && !canDecideReopen) ? (
      <div className="flex w-full flex-wrap items-center gap-2 rounded-full border border-border/40 bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
        <Lock className="h-3.5 w-3.5" />
        Ticket {isArchived ? "archivé" : r.status === "closed" ? "clôturé" : r.status === "rejected" ? "rejeté" : "résolu"} — aucune action disponible
      </div>
    ) : (hasTreatmentActions || hasRequestActions) ? (
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" role="group" aria-label="Actions de traitement">
        {/* BR-REOPEN-QUEUE-001 — assignee_id=null tant que personne n'a repris le
            ticket depuis la File d'attente : le rappeler explicitement. */}
        {!isRequesterView && r.status === "reopened" && !r.assigneeId && (
          <div className="col-span-full flex items-center gap-2 rounded-full border border-fuchsia-500/40 bg-fuchsia-500/10 px-4 py-2 text-sm text-fuchsia-700 dark:text-fuchsia-300">
            <RotateCcw className="h-3.5 w-3.5 shrink-0" />
            Ce ticket réouvert attend une nouvelle prise en charge.
          </div>
        )}
        {canApproveReopen && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-success/40 bg-success/10 p-3 text-left transition hover:bg-success/15 disabled:opacity-60"
            onClick={() => setDirectTreatmentAction("approveReopen")}
            disabled={approveReopenMut.isPending}
          >
            {approveReopenMut.isPending
              ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-success" />
              : <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
            <span>
              <span className="block text-sm font-semibold text-success">Approuver réouverture</span>
              <span className="text-xs text-muted-foreground">Le ticket retourne en traitement</span>
            </span>
          </button>
        )}
        {canRejectReopen && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-left transition hover:bg-destructive/15"
            onClick={() => setShowRejectReopenConfirm(true)}
          >
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span>
              <span className="block text-sm font-semibold text-destructive">Refuser réouverture</span>
              <span className="text-xs text-muted-foreground">Le ticket reste dans son état actuel</span>
            </span>
          </button>
        )}
        {/* Agent — auto-assignation d'un ticket libre de son périmètre */}
        {canSelfAssign && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/10 p-3 text-left transition hover:bg-primary/15 disabled:opacity-60"
            onClick={() => setDirectTreatmentAction("selfAssign")}
            disabled={selfAssignMut.isPending || !sessionUser?.id}
          >
            {selfAssignMut.isPending
              ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
              : <UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
            <span>
              <span className="block text-sm font-semibold text-primary">M'assigner</span>
              <span className="text-xs text-muted-foreground">Prendre en charge ce ticket</span>
            </span>
          </button>
        )}
        {/* C1/C9 — Prendre en charge : ASSIGNED, agent seulement */}
        {canTakeOwnership && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/10 p-3 text-left transition hover:bg-primary/15 disabled:opacity-60"
            onClick={() => setDirectTreatmentAction("takeOwnership")}
            disabled={takeOwnershipMut.isPending}
          >
            {takeOwnershipMut.isPending
              ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
              : <UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
            <span>
              <span className="block text-sm font-semibold text-primary">Démarrer traitement</span>
              <span className="text-xs text-muted-foreground">Passer le ticket en cours</span>
            </span>
          </button>
        )}
        {/* C2 — Demander des informations : IN_PROGRESS, agent seulement */}
        {canRequestInfo && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-left transition hover:bg-amber-500/10"
            onClick={() => setShowRequestInfoForm(true)}
          >
            <MessageSquareWarning className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <span>
              <span className="block text-sm font-semibold text-amber-500">Ouvrir une discussion</span>
              <span className="text-xs text-muted-foreground">Mettre en attente du demandeur</span>
            </span>
          </button>
        )}
        {/* C3 — Reprendre le traitement : PENDING, agent seulement */}
        {canResumeTreatment && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-info/40 bg-info/10 p-3 text-left transition hover:bg-info/15 disabled:opacity-60"
            onClick={() => setDirectTreatmentAction("resume")}
            disabled={resumeMut.isPending}
          >
            {resumeMut.isPending
              ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-info" />
              : <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-info" />}
            <span>
              <span className="block text-sm font-semibold text-info">Reprendre le traitement</span>
              <span className="text-xs text-muted-foreground">Sortir de l'attente</span>
            </span>
          </button>
        )}
        {/* C5 — Escalader : agent, chef, directeur, admin seulement */}
        {canEscalateTicket && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-orange-600/40 bg-orange-600/10 p-3 text-left transition hover:bg-orange-600/15"
            onClick={() => setShowEscalateForm(true)}
          >
            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-orange-600" />
            <span>
              <span className="block text-sm font-semibold text-orange-600">Escalader</span>
              <span className="text-xs text-muted-foreground">Transmettre à un niveau supérieur</span>
            </span>
          </button>
        )}
        {/* Lot 3.3 — Escalade exceptionnelle : court-circuite la hiérarchie, cible le directeur */}
        {canEscalateToDirector && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-left transition hover:bg-destructive/15"
            onClick={() => setShowEscalateToDirectorForm(true)}
          >
            <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span>
              <span className="block text-sm font-semibold text-destructive">Escalader au Directeur</span>
              <span className="text-xs text-muted-foreground">Escalade exceptionnelle — court-circuite la hiérarchie</span>
            </span>
          </button>
        )}
        {/* C6 — Assigner / réassigner : chef et admin seulement */}
        {canAssignTicket && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/10 p-3 text-left transition hover:bg-primary/15 disabled:opacity-60"
            onClick={() => setShowReassign(true)}
            disabled={assignMut.isPending}
          >
            <UserCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>
              <span className="block text-sm font-semibold text-primary">Réassigner</span>
              <span className="text-xs text-muted-foreground">Choisir un autre agent</span>
            </span>
          </button>
        )}
        {/* Créer circuit : agent, chef, admin */}
        {canCreateCircuit && workflows.length === 0 && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-indigo-600/40 bg-indigo-600/10 p-3 text-left transition hover:bg-indigo-600/15"
            onClick={() => setShowCircuitDialog(true)}
          >
            <GitBranch className="mt-0.5 h-4 w-4 shrink-0 text-indigo-600" />
            <span>
              <span className="block text-sm font-semibold text-indigo-600">Créer circuit</span>
              <span className="text-xs text-muted-foreground">Circuit de validation automatique</span>
            </span>
          </button>
        )}
        {/* Chef + Director: Changer priorité */}
        {canChangePriority && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-amber-600/40 bg-amber-600/10 p-3 text-left transition hover:bg-amber-600/15 disabled:opacity-60"
            onClick={() => setShowPriorityPicker(true)}
            disabled={changePriorityMut.isPending}
          >
            <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <span>
              <span className="block text-sm font-semibold text-amber-600">Changer priorité</span>
              <span className="text-xs text-muted-foreground">Ajuster le niveau d'urgence</span>
            </span>
          </button>
        )}
        {/* Responsables: Rejeter + Changer service + Transfert direction */}
        {canRejectTicket && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-left transition hover:bg-destructive/15"
            onClick={() => setShowRejectConfirm(true)}
          >
            <Ban className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span>
              <span className="block text-sm font-semibold text-destructive">Rejeter</span>
              <span className="text-xs text-muted-foreground">Refuser ce ticket</span>
            </span>
          </button>
        )}
        {canChangeService && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-sky-500/40 bg-sky-500/10 p-3 text-left transition hover:bg-sky-500/15 disabled:opacity-60"
            onClick={() => setShowServicePicker(true)}
            disabled={changeServiceMut.isPending}
          >
            <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-sky-500" />
            <span>
              <span className="block text-sm font-semibold text-sky-500">Changer service</span>
              <span className="text-xs text-muted-foreground">Réaffecter vers un autre service</span>
            </span>
          </button>
        )}
        {canTransferDirection && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-violet-600/40 bg-violet-600/10 p-3 text-left transition hover:bg-violet-600/15 disabled:opacity-60"
            onClick={() => {
              setTransferDirectionId("");
              setTransferReason("");
              setShowDirectionTransfer(true);
            }}
            disabled={transferDirectionMut.isPending}
          >
            <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-violet-600" />
            <span>
              <span className="block text-sm font-semibold text-violet-600">Transférer direction</span>
              <span className="text-xs text-muted-foreground">Envoyer vers une autre direction</span>
            </span>
          </button>
        )}
        {/* BR-TRANSMIT-001 — Transmettre le traitement : réservé à l'intervenant actuel. */}
        {canTransmitTreatment && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-sky-600/40 bg-sky-600/10 p-3 text-left transition hover:bg-sky-600/15 disabled:opacity-60"
            onClick={() => setShowTransmitForm(true)}
            disabled={transmitMut.isPending}
          >
            <Send className="mt-0.5 h-4 w-4 shrink-0 text-sky-600" />
            <span>
              <span className="block text-sm font-semibold text-sky-600">Transmettre le traitement</span>
              <span className="text-xs text-muted-foreground">Choisir le prochain intervenant</span>
            </span>
          </button>
        )}
        {/* BR-TRANSMIT-001 — Terminer le traitement : réservé à l'intervenant actuel,
            résumé/solution/travail réalisé obligatoires. */}
        {canResolveTicket && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-success/40 bg-success/10 p-3 text-left transition hover:bg-success/15 disabled:opacity-60"
            onClick={() => setShowResolveForm(true)}
            disabled={resolveMut.isPending}
          >
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
            <span>
              <span className="block text-sm font-semibold text-success">Terminer le traitement</span>
              <span className="text-xs text-muted-foreground">Ticket complètement traité</span>
            </span>
          </button>
        )}
        {canEdit && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/5 p-3 text-left transition hover:bg-amber-500/10"
            onClick={() => {
              setEditTitle(r.title);
              setEditDescription(r.description);
              setShowEditForm(true);
            }}
          >
            <Pencil className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
            <span>
              <span className="block text-sm font-semibold text-amber-500">Modifier le ticket</span>
              <span className="text-xs text-muted-foreground">Uniquement au début</span>
            </span>
          </button>
        )}
        {canCancel && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-left transition hover:bg-destructive/15"
            onClick={() => setShowCancelConfirm(true)}
          >
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
            <span>
              <span className="block text-sm font-semibold text-destructive">Annuler le ticket</span>
              <span className="text-xs text-muted-foreground">Uniquement au début</span>
            </span>
          </button>
        )}
        {canRequestReopen && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-info/40 bg-info/10 p-3 text-left transition hover:bg-info/15"
            onClick={() => setShowClosedRequestDialog(true)}
          >
            <RotateCcw className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <span>
              <span className="block text-sm font-semibold text-info">
                {r.status === "closed" ? "Rouvrir le ticket" : "Demander une réouverture"}
              </span>
              <span className="text-xs text-muted-foreground">Après résolution</span>
            </span>
          </button>
        )}
        {canShowClosedRequestAction && !canRequestReopen && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-border/40 bg-muted/10 p-3 text-left transition hover:bg-muted/20"
            onClick={() => setShowClosedRequestDialog(true)}
          >
            <Lock className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span>
              <span className="block text-sm font-semibold">Ticket clôturé</span>
              <span className="text-xs text-muted-foreground">Voir l'état du ticket</span>
            </span>
          </button>
        )}
        {canClose && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-success/40 bg-success/10 p-3 text-left transition hover:bg-success/15 disabled:opacity-60"
            onClick={() => setDirectTreatmentAction("close")}
            disabled={closeMut.isPending}
          >
            {closeMut.isPending
              ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-success" />
              : <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
            <span>
              <span className="block text-sm font-semibold text-success">Confirmer la résolution</span>
              <span className="text-xs text-muted-foreground">Après traitement</span>
            </span>
          </button>
        )}
        {canOpenAppreciation && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-border/40 bg-background/30 p-3 text-left transition hover:bg-foreground/5"
            onClick={() => setShowAppreciationDialog(true)}
          >
            <Star className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
            <span>
              <span className="block text-sm font-semibold">Votre avis</span>
              <span className="text-xs text-muted-foreground">Évaluer la prise en charge</span>
            </span>
          </button>
        )}
      </div>
    ) : null
  );

  const commentsPanel = (
    <section ref={commentsPanelRef} className="min-w-0">
      <div>
        {visibleComments.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-border/50 bg-background/35 px-4 py-5 text-sm text-muted-foreground">
            Aucun commentaire pour l'instant.
          </p>
        ) : (
          <ul className="relative space-y-4 pb-1">
            {visibleComments.map((c, index) => {
              const fullAttachment = c.attachmentName
                ? attachments.find((a) => a.id === c.attachmentId)
                : undefined;
              const authorAvatar = avatarForComment(c);
              // Style messagerie viewer-relatif : mes propres messages a droite,
              // ceux des autres a gauche, quel que soit mon role (demandeur ou personnel).
              const isMine = isRequester(c.authorId, sessionUser?.id);
              const attachmentSize = c.attachmentSize ?? fullAttachment?.size_bytes;
              const attachmentMime = c.attachmentMime ?? fullAttachment?.mime_type ?? "";
              const isAwaitingReply = needsUserResponse && index === visibleComments.length - 1;

              return (
                <li key={c.id} className={cn("relative flex min-w-0 gap-3", isMine && "flex-row-reverse")}>
                  <Avatar className="h-10 w-10 shrink-0 border border-border/60 bg-background shadow-sm">
                    <AvatarImage src={authorAvatar} alt={c.author} />
                    <AvatarFallback className="bg-primary/10 text-xs font-bold text-primary">
                      {initialsFor(c.author)}
                    </AvatarFallback>
                  </Avatar>
                  <div className={cn("flex min-w-0 flex-1 flex-col", isMine ? "items-end" : "items-start")}>
                    <div className={cn(
                      "relative inline-block max-w-full rounded-2xl px-3.5 py-2.5 pr-10 shadow-sm",
                      c.isDirective
                        ? "border border-warning/40 bg-warning/10"
                        : "bg-muted/45",
                    )}>
                      <div className="flex min-w-0 flex-wrap items-center gap-2">
                        <span className="truncate text-sm font-semibold text-foreground">{c.author}</span>
                        <span className="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-semibold text-primary">
                          {roleForComment(c)}
                        </span>
                        {c.isDirective && (
                          <span className="flex shrink-0 items-center gap-1 rounded-full bg-warning/20 px-2 py-0.5 text-[10px] font-bold text-warning-foreground dark:text-warning">
                            <AlertTriangle className="h-2.5 w-2.5" /> Directive
                          </span>
                        )}
                        {!isRequesterView && (
                          c.isPublic ? (
                            <span className="shrink-0 rounded-full bg-info/15 px-2 py-0.5 text-[10px] text-info">
                              Visible public
                            </span>
                          ) : (
                            <span className="shrink-0 rounded-full bg-muted px-2 py-0.5 text-[10px]">Interne</span>
                          )
                        )}
                      </div>
                      <p className="mt-1 whitespace-pre-wrap text-sm leading-5 text-foreground">{c.body}</p>
                      {c.attachmentName && (
                        <button
                          type="button"
                          className="mt-2 flex w-full max-w-sm items-center gap-3 rounded-xl border border-border/40 bg-background/75 px-2.5 py-2 text-left text-xs transition hover:bg-background disabled:cursor-default"
                          onClick={() => fullAttachment && void handleAttachmentFile(fullAttachment, "download")}
                          disabled={!fullAttachment}
                        >
                          <span className="grid h-10 w-14 shrink-0 place-items-center rounded-lg border border-border/40 bg-background/80">
                            <FileText className="h-5 w-5 text-primary" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-semibold text-foreground">{c.attachmentName}</span>
                            <span className="block text-muted-foreground">
                              {attachmentSize ? formatAttachmentSize(attachmentSize) : attachmentTypeLabel(attachmentMime)}
                            </span>
                          </span>
                          <Download className="h-4 w-4 shrink-0 text-muted-foreground" />
                        </button>
                      )}
                      {canDeleteComment(c) && (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <button
                              type="button"
                              className="absolute right-2 top-2 grid h-7 w-7 place-items-center rounded-full text-muted-foreground opacity-80 transition hover:bg-background/80 hover:text-foreground"
                              title="Options du commentaire"
                            >
                              <MoreVertical className="h-4 w-4" />
                            </button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem
                              className="text-destructive focus:text-destructive"
                              onClick={() => deleteCommentMut.mutate(c.id)}
                            >
                              <Trash2 className="mr-2 h-4 w-4" />
                              Supprimer
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </div>
                    <div className={cn(
                      "mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground",
                      isMine ? "pr-1" : "pl-1",
                    )}>
                      <span>{formatCommentDate(c.createdAt)}</span>
                      {!(isArchived || r.status === "closed" || r.status === "rejected") && (
                        <>
                          <span aria-hidden>-</span>
                          <button
                            type="button"
                            className={cn(
                              "rounded-full font-medium transition",
                              isAwaitingReply
                                ? "animate-pulse bg-success/20 px-2.5 py-1 text-success ring-1 ring-success/50"
                                : "hover:text-foreground",
                            )}
                            title={isAwaitingReply ? "Une réponse est attendue à ce message" : undefined}
                            onClick={() => {
                              setReplyTarget(c.author);
                              setReplyToId(c.id);
                              commentRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
                              commentRef.current?.focus();
                            }}
                          >
                            Repondre
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        )}

        {isArchived || r.status === "closed" || r.status === "rejected" ? (
          <div className="mt-4 flex items-center gap-2 rounded-xl border border-border/30 bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
            <Lock className="h-3.5 w-3.5 shrink-0" />
            Les commentaires sont desactives - ticket {isArchived ? "archive" : r.status === "closed" ? "cloture" : "rejete"}.
          </div>
        ) : (
          <div className="mt-5 rounded-2xl border border-border/40 bg-background/45 p-2 shadow-sm">
            {replyTarget && (
              <div className="mb-2 flex items-center justify-between gap-2 px-2 py-1">
                <span className="min-w-0 truncate text-sm font-medium text-success">
                  Répondre à @{replyTarget}
                </span>
                <button
                  type="button"
                  className="grid h-5 w-5 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="Annuler la réponse"
                  onClick={() => { setReplyTarget(null); setReplyToId(null); }}
                >
                  <XCircle className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            {stagedFile && (
              <div className="mb-2 ml-0 flex items-center gap-2 rounded-xl border border-border/40 bg-background/70 px-3 py-2 text-xs sm:ml-12">
                <FileText className="h-3.5 w-3.5 shrink-0 text-primary" />
                <span className="min-w-0 flex-1 truncate">{stagedFile.name}</span>
                <button
                  type="button"
                  className="grid h-5 w-5 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                  title="Retirer la piece jointe"
                  onClick={() => {
                    setStagedFile(null);
                    if (attachRef.current) attachRef.current.value = "";
                  }}
                >
                  <XCircle className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            <div className="flex items-end gap-2">
              <div className="flex min-w-0 flex-1 items-end gap-1 rounded-xl border border-border/35 bg-background/70 px-3 py-1.5">
                <Textarea
                  ref={commentRef}
                  placeholder={isRequesterView ? "Ecrire un commentaire..." : "Ajouter un commentaire..."}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  className="max-h-28 min-h-10 resize-none border-0 bg-transparent px-0 py-2 text-sm shadow-none focus-visible:ring-0"
                />
                <input
                  ref={attachRef}
                  type="file"
                  accept=".jpg,.jpeg,.png,.webp,.heic,.pdf"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) setStagedFile(f);
                  }}
                />
                <Button
                  variant="ghost"
                  size="icon"
                  className={cn("h-9 w-9 shrink-0 rounded-full", stagedFile && "text-primary")}
                  title="Joindre un fichier"
                  onClick={() => attachRef.current?.click()}
                >
                  <Paperclip className="h-4 w-4" />
                </Button>
                <Popover open={emojiPickerOpen} onOpenChange={setEmojiPickerOpen}>
                  <PopoverTrigger asChild>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      className="h-9 w-9 shrink-0 rounded-full"
                      title="Ajouter un emoji"
                    >
                      <Smile className="h-4 w-4" />
                    </Button>
                  </PopoverTrigger>
                  <PopoverContent align="end" className="w-64 p-2">
                    <div className="grid grid-cols-8 gap-1">
                      {COMMENT_EMOJIS.map((emoji) => (
                        <button
                          key={emoji}
                          type="button"
                          className="grid h-7 w-7 place-items-center rounded-md text-lg transition hover:bg-muted"
                          onClick={() => insertEmoji(emoji)}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </PopoverContent>
                </Popover>
              </div>
              <Button
                size="sm"
                className="h-10 rounded-xl gradient-primary px-5"
                disabled={!comment.trim() || commentMut.isPending}
                onClick={() => commentMut.mutate()}
              >
                {commentMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : "Envoyer"}
              </Button>
            </div>
            {!isRequesterView && (
              <div className="mt-2 flex flex-wrap items-center gap-4 pl-0 sm:pl-12">
                <div className="flex items-center gap-2">
                  <Switch id="public" checked={isPublic} onCheckedChange={setIsPublic} />
                  <Label htmlFor="public" className="text-sm">
                    Visible par le demandeur
                  </Label>
                </div>
                {canSendDirective && (
                  <div className="flex items-center gap-2">
                    <Switch id="directive" checked={isDirective} onCheckedChange={setIsDirective} />
                    <Label htmlFor="directive" className="text-sm font-medium text-warning-foreground dark:text-warning">
                      Marquer comme directive
                    </Label>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );

  return (
    <div className="mx-auto w-full max-w-[1700px] space-y-5 px-3 pb-24 sm:px-5 lg:px-8">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Button asChild variant="ghost" size="sm" className="-ml-2 rounded-full">
          <Link to={detailContext.backTo}>
            <ArrowLeft className="mr-1 h-4 w-4" /> {detailContext.backLabel}
          </Link>
        </Button>
        <span className="hidden text-muted-foreground sm:inline">/</span>
        <span className="hidden rounded-full border border-border/50 bg-background/50 px-3 py-1 text-xs font-medium text-muted-foreground sm:inline-flex">
          {detailContext.eyebrow} · Détail du ticket
        </span>
      </div>

      <div className="grid min-w-0 items-start gap-5 xl:grid-cols-[minmax(0,68fr)_minmax(320px,32fr)] 2xl:gap-6">
      <div className="min-w-0 space-y-5">
      <div className="overflow-hidden rounded-[18px] border border-border/50 bg-gradient-to-br from-background/95 via-card/80 to-primary/10 shadow-sm backdrop-blur">
      <header className="flex flex-col flex-wrap gap-5 p-5 sm:p-6 xl:p-7 lg:flex-row lg:items-stretch lg:justify-between">
        <div className="flex min-w-0 flex-1 flex-col gap-5 xl:flex-row xl:flex-wrap">
          <div className="min-w-[14rem] flex-1">
            <motion.div
              layoutId={`req-ref-${r.id}`}
              className="flex max-w-full items-center gap-2 font-mono text-[11px] text-muted-foreground sm:text-xs"
            >
              <span className="min-w-0 truncate">{r.ref}</span>
              <button
                type="button"
                title="Copier l'identifiant"
                className="grid h-6 w-6 place-items-center rounded-lg border border-border/50 bg-background/60 hover:bg-muted"
                onClick={() => {
                  void navigator.clipboard.writeText(r.ref);
                  toast.success("Identifiant copié");
                }}
              >
                <Copy className="h-3.5 w-3.5" />
              </button>
            </motion.div>
            <div className="mt-3 flex min-w-0 items-start gap-2">
              <h1 className="min-w-0 max-w-4xl break-words text-3xl font-bold leading-tight tracking-tight sm:text-4xl xl:text-5xl">{r.title}</h1>
              <Star className="mt-1 h-5 w-5 shrink-0 text-muted-foreground" />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge status={r.status} />
              <PriorityBadge priority={r.priority} />
              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-xs font-medium capitalize text-muted-foreground">
                {r.category}
              </span>
            </div>
            <p className="mt-5 text-sm text-muted-foreground">
              Créée le <span className="text-foreground">{createdAtLabel}</span> par{" "}
              <span className="text-foreground">{isRequesterView ? "vous" : r.requesterName}</span>
            </p>
          </div>

          <div className="w-full border-t border-border/40 pt-5 xl:w-72 xl:shrink-0 xl:border-l xl:border-t-0 xl:pl-6 xl:pt-0">
            <div className={cn("flex items-center gap-2 text-sm font-semibold", slaOver ? "text-destructive" : "text-success")}>
              {slaOver ? <AlertTriangle className="h-4 w-4" /> : <CheckCircle2 className="h-4 w-4" />}
              {slaOver ? "Délai dépassé" : "Délai conforme"}
            </div>
            <div className="mt-2 text-3xl font-bold sm:text-4xl">{slaPct}%</div>
            <div className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
              <Clock className="h-4 w-4" />
              {r.slaHours > 0 ? `${r.slaElapsed}h / ${r.slaHours}h` : "Délai non configuré"}
            </div>
            <div className="mt-4 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className={cn("h-full rounded-full", slaOver ? "bg-destructive" : "gradient-primary")}
                style={{ width: `${slaPct}%` }}
              />
            </div>
          </div>
        </div>

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

      </header>

      <TicketLifecycleStepper request={r} />

      </div>

      <div className="min-w-0 space-y-5">

          {directTreatmentActionConfig && (
            <Dialog
              open={!!directTreatmentActionConfig}
              onOpenChange={(open) => {
                if (!open) setDirectTreatmentAction(null);
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    {(() => {
                      const Icon = directTreatmentActionConfig.icon;
                      return <Icon className="h-5 w-5 text-primary" />;
                    })()}
                    {directTreatmentActionConfig.title}
                  </DialogTitle>
                  <DialogDescription>
                    {directTreatmentActionConfig.description}
                  </DialogDescription>
                </DialogHeader>
                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => setDirectTreatmentAction(null)}
                  >
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={directTreatmentActionConfig.isPending}
                    onClick={confirmDirectTreatmentAction}
                  >
                    {directTreatmentActionConfig.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <CheckCircle2 className="mr-1.5 h-4 w-4" />}
                    {directTreatmentActionConfig.confirmLabel}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {canEdit && (
            <Dialog
              open={showEditForm}
              onOpenChange={(open) => {
                setShowEditForm(open);
                if (!open) {
                  setEditTitle("");
                  setEditDescription("");
                }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Pencil className="h-5 w-5 text-amber-500" />
                    Modifier le ticket
                  </DialogTitle>
                  <DialogDescription>
                    Vous pouvez corriger le titre ou la description tant que le ticket n'est pas encore traité.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-3 py-2">
                  <div>
                    <Label className="text-sm">Titre</Label>
                    <input
                      type="text"
                      value={editTitle}
                      onChange={(e) => setEditTitle(e.target.value)}
                      className="mt-1.5 w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    />
                  </div>
                  <div>
                    <Label className="text-sm">Description détaillée</Label>
                    <Textarea
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      rows={4}
                      className="mt-1.5 min-h-32 bg-background"
                    />
                  </div>
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="ghost" className="rounded-full"
                    onClick={() => setShowEditForm(false)}>
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full gradient-primary"
                    disabled={
                      !editTitle.trim() ||
                      editDescription.trim().length < 10 ||
                      editMut.isPending
                    }
                    onClick={() => editMut.mutate()}
                  >
                    {editMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <CheckCircle2 className="mr-1.5 h-4 w-4" />}
                    Enregistrer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {canCancel && (
            <Dialog
              open={showCancelConfirm}
              onOpenChange={(open) => {
                setShowCancelConfirm(open);
                if (!open) setCancelReason("");
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <Ban className="h-5 w-5" />
                    Annuler ce ticket ?
                  </DialogTitle>
                  <DialogDescription>
                    Cette action est irréversible. Le ticket sera marqué comme annulé et ne sera plus traité.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  <Label>
                    Motif de l'annulation <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    placeholder="Motif de l'annulation…"
                    rows={3}
                    className="min-h-24 bg-background"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="ghost" className="rounded-full"
                    onClick={() => { setShowCancelConfirm(false); setCancelReason(""); }}>
                    Garder le ticket
                  </Button>
                  <Button
                    variant="destructive"
                    className="rounded-full"
                    disabled={!cancelReason.trim() || cancelMut.isPending}
                    onClick={() => cancelMut.mutate()}
                  >
                    {cancelMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Ban className="mr-1.5 h-4 w-4" />}
                    Confirmer l'annulation
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* C2 — Modal demande d'informations */}
          {!isRequesterView && (
            <Dialog
              open={showRequestInfoForm}
              onOpenChange={(open) => {
                setShowRequestInfoForm(open);
                if (!open) setInfoQuestion("");
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
                    <MessageSquareWarning className="h-5 w-5" />
                    Ouvrir une discussion
                  </DialogTitle>
                  <DialogDescription>
                    Le demandeur recevra une notification. Le ticket passera en attente jusqu'à sa réponse.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  <Label htmlFor="request-info-question">
                    Question <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="request-info-question"
                    value={infoQuestion}
                    onChange={(e) => setInfoQuestion(e.target.value)}
                    placeholder="Posez votre question ou décrivez les informations manquantes…"
                    rows={3}
                    className="min-h-24 bg-background"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="ghost" className="rounded-full"
                    onClick={() => { setShowRequestInfoForm(false); setInfoQuestion(""); }}>
                    Annuler
                  </Button>
                  <Button
                    className="rounded-full bg-amber-500 text-white hover:bg-amber-600"
                    disabled={!infoQuestion.trim() || requestInfoMut.isPending}
                    onClick={() => requestInfoMut.mutate()}
                  >
                    {requestInfoMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <MessageSquareWarning className="mr-1.5 h-4 w-4" />}
                    Envoyer la demande
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
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
                    Escalader le ticket
                  </DialogTitle>
                  <DialogDescription>
                    Ce ticket sera transmis au chef hiérarchique de la personne en charge
                    du traitement. Le motif sera enregistré dans l'historique.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
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

          {/* Lot 3.3 — Modal escalade exceptionnelle au directeur */}
          {!isRequesterView && (
            <Dialog
              open={showEscalateToDirectorForm}
              onOpenChange={(open) => {
                if (!open) { setShowEscalateToDirectorForm(false); setEscalateToDirectorReason(""); }
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <ArrowUpRight className="h-5 w-5" />
                    Escalade exceptionnelle au Directeur
                  </DialogTitle>
                  <DialogDescription>
                    Ce ticket sera transmis directement au directeur de votre direction,
                    sans passer par le chef hiérarchique le plus proche. Le motif sera enregistré
                    dans l'historique.
                  </DialogDescription>
                </DialogHeader>

                <div className="space-y-4 py-2">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      Motif <span className="text-destructive">*</span>
                    </label>
                    <textarea
                      value={escalateToDirectorReason}
                      onChange={(e) => setEscalateToDirectorReason(e.target.value)}
                      placeholder="Décrivez la raison de cette escalade exceptionnelle…"
                      rows={3}
                      className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive/40"
                    />
                  </div>
                </div>

                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => { setShowEscalateToDirectorForm(false); setEscalateToDirectorReason(""); }}
                  >
                    Annuler
                  </Button>
                  <Button
                    variant="destructive"
                    className="rounded-full"
                    disabled={!escalateToDirectorReason.trim() || escalateToDirectorMut.isPending}
                    onClick={() => escalateToDirectorMut.mutate()}
                  >
                    {escalateToDirectorMut.isPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <ArrowUpRight className="mr-1.5 h-4 w-4" />}
                    Confirmer l'escalade au directeur
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {/* BR-TRANSMIT-001 — Modal "Terminer le traitement" : résumé/solution/travail
              réalisé obligatoires, recommandations et pièces jointes facultatives. */}
          <Dialog
            open={showResolveForm}
            onOpenChange={(open) => {
              setShowResolveForm(open);
              if (!open) {
                setResolveSummary("");
                setResolveSolution("");
                setResolveWorkDone("");
                setResolveRecommendations("");
              }
            }}
          >
            <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                  Terminer le traitement
                </DialogTitle>
                <DialogDescription>
                  L'ensemble du ticket est complètement traité. Le demandeur sera notifié
                  et pourra confirmer la résolution ou demander une réouverture.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <div className="space-y-1.5">
                  <Label htmlFor="resolve-summary" className="text-sm font-medium">
                    Résumé final <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="resolve-summary"
                    value={resolveSummary}
                    onChange={(e) => setResolveSummary(e.target.value)}
                    placeholder="Résumé de la résolution…"
                    className="min-h-16 bg-background"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="resolve-solution" className="text-sm font-medium">
                    Solution appliquée <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="resolve-solution"
                    value={resolveSolution}
                    onChange={(e) => setResolveSolution(e.target.value)}
                    placeholder="Solution mise en œuvre…"
                    className="min-h-16 bg-background"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="resolve-work-done" className="text-sm font-medium">
                    Travail réalisé <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="resolve-work-done"
                    value={resolveWorkDone}
                    onChange={(e) => setResolveWorkDone(e.target.value)}
                    placeholder="Détail du travail effectué…"
                    className="min-h-16 bg-background"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="resolve-recommendations" className="text-sm font-medium">
                    Recommandations <span className="text-xs text-muted-foreground">(facultatif)</span>
                  </Label>
                  <Textarea
                    id="resolve-recommendations"
                    value={resolveRecommendations}
                    onChange={(e) => setResolveRecommendations(e.target.value)}
                    placeholder="Recommandations pour éviter que le problème ne se reproduise…"
                    className="min-h-14 bg-background"
                  />
                </div>
              </div>
              <DialogFooter className="gap-2">
                <Button variant="ghost" className="rounded-full"
                  onClick={() => setShowResolveForm(false)}>
                  Annuler
                </Button>
                <Button className="rounded-full gradient-primary"
                  disabled={
                    resolveMut.isPending
                    || !resolveSummary.trim()
                    || !resolveSolution.trim()
                    || !resolveWorkDone.trim()
                  }
                  onClick={() => resolveMut.mutate()}>
                  {resolveMut.isPending
                    ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    : <CheckCircle2 className="mr-1.5 h-4 w-4" />}
                  Terminer le traitement
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* BR-TRANSMIT-001 — Modal "Transmettre le traitement" : annuaire libre
              (direction/département/service/recherche), motif + travail effectué
              obligatoires, instruction et pièces jointes facultatives. */}
          <Dialog
            open={showTransmitForm}
            onOpenChange={(open) => {
              setShowTransmitForm(open);
              if (!open) resetTransmitForm();
            }}
          >
            <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <Send className="h-5 w-5 text-sky-600" />
                  Transmettre le traitement
                </DialogTitle>
                <DialogDescription>
                  Choisissez librement le prochain intervenant dans l'annuaire — aucune
                  chaîne fixe, le ticket reste dans son statut de traitement actif.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <div className="space-y-1.5">
                  <Label htmlFor="transmit-search" className="text-sm font-medium">
                    Recherche
                  </Label>
                  <input
                    id="transmit-search"
                    value={transmitSearch}
                    onChange={(e) => {
                      setTransmitSearch(e.target.value);
                      setTransmitTargetId("");
                    }}
                    placeholder="Nom d'un intervenant, dans toute l'organisation…"
                    className="w-full rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">Direction</Label>
                    <select
                      value={transmitDirectionId}
                      onChange={(e) => {
                        setTransmitDirectionId(e.target.value);
                        setTransmitDepartmentId("");
                        setTransmitUnitId("");
                        setTransmitTargetId("");
                      }}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Toutes</option>
                      {transmitDirections.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">Département</Label>
                    <select
                      value={transmitDepartmentId}
                      onChange={(e) => {
                        setTransmitDepartmentId(e.target.value);
                        setTransmitUnitId("");
                        setTransmitTargetId("");
                      }}
                      disabled={!transmitDirectionId}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
                    >
                      <option value="">Tous</option>
                      {transmitDepartments.map((d) => (
                        <option key={d.id} value={d.id}>{d.name}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs font-medium text-muted-foreground">Service</Label>
                    <select
                      value={transmitUnitId}
                      onChange={(e) => {
                        setTransmitUnitId(e.target.value);
                        setTransmitTargetId("");
                      }}
                      disabled={!transmitDepartmentId}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 disabled:opacity-50"
                    >
                      <option value="">Tous</option>
                      {transmitUnits.map((u) => (
                        <option key={u.id} value={u.id}>{u.name}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">
                    Personne cible <span className="text-destructive">*</span>
                  </Label>
                  {selectedTransmitPerson ? (
                    <div className="rounded-xl border border-primary/20 bg-primary/10 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-slate-900">
                            {[selectedTransmitPerson.firstname, selectedTransmitPerson.name].filter(Boolean).join(" ")}
                          </div>
                          <div className="mt-0.5 truncate text-xs text-muted-foreground">
                            {selectedTransmitPerson.email} · {roleLabels[selectedTransmitPerson.role as keyof typeof roleLabels] ?? selectedTransmitPerson.role}
                            {(selectedTransmitPerson.service ?? selectedTransmitPerson.direction) ? ` · ${selectedTransmitPerson.service ?? selectedTransmitPerson.direction}` : ""}
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setTransmitTargetId("");
                            setTransmitSearch("");
                          }}
                          className="rounded-full border border-border/70 bg-background px-3 py-1 text-xs text-slate-600 hover:bg-foreground/5"
                        >
                          Changer
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="max-h-48 space-y-1 overflow-y-auto rounded-xl border border-border/40 bg-background/40 p-1.5">
                      {transmitPeopleLoading ? (
                        <p className="px-2 py-3 text-center text-xs text-muted-foreground">Recherche en cours…</p>
                      ) : transmitPeople.length === 0 ? (
                        <p className="px-2 py-3 text-center text-xs text-muted-foreground">
                          {transmitSearch.trim() || transmitUnitId || transmitDepartmentId || transmitDirectionId
                            ? "Aucun intervenant actif trouvé pour ces critères."
                            : "Recherchez un nom ou affinez par direction/département/service."}
                        </p>
                      ) : (
                        transmitPeople.map((person) => (
                          <button
                            key={person.id}
                            type="button"
                            onClick={() => {
                              setTransmitTargetId(person.id);
                              setTransmitDirectionId(person.direction_id ?? "");
                              setTransmitDepartmentId(person.department_id ?? "");
                              setTransmitUnitId(person.unit_id ?? "");
                            }}
                            className={cn(
                              "flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-left text-sm transition",
                              transmitTargetId === person.id
                                ? "bg-primary/15 text-primary"
                                : "hover:bg-foreground/5",
                            )}
                          >
                            <span className="min-w-0">
                              <span className="block truncate font-medium">
                                {[person.firstname, person.name].filter(Boolean).join(" ")}
                              </span>
                              <span className="block truncate text-xs text-muted-foreground">
                                {person.email} · {roleLabels[person.role as keyof typeof roleLabels] ?? person.role}
                                {(person.service ?? person.direction) ? ` · ${person.service ?? person.direction}` : ""}
                              </span>
                            </span>
                            {transmitTargetId === person.id && <BadgeCheck className="h-4 w-4 shrink-0 text-primary" />}
                          </button>
                        ))
                      )}
                    </div>
                  )}
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="transmit-work-done" className="text-sm font-medium">
                    Travail effectué <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="transmit-work-done"
                    value={transmitWorkDone}
                    onChange={(e) => setTransmitWorkDone(e.target.value)}
                    placeholder="Ce qui a déjà été fait sur ce ticket…"
                    className="min-h-16 bg-background"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="transmit-reason" className="text-sm font-medium">
                    Motif <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="transmit-reason"
                    value={transmitReason}
                    onChange={(e) => setTransmitReason(e.target.value)}
                    placeholder="Pourquoi une autre intervention est nécessaire…"
                    className="min-h-14 bg-background"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="transmit-instruction" className="text-sm font-medium">
                    Instruction <span className="text-xs text-muted-foreground">(facultatif)</span>
                  </Label>
                  <Textarea
                    id="transmit-instruction"
                    value={transmitInstruction}
                    onChange={(e) => setTransmitInstruction(e.target.value)}
                    placeholder="Consigne pour le prochain intervenant…"
                    className="min-h-14 bg-background"
                  />
                </div>
              </div>
              <DialogFooter className="gap-2">
                <Button variant="ghost" className="rounded-full"
                  onClick={() => setShowTransmitForm(false)}>
                  Annuler
                </Button>
                <Button className="rounded-full gradient-primary"
                  disabled={
                    transmitMut.isPending
                    || !transmitTargetId
                    || !transmitWorkDone.trim()
                    || !transmitReason.trim()
                  }
                  onClick={() => transmitMut.mutate()}>
                  {transmitMut.isPending
                    ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    : <Send className="mr-1.5 h-4 w-4" />}
                  Transmettre
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* Director — Modal rejet */}
          {canRejectTicket && (
            <Dialog
              open={showRejectConfirm}
              onOpenChange={(open) => {
                setShowRejectConfirm(open);
                if (!open) setRejectNote("");
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-destructive">
                    <Ban className="h-5 w-5" />
                    Rejeter le ticket
                  </DialogTitle>
                  <DialogDescription>
                    Expliquez clairement pourquoi ce ticket est rejeté.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  <Label>
                    Motif du rejet <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    value={rejectNote}
                    onChange={(e) => setRejectNote(e.target.value)}
                    placeholder="Expliquez clairement pourquoi ce ticket est rejeté…"
                    className="min-h-24 bg-background"
                  />
                </div>
                <DialogFooter className="gap-2">
                  <Button variant="ghost" className="rounded-full"
                    onClick={() => { setShowRejectConfirm(false); setRejectNote(""); }}>
                    Annuler
                  </Button>
                  <Button variant="destructive" className="rounded-full"
                    disabled={!rejectNote.trim() || rejectMut.isPending} onClick={() => rejectMut.mutate()}>
                    {rejectMut.isPending ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : null}
                    Rejeter
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
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


          {canAssignTicket && (
            <Dialog open={showReassign} onOpenChange={setShowReassign}>
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <UserCheck className="h-5 w-5 text-primary" />
                    Réassigner le ticket
                  </DialogTitle>
                  <DialogDescription>
                    Sélectionnez l'agent qui prendra le ticket en charge.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  {agentPool.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-border/60 bg-background/35 px-4 py-5 text-sm text-muted-foreground">
                      Aucun agent disponible.
                    </p>
                  ) : (
                    <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
                      {agentPool.map((agent) => (
                        <button
                          key={agent.id}
                          type="button"
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-foreground/5"
                          onClick={() => assignMut.mutate(agent.id)}
                          disabled={assignMut.isPending}
                        >
                          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/10 text-[10px] font-bold text-primary">
                            {agent.name.slice(0, 2).toUpperCase()}
                          </span>
                          <span className="min-w-0 flex-1 truncate">{agent.name}</span>
                          {agent.availability && (
                            <span className="text-[10px] text-muted-foreground">{agent.availability}</span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="ghost" className="rounded-full" onClick={() => setShowReassign(false)}>
                    Fermer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {canChangePriority && (
            <Dialog open={showPriorityPicker} onOpenChange={setShowPriorityPicker}>
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <ChevronDown className="h-5 w-5 text-primary" />
                    Changer la priorité
                  </DialogTitle>
                  <DialogDescription>
                    Choisissez la nouvelle priorité de traitement.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid gap-2 py-2">
                  {(["low", "medium", "high", "critical"] as const).map((p) => (
                    <button
                      key={p}
                      type="button"
                      className="flex w-full items-center gap-2 rounded-xl border border-border/40 bg-background/35 px-3 py-2 text-left text-sm transition hover:bg-foreground/5"
                      onClick={() => changePriorityMut.mutate(p)}
                      disabled={changePriorityMut.isPending}
                    >
                      <PriorityBadge priority={p} />
                    </button>
                  ))}
                </div>
                <DialogFooter>
                  <Button variant="ghost" className="rounded-full" onClick={() => setShowPriorityPicker(false)}>
                    Fermer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {canChangeService && (
            <Dialog open={showServicePicker} onOpenChange={setShowServicePicker}>
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Building2 className="h-5 w-5 text-primary" />
                    Changer le service
                  </DialogTitle>
                  <DialogDescription>
                    Sélectionnez le service qui doit reprendre le ticket.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-2 py-2">
                  {availableServices.length === 0 ? (
                    <p className="rounded-xl border border-dashed border-border/60 bg-background/35 px-4 py-5 text-sm text-muted-foreground">
                      Aucun service disponible.
                    </p>
                  ) : (
                    <div className="max-h-72 space-y-1 overflow-y-auto pr-1">
                      {availableServices.map((svc) => (
                        <button
                          key={svc}
                          type="button"
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-foreground/5"
                          onClick={() => changeServiceMut.mutate(svc)}
                          disabled={changeServiceMut.isPending}
                        >
                          {svc}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button variant="ghost" className="rounded-full" onClick={() => setShowServicePicker(false)}>
                    Fermer
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          <div className="glass-strong overflow-visible rounded-[18px]">
            <div className="flex max-w-full items-center gap-0.5 overflow-x-auto border-b border-border/40 bg-background/10 px-2 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm">
                {detailTabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeDetailTab === tab.key;
                  const startsVisualGroup = tab.key === "comments" || tab.key === "sla";

                  return (
                    <button
                      key={tab.key}
                      type="button"
                      className={cn(
                        "inline-flex shrink-0 items-center gap-1.5 border-b-2 px-2 py-1.5 font-medium transition-colors sm:px-2.5",
                        startsVisualGroup && "relative ml-1 pl-3 before:absolute before:left-0 before:top-1.5 before:h-5 before:border-l before:border-border/30 sm:ml-2 sm:pl-4",
                        isActive
                          ? "border-primary text-primary"
                          : "border-transparent text-muted-foreground hover:text-foreground",
                      )}
                      onClick={() => setActiveDetailTab(tab.key)}
                    >
                      <Icon className="h-3.5 w-3.5" />
                      {tab.label}
                      {typeof tab.count === "number" && (
                        <span className={cn(
                          "rounded-full px-1.5 py-0.5 text-[10px]",
                          isActive ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground",
                        )}>
                          {tab.count}
                        </span>
                      )}
                    </button>
                  );
                })}
            </div>

            <div className="flex flex-col">
            <section className={cn("order-0 p-3 sm:p-4", activeDetailTab !== "description" && "hidden")}>
              <div className="rounded-2xl border border-border/45 bg-background/35 p-4">
                <h3 className="mb-3 flex items-center gap-2 font-semibold">
                  <FileText className="h-4 w-4 text-primary" />
                  Description du ticket
                </h3>
                <p className="whitespace-pre-wrap text-sm leading-7 text-muted-foreground">
                  {r.description}
                </p>
              </div>
            </section>

            <section className={cn("order-4 border-t border-border/40 p-3 sm:p-4", activeDetailTab !== "files" && "hidden")}>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div>
                  <h3 className="font-semibold">Pièces jointes</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Fichiers ajoutés à ce ticket.
                  </p>
                </div>
                <span className="rounded-full bg-muted px-2.5 py-1 text-[10px] font-medium text-muted-foreground">
                  {attachments.length} fichier{attachments.length > 1 ? "s" : ""}
                </span>
              </div>

              {attachmentsLoading ? (
                <div className="flex items-center gap-2 rounded-2xl border border-border/40 bg-background/40 px-4 py-3 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Chargement des pièces jointes…
                </div>
              ) : attachments.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border/60 bg-background/35 px-4 py-5 text-sm text-muted-foreground">
                  Aucune pièce jointe n'a encore été ajoutée à ce ticket.
                </div>
              ) : (
                <ul className="grid gap-3 lg:grid-cols-2">
                  {attachments.map((attachment) => {
                    const isOpeningAttachment =
                      attachmentAction?.id === attachment.id && attachmentAction.mode === "open";
                    const isDownloadingAttachment =
                      attachmentAction?.id === attachment.id && attachmentAction.mode === "download";
                    const isAttachmentBusy = attachmentAction?.id === attachment.id;

                    return (
                    <li
                      key={attachment.id}
                      className="flex min-w-0 flex-col gap-3 rounded-2xl border border-border/50 bg-background/55 p-3 sm:flex-row sm:items-center"
                    >
                      <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary/10 text-primary">
                        <FileText className="h-5 w-5" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">{attachment.filename}</p>
                        <p className="mt-0.5 truncate text-xs text-muted-foreground">
                          {attachmentTypeLabel(attachment.mime_type)} · {formatAttachmentSize(attachment.size_bytes)} ·{" "}
                          {formatAttachmentDate(attachment.created_at)}
                        </p>
                        {attachment.scan_status && (
                          <p className="mt-1 text-[11px] text-muted-foreground">
                            Scan : {attachment.scan_status}
                          </p>
                        )}
                      </div>
                      <div className="flex w-full shrink-0 items-center justify-end gap-1 sm:w-auto">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="h-9 flex-1 rounded-full px-3 sm:flex-none"
                          disabled={Boolean(isAttachmentBusy)}
                          onClick={() => void handleAttachmentFile(attachment, "open")}
                        >
                          {isOpeningAttachment ? (
                            <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                          ) : (
                            <ExternalLink className="mr-1.5 h-4 w-4" />
                          )}
                          Voir
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-9 w-9 rounded-full"
                          disabled={Boolean(isAttachmentBusy)}
                          title="Télécharger"
                          onClick={() => void handleAttachmentFile(attachment, "download")}
                        >
                          {isDownloadingAttachment ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Download className="h-4 w-4" />
                          )}
                        </Button>
                      </div>
                    </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className={cn("order-1 p-3 sm:p-4", activeDetailTab !== "journal" && "hidden")}>
              {/* BR-TRACE-001 — journal d'interventions hiérarchique (Cycle ->
                  Intervention) par défaut ; bascule possible vers la timeline
                  événement par événement déjà existante (audit fin). */}
              {(r.interventions?.length ?? 0) > 0 && (
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-1 rounded-full border border-border/50 bg-background/50 p-1 text-xs">
                    <button
                      type="button"
                      className={cn(
                        "rounded-full px-3 py-1 font-medium transition-colors",
                        journalView === "interventions" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                      onClick={() => setJournalView("interventions")}
                    >
                      Journal des interventions
                    </button>
                    <button
                      type="button"
                      className={cn(
                        "rounded-full px-3 py-1 font-medium transition-colors",
                        journalView === "events" ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:text-foreground",
                      )}
                      onClick={() => setJournalView("events")}
                    >
                      Chronologie complète
                    </button>
                  </div>
                  {journalView === "interventions" && (
                    <button
                      type="button"
                      disabled
                      title="Export du journal — bientôt disponible"
                      className="cursor-not-allowed rounded-full border border-border/50 px-3 py-1 text-xs font-medium text-muted-foreground opacity-60"
                    >
                      Exporter le journal
                    </button>
                  )}
                </div>
              )}
              <div className="max-h-[520px] overflow-y-auto pr-1">
                {journalView === "interventions" && (r.interventions?.length ?? 0) > 0 ? (
                  <InterventionJournal
                    interventions={r.interventions!}
                    events={r.timeline}
                    currentAssigneeId={r.assigneeId}
                    requestRef={r.ref}
                    onOpenAttachment={handleTimelineAttachmentOpen}
                  />
                ) : (
                  <WorkflowTimeline events={r.timeline} onOpenAttachment={handleTimelineAttachmentOpen} />
                )}
              </div>
            </section>

            <section className={cn("order-1 border-t border-border/40 p-3 sm:p-4", activeDetailTab !== "comments" && "hidden")}>
              {commentsPanel}
            </section>

            <section className={cn("order-2 border-t border-border/40 p-3 sm:p-4", activeDetailTab !== "sla" && "hidden")}>
              <div className="mb-4">
                <h3 className="font-semibold">Activité SLA</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Lecture basée uniquement sur le SLA et les événements disponibles du ticket.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Clock className="h-4 w-4 text-primary" />
                    <span className="truncate">Début SLA</span>
                  </div>
                  <p className="mt-2 truncate text-sm text-muted-foreground" title={createdAtLabel}>{createdAtLabel}</p>
                </div>
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <AlertTriangle className={cn("h-4 w-4", slaOver ? "text-destructive" : "text-success")} />
                    <span className="truncate">{slaOver ? "Expiration" : "Temps consommé"}</span>
                  </div>
                  <p className={cn("mt-2 truncate text-sm font-medium", slaOver ? "text-destructive" : "text-success")}>
                    {r.slaHours > 0 ? `${r.slaElapsed}h / ${r.slaHours}h` : "SLA non configuré"}
                  </p>
                </div>
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <ArrowUpRight className="h-4 w-4 text-amber-500" />
                    <span className="truncate">Escalade</span>
                  </div>
                  <p className="mt-2 truncate text-sm text-muted-foreground">
                    {r.timeline.some((event) => event.type.includes("escalat"))
                      ? "Escalade tracée dans le journal."
                      : "Aucune escalade tracée."}
                  </p>
                </div>
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <RotateCcw className="h-4 w-4 text-info" />
                    <span className="truncate">Historique</span>
                  </div>
                  <p className="mt-2 truncate text-sm text-muted-foreground">
                    {r.timeline.length} événement{r.timeline.length > 1 ? "s" : ""} disponible{r.timeline.length > 1 ? "s" : ""}.
                  </p>
                </div>
              </div>

              {/* BR-SLA-REOPEN-001 — cycles SLA distincts : le 1er traitement et chaque
                  traitement après réouverture sont mesurés indépendamment, sans jamais
                  recalculer un cycle déjà clos. */}
              {(r.slaCycles?.length ?? 0) > 1 && (
                <div className="mt-5 space-y-3">
                  <div>
                    <h3 className="font-semibold">Cycles SLA ({r.slaCycles!.length})</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Ce ticket a été réouvert {r.reopenCount ?? r.slaCycles!.length - 1} fois — chaque
                      traitement est mesuré indépendamment, le premier cycle n'est jamais recalculé.
                    </p>
                  </div>
                  <div className="space-y-3">
                    {r.slaCycles!.map((cycle) => (
                      <div
                        key={cycle.cycleNumber}
                        className={cn(
                          "rounded-2xl border p-3 sm:p-4",
                          cycle.breached
                            ? "border-destructive/40 bg-destructive/5"
                            : "border-border/50 bg-background/55",
                        )}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold">
                            {cycle.cycleNumber === 1
                              ? "Premier traitement"
                              : `Traitement après réouverture n°${cycle.cycleNumber - 1}`}
                          </h4>
                          {cycle.closed ? (
                            <span
                              className={cn(
                                "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                                cycle.breached
                                  ? "bg-destructive/15 text-destructive"
                                  : "bg-success/15 text-success",
                              )}
                            >
                              {cycle.breached ? "SLA dépassé" : "SLA respecté"}
                            </span>
                          ) : (
                            <span className="rounded-full bg-fuchsia-500/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-fuchsia-600">
                              En cours
                            </span>
                          )}
                        </div>
                        {cycle.reopenReason && (
                          <p className="mt-1.5 text-xs text-muted-foreground">
                            <span className="font-medium text-foreground">Motif de réouverture :</span>{" "}
                            {cycle.reopenReason}
                          </p>
                        )}
                        <dl className="mt-2.5 grid gap-2 text-xs sm:grid-cols-2 lg:grid-cols-4">
                          <div>
                            <dt className="text-muted-foreground">Début</dt>
                            <dd className="mt-0.5 font-medium">{formatTicketDateTime(cycle.startedAt)}</dd>
                          </div>
                          <div>
                            <dt className="text-muted-foreground">Fin</dt>
                            <dd className="mt-0.5 font-medium">
                              {cycle.closed ? formatTicketDateTime(cycle.endedAt) : "En cours"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-muted-foreground">Temps de résolution</dt>
                            <dd className="mt-0.5 font-medium">
                              {cycle.elapsedHours != null
                                ? `${cycle.elapsedHours}h${cycle.slaHours ? ` / ${cycle.slaHours}h` : ""}`
                                : "—"}
                            </dd>
                          </div>
                          <div>
                            <dt className="text-muted-foreground">Respect SLA</dt>
                            <dd
                              className={cn(
                                "mt-0.5 font-medium",
                                cycle.closed
                                  ? cycle.breached ? "text-destructive" : "text-success"
                                  : "text-muted-foreground",
                              )}
                            >
                              {cycle.closed ? (cycle.breached ? "Non" : "Oui") : "—"}
                            </dd>
                          </div>
                        </dl>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </section>

            <section className={cn("order-3 space-y-3 border-t border-border/40 p-3 sm:p-4", activeDetailTab !== "treatment" && "hidden")}>
              {treatmentActionsPanel}
            </section>

          </div>
          </div>

          {/* ── Panneau rejet (demandeur uniquement) ── */}
          {iAmRequester && r.status === "rejected" && (
            <GlassCard className="space-y-4 border-destructive/30 bg-destructive/5">
              <div className="flex items-start gap-3">
                <XCircle className="mt-0.5 h-5 w-5 shrink-0 text-destructive" />
                <div className="min-w-0 flex-1">
                  <h3 className="font-semibold text-destructive">Ticket rejeté</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Votre ticket a été examiné et n'a pas pu être traité dans son état actuel.
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
                  vous pouvez réouvrir ce ticket. L'historique complet sera conservé.
                </p>

                {!showReopenForm ? (
                  <Button
                    variant="outline"
                    className="rounded-full border-destructive/40 text-destructive hover:bg-destructive/10 hover:border-destructive/60"
                    onClick={() => setShowClosedRequestDialog(true)}
                  >
                    <RotateCcw className="mr-1.5 h-4 w-4" />
                    Réouvrir le ticket
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

          {iAmRequester && r.status === "resolved" && (r.infos as Record<string, unknown>)?.reopen_requested && (
            <GlassCard className="border-warning/30 bg-warning/5">
              <div className="flex items-start gap-3">
                <RotateCcw className="mt-0.5 h-5 w-5 shrink-0 text-warning" />
                <div className="min-w-0 flex-1 space-y-3">
                  <div>
                    <h3 className="font-semibold text-warning">Réouverture en attente d'approbation</h3>
                    <p className="mt-1 text-sm text-muted-foreground">
                      Votre demande de réouverture a été transmise au chef de service.
                      Vous serez notifié dès qu'une décision sera prise.
                    </p>
                  </div>
                </div>
              </div>
            </GlassCard>
          )}

          {isRequesterView && (
            <Dialog
              open={showClosedRequestDialog}
              onOpenChange={(open) => {
                setShowClosedRequestDialog(open);
                if (!open) setReopenReason("");
              }}
            >
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Lock className="h-5 w-5 text-muted-foreground" />
                    {r.status === "closed" ? "Ticket clôturé" : "Demander une réouverture"}
                  </DialogTitle>
                  <DialogDescription>
                    {r.status === "closed"
                      ? canReopenClosed
                        ? "Ce ticket a été fermé. Si votre problème persiste, vous pouvez encore le rouvrir."
                        : "Ce ticket est archivé. La fenêtre de réouverture (7 jours) est expirée — créez un nouveau ticket si nécessaire."
                      : "Expliquez pourquoi la résolution ne répond pas encore à votre besoin."}
                  </DialogDescription>
                </DialogHeader>

                {canRequestReopen && (
                  <div className="space-y-3 py-2">
                    <div className="space-y-1.5">
                      <Label>
                        Motif de réouverture <span className="text-destructive">*</span>
                      </Label>
                      <Textarea
                        value={reopenReason}
                        onChange={(e) => setReopenReason(e.target.value)}
                        placeholder="Décrivez précisément ce qui n'a pas été résolu…"
                        rows={4}
                      />
                    </div>
                  </div>
                )}

                <DialogFooter className="gap-2">
                  <Button
                    variant="ghost"
                    className="rounded-full"
                    onClick={() => {
                      setShowClosedRequestDialog(false);
                      setReopenReason("");
                    }}
                  >
                    Fermer
                  </Button>
                  {canRequestReopen && (
                    <Button
                      className="rounded-full gradient-primary"
                      disabled={requestReopenMut.isPending || !reopenReason.trim()}
                      onClick={() => requestReopenMut.mutate(reopenReason.trim())}
                    >
                      {requestReopenMut.isPending
                        ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                        : <RotateCcw className="mr-1.5 h-4 w-4" />}
                      Demander la réouverture
                    </Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {canOpenAppreciation && (
            <Dialog open={showAppreciationDialog} onOpenChange={setShowAppreciationDialog}>
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <Star className="h-5 w-5 text-muted-foreground" />
                    Votre avis
                  </DialogTitle>
                  <DialogDescription>
                    Évaluez la prise en charge de votre ticket.
                  </DialogDescription>
                </DialogHeader>
                <AppreciationForm
                  requestId={r.id}
                  authorType={authorType}
                  existing={localAppreciation ?? r.appreciation}
                  isClosed={r.status === "closed"}
                  onSubmit={(appr) => {
                    setLocalAppreciation(appr);
                    setShowAppreciationDialog(false);
                    invalidate();
                  }}
                  onReopen={() => {
                    setShowAppreciationDialog(false);
                    setShowClosedRequestDialog(true);
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
              </DialogContent>
            </Dialog>
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
                    Le ticket entrera dans la direction cible comme un ticket à qualifier.
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
                      placeholder="Expliquez pourquoi le ticket sort de votre direction…"
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
                    Un circuit de validation automatique sera créé pour ce ticket.
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

          {/* Dialog — Prévisualisation piece jointe (image zoomable / PDF) */}
          <Dialog open={!!previewFile} onOpenChange={(open) => { if (!open) closePreview(); }}>
            <DialogContent className="flex max-h-[90dvh] flex-col gap-0 overflow-hidden p-0 sm:max-w-4xl">
              <DialogHeader className="border-b border-border/40 px-5 py-4">
                <DialogTitle className="truncate pr-8 text-base">{previewFile?.filename}</DialogTitle>
              </DialogHeader>
              <div className="flex-1 overflow-auto bg-muted/30">
                {previewFile && previewFile.mimeType.startsWith("image/") ? (
                  <div className="flex min-h-full items-center justify-center p-4">
                    <img
                      src={previewFile.url}
                      alt={previewFile.filename}
                      className="max-h-[70dvh] max-w-full select-none rounded-lg shadow-sm transition-transform duration-150"
                      style={{ transform: `scale(${previewZoom})`, transformOrigin: "center" }}
                    />
                  </div>
                ) : previewFile && previewFile.mimeType === "application/pdf" ? (
                  <iframe src={previewFile.url} title={previewFile.filename} className="h-[75dvh] w-full" />
                ) : (
                  <div className="flex flex-col items-center justify-center gap-3 p-12 text-center text-sm text-muted-foreground">
                    <FileText className="h-10 w-10 opacity-50" />
                    <p>Aperçu non disponible pour ce type de fichier. Utilisez le téléchargement ci-dessous.</p>
                  </div>
                )}
              </div>
              <DialogFooter className="border-t border-border/40 px-5 py-3">
                {previewFile && previewFile.mimeType.startsWith("image/") && (
                  <div className="mr-auto flex items-center gap-1">
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      disabled={previewZoom <= 1}
                      onClick={() => setPreviewZoom((z) => Math.max(1, Number((z - 0.5).toFixed(1))))}
                    >
                      <ZoomOut className="h-4 w-4" />
                    </Button>
                    <span className="w-12 text-center text-xs text-muted-foreground">{Math.round(previewZoom * 100)}%</span>
                    <Button
                      type="button"
                      variant="outline"
                      size="icon"
                      className="h-8 w-8 rounded-full"
                      disabled={previewZoom >= 3}
                      onClick={() => setPreviewZoom((z) => Math.min(3, Number((z + 0.5).toFixed(1))))}
                    >
                      <ZoomIn className="h-4 w-4" />
                    </Button>
                  </div>
                )}
                <Button
                  type="button"
                  variant="outline"
                  className="rounded-full"
                  onClick={() => {
                    if (!previewFile) return;
                    const link = document.createElement("a");
                    link.href = previewFile.url;
                    link.download = previewFile.filename;
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                  }}
                >
                  <Download className="mr-1.5 h-4 w-4" />
                  Télécharger
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

        <aside className="min-w-0">
          <div className="flex flex-col gap-3">

          <section className={cn("order-2", sideCardClass)}>
            <div className="mb-3 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                Intervenants ({participants.length})
              </h3>
              {canToggleParticipants && (
                <button
                  type="button"
                  className="inline-flex items-center gap-1 text-xs font-medium text-primary transition hover:text-primary/80"
                  onClick={() => setShowAllParticipants(true)}
                >
                  Voir tout
                  <ArrowUpRight className="h-3.5 w-3.5" />
                </button>
              )}
            </div>
            {sideParticipants.length === 0 ? (
              <p className="text-sm text-muted-foreground">Aucun intervenant enregistré.</p>
            ) : (
              <ul className="space-y-3">
                {sideParticipants.map((participant) => (
                  <ParticipantRow key={participant.key} participant={participant} />
                ))}
              </ul>
            )}
          </section>

          <Dialog open={showAllParticipants} onOpenChange={setShowAllParticipants}>
            <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Intervenants ({participants.length})</DialogTitle>
                <DialogDescription>Toutes les personnes liées à ce ticket.</DialogDescription>
              </DialogHeader>
              <ul className="space-y-3">
                {participants.map((participant) => (
                  <ParticipantRow key={participant.key} participant={participant} />
                ))}
              </ul>
            </DialogContent>
          </Dialog>

          <section className={cn("order-3", sideCardClass)}>
            <div className="mb-4 flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-foreground">
                Détails du ticket
              </h3>
              <button
                type="button"
                className="inline-flex items-center gap-1 text-xs font-medium text-primary transition hover:text-primary/80"
                onClick={() => setShowAllDetails(true)}
              >
                Voir tout
                <ArrowUpRight className="h-3.5 w-3.5" />
              </button>
            </div>

            <div className="mb-2 flex items-center gap-2">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-emerald-500/15 text-emerald-500">
                <User className="h-3.5 w-3.5" />
              </span>
              <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-500">Ticket</h4>
            </div>
            <dl className="space-y-0 text-sm">
              <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Tag className="h-3.5 w-3.5" /> Catégorie
                </dt>
                <dd className="min-w-0 truncate font-medium" title={r.category}>{r.category}</dd>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" /> Créé le
                </dt>
                <dd className="text-xs font-medium">{createdAtLabel}</dd>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="h-3.5 w-3.5" />
                  {["resolved", "closed", "rejected", "cancelled"].includes(r.status)
                    ? (r.status === "rejected" ? "Rejeté le" : r.status === "cancelled" ? "Annulé le" : "Résolu le")
                    : "Mise à jour"}
                </dt>
                <dd className="text-xs font-medium">{updatedAtLabel}</dd>
              </div>
              <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                <dt className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <FileText className="h-3.5 w-3.5" /> ID du ticket
                </dt>
                <dd className="flex min-w-0 items-center gap-1.5 font-mono text-xs font-medium">
                  <span className="min-w-0 truncate">{r.ref}</span>
                  <button
                    type="button"
                    className="grid h-5 w-5 shrink-0 place-items-center rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                    title="Copier l'identifiant"
                    onClick={() => {
                      void navigator.clipboard.writeText(r.ref);
                      toast.success("Identifiant copié");
                    }}
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </dd>
              </div>
            </dl>
          </section>

          <Dialog open={showAllDetails} onOpenChange={setShowAllDetails}>
            <DialogContent className="max-h-[80vh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Détails du ticket</DialogTitle>
                <DialogDescription>Demandeur, traitement et délai de ce ticket.</DialogDescription>
              </DialogHeader>
              <div>
                <div className="mb-2 mt-2 flex items-center gap-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sky-500/15 text-sky-500">
                    <Building2 className="h-3.5 w-3.5" />
                  </span>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-sky-500">Demandeur</h4>
                </div>
                <dl className="space-y-0 text-sm">
                  {authorType === "internal" && (
                    <>
                      <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                        <dt className="text-xs text-muted-foreground">Direction</dt>
                        <dd className="truncate font-medium" title={requesterDirectionName}>{requesterDirectionName}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                        <dt className="text-xs text-muted-foreground">Département</dt>
                        <dd className="truncate font-medium" title={requesterDepartmentName}>{requesterDepartmentName}</dd>
                      </div>
                      <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                        <dt className="text-xs text-muted-foreground">Service</dt>
                        <dd className="truncate font-medium" title={requesterUnitName}>{requesterUnitName}</dd>
                      </div>
                    </>
                  )}
                  <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                    <dt className="text-xs text-muted-foreground">Demandeur</dt>
                    <dd className="truncate font-medium" title={r.requesterName}>{r.requesterName}</dd>
                  </div>
                </dl>

                <div className="mb-2 mt-4 flex items-center gap-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-violet-500/15 text-violet-500">
                    <UserCog className="h-3.5 w-3.5" />
                  </span>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-violet-500">Traitement</h4>
                </div>
                <dl className="space-y-0 text-sm">
                  <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                    <dt className="text-xs text-muted-foreground">Direction en charge</dt>
                    <dd className="truncate font-medium" title={directionName}>{directionName}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                    <dt className="text-xs text-muted-foreground">Département en charge</dt>
                    <dd className="truncate font-medium" title={departmentName}>{departmentName}</dd>
                  </div>
                  <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                    <dt className="text-xs text-muted-foreground">Service en charge</dt>
                    <dd className="truncate font-medium" title={unitName}>{unitName}</dd>
                  </div>
                  {isRequesterView && (
                    <div className="flex items-center justify-between gap-3 border-b border-border/30 py-3">
                      <dt className="text-xs text-muted-foreground">Agent en charge</dt>
                      <dd className="font-medium">
                        {r.assigneeId
                          ? assigneeDisplayName
                          : <span className="italic text-muted-foreground">En attente</span>}
                      </dd>
                    </div>
                  )}
                </dl>

                <div className="mt-4 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-amber-500">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-amber-500/15 text-amber-500">
                      <AlertTriangle className="h-3.5 w-3.5" />
                    </span>
                    Délai
                  </div>
                  <div className={cn("flex items-center gap-1.5 text-sm font-semibold", slaOver ? "text-destructive" : "text-success")}>
                    {slaOver && <AlertTriangle className="h-3.5 w-3.5" />}
                    {slaOver ? "Délai dépassé" : "Dans les délais"}
                  </div>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          </div>
        </aside>
      </div>

    </div>
  );
}

