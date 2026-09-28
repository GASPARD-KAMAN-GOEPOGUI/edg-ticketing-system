import { createFileRoute, Link, useSearch } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { prefetch } from "@/lib/prefetch";
import { useState, useRef, useEffect, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import type { RequestItem, Appreciation } from "@/lib/mock-data";
import { roleLabels, priorityLabels } from "@/lib/mock-data";
import { AppreciationForm } from "@/components/appreciation-form";
import { cn, formatElapsedHours } from "@/lib/utils";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  fetchRequest,
  resolveRequest,
  transmitTreatment,
  fetchTransmitTargets,
  assignRequest,
  reopenRequest,
  closeRequest,
  updateRequest,
  changeRequestPriority,
  cancelRequest,
  uploadAttachment,
  fetchAttachments,
  fetchAttachmentFile,
  rejectTicket,
  reassignService,
  transferDirection,
  requesterEditRequest,
  exportRequestDossier,
  downloadPvIntervention,
  submitPvIntervention,
  archivePvIntervention,
  fetchProposedSolution,
  submitFieldCheck,
  startTreatment,
  type RawAttachment,
} from "@/lib/api/requests";
import { fetchRequestCategories } from "@/lib/api/admin-config";
import { buildAvatarUrl, fetchUser, fetchUsers, fetchUsersByIds, type AccountUser } from "@/lib/api/accounts";
import { fetchDirections, fetchDepartments, fetchUnits, fetchUnit } from "@/lib/api/directions-units";
import type { Direction, Unit } from "@/lib/api/directions-units";
import { useDebounce } from "@/lib/hooks/use-debounce";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { submitAppreciation, updateRequestAppreciation } from "@/lib/api/csat";
import {
  fetchRequestWorkflows,
  type WorkflowItem,
} from "@/lib/api/workflow";

import {
  ArrowLeft,
  Clock,
  Paperclip,
  Download,
  ExternalLink,
  Archive,
  ClipboardCheck,
  PlayCircle,
  FileText,
  Lightbulb,
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
  FileSpreadsheet,
  MoreHorizontal,
  type LucideIcon,
} from "lucide-react";
import { toast } from "sonner";
import { copyWithToast } from "@/lib/clipboard";
import { formatDistanceToNow, format, differenceInDays } from "date-fns";
import { fr } from "date-fns/locale";
import { canTicketAction, isRequester } from "@/lib/capabilities";

export const Route = createFileRoute("/app/requests/$id")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Détail ticket — EDG Support" }] }),
  // Précharge le ticket + ses pièces jointes en parallèle au survol du lien —
  // mêmes queryKeys que les useQuery du composant (context="requests" ici).
  loader: ({ context: { queryClient }, params: { id } }) =>
    Promise.all([
      prefetch(queryClient.ensureQueryData({
        queryKey: ["request", id, "active"],
        queryFn: () => fetchRequest(id, { includeDeleted: false }),
        staleTime: 15_000,
      })),
      prefetch(queryClient.ensureQueryData({
        queryKey: ["request", id, "active", "attachments"],
        queryFn: () => fetchAttachments(id),
        staleTime: 30_000,
      })),
    ]),
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
  distribution: {
    eyebrow: "Distribution",
    backLabel: "Retour à la distribution",
    notFoundBackLabel: "Retour à la distribution",
    backTo: "/app/distribution",
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
  resolved: {
    eyebrow: "Tickets résolus",
    backLabel: "Retour aux tickets résolus",
    notFoundBackLabel: "Retour aux tickets résolus",
    backTo: "/app/resolved",
  },
} as const;

/** Contextes en LECTURE SEULE du traitement : le travail y est terminé, le
 *  panneau Traitement n'expose donc qu'une consultation du PV d'intervention
 *  et aucune action mutante. Les gardes serveur restent la vraie protection ;
 *  ceci évite seulement de proposer des gestes qui n'ont plus lieu d'être. */
const READ_ONLY_TREATMENT_CONTEXTS = new Set<RequestDetailContext>(["resolved"]);

export type RequestDetailContext = keyof typeof DETAIL_CONTEXTS;
// Messagerie retiree le 2026-09-25 : plus d'onglet "comments".
type DetailTab = "description" | "files" | "sla" | "treatment";
type DirectTreatmentAction =
  | "selfAssign"
  | "close";

// BR-TRANSMIT-001 — rôles pouvant devenir/rester "intervenant actuel" d'un ticket
// (cible valide pour une transmission). Doit rester aligné avec TREATING_ROLES
// côté backend (ticket_actions.py).
const TREATING_ROLES = new Set(["chief-service", "technicien", "chef-division-support", "chief-departement", "director"]);

type RequestDetailPageProps = {
  id: string;
  context?: RequestDetailContext;
};

type Participant = {
  key: string;
  name: string;
  role?: string;
  detail: string;
  /** Première action de cet acteur — détermine sa position dans la chaîne. */
  firstAt?: string;
  /** Dernière action connue — c'est elle qui est décrite par `detail`. */
  lastAt?: string;
  avatar?: string;
};

const COMMENT_EMOJIS = [
  "😀", "😃", "😄", "😁", "😊", "🙂", "😉", "😍", "🤩", "😘",
  "😅", "😂", "🤣", "😇", "🙃", "😜", "🤔", "😐", "😴", "😪",
  "😢", "😭", "😡", "😱", "😳", "🥳", "😷", "🤒", "🤕", "🤗",
  "👍", "👎", "👏", "🙏", "💪", "👌", "✌️", "🤝", "🙌", "🤞",
  "❤️", "🔥", "⭐", "✅", "❌", "⚠️", "❓", "❗", "💡", "📌",
] as const;

const PARTICIPANT_ROLE_LABELS: Record<string, string> = {
  user: "Requérant",
  "chief-service": "Chef de Service",
  technicien: "Technicien",
  "chef-division-support": "Chef de Division Support",
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
        <span className="absolute inset-0 grid place-items-center overflow-hidden rounded-full">
          {participant.avatar ? (
            <img
              src={buildAvatarUrl(participant.avatar)}
              alt={participant.name}
              className="h-full w-full object-cover"
            />
          ) : (
            initialsFor(participant.name)
          )}
        </span>
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

/**
 * Chaîne des intervenants d'un ticket, dans l'ordre où ils sont intervenus.
 *
 * Règle métier : **est intervenant quiconque a posé une ACTION sur le ticket**,
 * et rien d'autre. Créer la demande est une action, la qualifier en est une,
 * l'envoyer au chef de division ou la prendre pour soi en est une, la traiter
 * en est une. Recevoir un ticket dans sa file n'en est PAS une : tant qu'un
 * acteur n'a rien fait, il n'apparaît pas — on ne dévoile jamais quelqu'un dont
 * le tour d'intervention n'est pas encore venu.
 *
 * La timeline est la source : chaque action y laisse un événement horodaté
 * portant son auteur (`actor_id`/`actor_name`/`actor_role`, cf.
 * `ServiceRequest.py`). Elle couvre donc toute la chaîne, y compris la création
 * et la qualification — contrairement aux `interventions` (BR-TRACE-001), qui
 * ne tracent que le traitement et ignorent ces deux étapes.
 *
 * Un acteur qui intervient plusieurs fois reste UNE entrée, placée à sa
 * première action ; `detail` décrit alors sa dernière action connue.
 *
 * Le rôle affiché vient de l'action elle-même, jamais d'une supposition : un
 * chef de service ou un chef de division qui prend le ticket pour le traiter
 * apparaît à sa place dans la chaîne, avec son vrai rôle.
 */
function buildParticipants(
  request: RequestItem,
  assigneeName?: string,
): Participant[] {
  const avatars = request.participantAvatars ?? {};
  const participants = new Map<string, Participant>();
  const add = (candidate: Participant) => {
    const normalized = candidate.key || `${candidate.name}-${candidate.role ?? ""}`;
    const existing = participants.get(normalized);
    if (!existing) {
      participants.set(normalized, { ...candidate, firstAt: candidate.firstAt ?? candidate.lastAt });
      return;
    }
    const isMoreRecent = candidate.lastAt && (!existing.lastAt || candidate.lastAt > existing.lastAt);
    const isEarlier = candidate.lastAt && (!existing.firstAt || candidate.lastAt < existing.firstAt);
    participants.set(normalized, {
      ...existing,
      // Le rôle le plus précis l'emporte : celui porté par l'action réelle.
      role: existing.role ?? candidate.role,
      detail: isMoreRecent ? candidate.detail : existing.detail,
      lastAt: isMoreRecent ? candidate.lastAt : existing.lastAt,
      firstAt: isEarlier ? candidate.lastAt : existing.firstAt,
      avatar: existing.avatar ?? candidate.avatar,
    });
  };

  // Création : première action de la chaîne, toujours celle du demandeur.
  // Volontairement sans rôle : l'événement `created` de la timeline porte le
  // vrai `actor_role` du demandeur et viendra le renseigner. Le figer à "user"
  // afficherait un rôle faux dès qu'un chef de service ou un technicien crée
  // une demande pour lui-même.
  if (request.requesterName) {
    add({
      key: request.requesterId || `requester-${request.requesterName}`,
      name: request.requesterName,
      detail: "Créateur",
      lastAt: request.createdAt,
      avatar: request.requesterId ? avatars[request.requesterId] : undefined,
    });
  }

  // Chaque événement de timeline est une action : son auteur est un intervenant.
  // L'ancienne branche `event.targetUserName` ("Destinataire") est retirée —
  // elle affichait le prochain acteur AVANT qu'il n'ait agi.
  for (const event of request.timeline) {
    if (!event.by) continue;
    add({
      key: event.actorId || `actor-${event.by}`,
      name: event.by,
      role: event.actorRole,
      detail: event.label,
      lastAt: event.at,
      avatar: event.actorId ? avatars[event.actorId] : undefined,
    });
  }

  // Intervenant courant : ajouté seulement s'il a déjà agi (donc déjà présent
  // via la timeline). On enrichit alors son libellé, sans jamais créer une
  // entrée pour un assigné qui n'aurait encore rien fait.
  const currentHandlerKey = request.assigneeId
    || (assigneeName ?? request.assigneeName ? `actor-${assigneeName ?? request.assigneeName}` : undefined);
  if (currentHandlerKey) {
    const current = participants.get(currentHandlerKey);
    if (current) {
      participants.set(currentHandlerKey, {
        ...current,
        name: assigneeName ?? current.name,
        detail: `${current.detail} · en charge`,
      });
    }
  }

  // Ordre d'intervention : première action croissante.
  return Array.from(participants.values()).sort((a, b) => {
    const aTime = a.firstAt ? new Date(a.firstAt).getTime() : 0;
    const bTime = b.firstAt ? new Date(b.firstAt).getTime() : 0;
    return aTime - bTime;
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

type FixedStepState = "done" | "active" | "pending" | "cancelled";

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
  // rejected/cancelled reviennent au point initial (étape "Ouverture") plutôt
  // que de rester bloqués sur l'étape où l'annulation/le rejet a eu lieu — le
  // marqueur rouge à l'étape 1 signale l'arrêt du cycle de vie.
  rejected: 0,
  cancelled: 0,
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
    else if (index === currentIndex) state = isRejectedOrCancelled ? "cancelled" : "active";
    else state = "pending";

    const dateLabel =
      state === "done" ? (formatTraceDate(stepDates[index]) ?? "—")
      : state === "cancelled" ? (DETAIL_STATUS_LABELS[status] ?? status)
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
                    step.state === "cancelled" && "border-destructive bg-destructive text-white shadow-destructive/25",
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
  // Lien profond depuis une notification : ouvrir la fiche sur le panneau
  // d'actions plutot que sur la description. Indispensable pour le demandeur,
  // dont le contexte personnel ouvre normalement sur la description : une
  // notification "votre validation est attendue" doit montrer l'action, pas
  // le descriptif du ticket.
  const wantsTreatmentDeepLink = deepLinkSearch.tab === "treatment";
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
    staleTime: 30_000,
  });

  const [comment, setComment] = useState("");
  const [stagedFile, setStagedFile] = useState<File | null>(null);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [isDirective, setIsDirective] = useState(false);
  // BR-MESSAGING-PAIR-001 — conversation sélectionnée dans le sélecteur multi-fils
  // (demandeur avec plusieurs intervenants successifs, ou supervision admin).
  // undefined = pas de choix explicite, la valeur par défaut est recalculée au rendu.
  const [selectedPeerId, setSelectedPeerId] = useState<string | undefined>(undefined);
  const [role] = useRole();
  // Dans "Mes demandes", le propriétaire garde la vue demandeur. Dans les espaces
  // métier, le contexte fonctionnel prime sur la propriété personnelle du ticket.
  const iAmRequester = isRequester(r?.requesterId, sessionUser?.id);
  const isRequesterView = role === "user" || (isPersonalContext && iAmRequester);
  const isAgentOnly = (role === "chief-service" || role === "technicien" || role === "chef-division-support") && !iAmRequester;
  // Procédure EDG/PS-GSI/Pro-02 tâche 1.3 — descriptif de solution proposée,
  // servi par un endpoint dédié et gardé (il n'est pas dans la fiche du ticket,
  // que le demandeur peut lire). On ne l'interroge que pour un intervenant du
  // support qui n'est pas le demandeur de CE ticket : sinon le backend répond
  // 403, et il n'y a aucune raison de déclencher l'appel.
  const canSeeProposedSolution = Boolean(
    r && !iAmRequester &&
    ["chief-service", "technicien", "chef-division-support", "chief-departement", "director", "admin"]
      .includes(role ?? ""),
  );
  const { data: proposedSolution } = useQuery({
    queryKey: [...requestQueryKey, "proposed-solution"],
    queryFn: () => fetchProposedSolution(id),
    enabled: canSeeProposedSolution,
    staleTime: 60_000,
  });
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
  // Procédure tâche 2.1 — constat d'intervention (technicien uniquement).
  const [showFieldCheckForm, setShowFieldCheckForm] = useState(false);
  const [fieldCheckConformity, setFieldCheckConformity] = useState<"conforme" | "ecart">("conforme");
  const [fieldCheckFindings, setFieldCheckFindings] = useState("");
  // Catégorie et priorité observées sont choisies dans une liste, jamais tapées :
  // le constat sert à confronter le terrain à la qualification du chef de service,
  // ce qui suppose le même vocabulaire de part et d'autre. On stocke le libellé
  // lisible (« Incident », « Haute »), car ces valeurs sont destinées à être lues.
  const [observedCategory, setObservedCategory] = useState("");
  const [observedPriority, setObservedPriority] = useState("");
  // BR-TRAITEMENT-PROGRESSIF-001 — « Démarrer le traitement ». Seul le lieu est
  // saisi : date et heure de début sont horodatées par le serveur.
  const [showStartForm, setShowStartForm] = useState(false);
  const [startLocation, setStartLocation] = useState("");
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
  const [showServicePicker, setShowServicePicker] = useState(false);
  const [showDirectionTransfer, setShowDirectionTransfer] = useState(false);
  const [transferDirectionId, setTransferDirectionId] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [showClosedRequestDialog, setShowClosedRequestDialog] = useState(false);
  const [showAppreciationDialog, setShowAppreciationDialog] = useState(false);
  const [directTreatmentAction, setDirectTreatmentAction] =
    useState<DirectTreatmentAction | null>(null);
  // Espaces de traitement (queue, boîtes de chef, supervision, direction…) :
  // on ouvre directement sur "Traitement" puisque c'est là que se trouvent
  // désormais les actions (déplacées depuis les boutons de la card liste).
  // Le contexte personnel ("Mes demandes") reste sur la description.
  const [activeDetailTab, setActiveDetailTab] = useState<DetailTab>(
    wantsTreatmentDeepLink || !isPersonalContext ? "treatment" : "description",
  );
  const [showAllParticipants, setShowAllParticipants] = useState(false);
  const [showAllDetails, setShowAllDetails] = useState(false);
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
  const [exportPending, setExportPending] = useState(false);
  const [pvPending, setPvPending] = useState(false);
  // Aperçu du PV : URL d'objet créée à la volée depuis le blob, révoquée à la
  // fermeture pour ne pas retenir le document en mémoire.
  const [pvPreviewUrl, setPvPreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (previewFile) URL.revokeObjectURL(previewFile.url);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


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

  const handleExportDossier = async (format: "excel" | "pdf") => {
    setExportPending(true);
    try {
      const { blob, filename } = await exportRequestDossier(id, format);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1_000);
      toast.success("Dossier de la demande exporté.");
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      toast.error(message ? `Impossible de générer l'export : ${message}` : "Impossible de générer l'export.");
    } finally {
      setExportPending(false);
    }
  };

  /** Procédure tâche 3.1 — PV d'intervention au format officiel
   *  EDG/PS-GSI/PV-01. Depuis le 2026-09-27, les validations faites dans
   *  l'application (traitement terminé, dépannage validé par le demandeur) sont
   *  portées sur le document sous forme d'émargement électronique : il n'y a
   *  plus de signature manuscrite à recueillir. */
  const handleDownloadPv = async () => {
    setPvPending(true);
    try {
      const { blob, filename } = await downloadPvIntervention(id);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename.toLowerCase().endsWith(".pdf") ? filename : `${filename}.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1_000);
      toast.success("PV d'intervention généré.");
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      toast.error(message ? `Impossible de générer le PV : ${message}` : "Impossible de générer le PV.");
    } finally {
      setPvPending(false);
    }
  };

  /** Onglet « Tickets résolus » — consultation seule : le PV s'ouvre dans un
   *  visualiseur intégré, sans jamais être enregistré sur le poste. Même
   *  source que le téléchargement (`GET /requests/{id}/pv`), qui est en
   *  lecture seule côté serveur : aucun statut, aucune notification. */
  const handlePreviewPv = async () => {
    setPvPending(true);
    try {
      const { blob } = await downloadPvIntervention(id);
      setPvPreviewUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return URL.createObjectURL(blob);
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : undefined;
      toast.error(message ? `Impossible d'ouvrir le PV : ${message}` : "Impossible d'ouvrir le PV.");
    } finally {
      setPvPending(false);
    }
  };

  const closePvPreview = () => {
    setPvPreviewUrl((previous) => {
      if (previous) URL.revokeObjectURL(previous);
      return null;
    });
  };

  // Même référentiel que la qualification du chef de service (File d'attente) :
  // les deux bouts de la comparaison doivent parler la même langue.
  const { data: observedCategoryItems = [] } = useQuery({
    queryKey: ["admin-ref", "request_categories"],
    queryFn: fetchRequestCategories,
    staleTime: 300_000,
  });
  const observedCategories = observedCategoryItems
    .filter((c) => c.status)
    .map((c) => c.label);

  // Un écart remet en cause la qualification du chef de service : le caractériser
  // est obligatoire, au même titre que les observations. Un constat conforme n'a
  // rien à caractériser — les deux champs ne lui sont d'ailleurs pas présentés.
  const canSubmitFieldCheck = Boolean(
    fieldCheckFindings.trim()
    && (fieldCheckConformity !== "ecart" || (observedCategory && observedPriority)),
  );

  const startMut = useMutation({
    mutationFn: () => startTreatment(id, startLocation.trim()),
    onSuccess: () => {
      toast.success("Traitement démarré.");
      setShowStartForm(false);
      setStartLocation("");
      qc.invalidateQueries({ queryKey: requestQueryKey });
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["my-tickets"] });
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Impossible de démarrer le traitement.");
    },
  });

  // Procédure EDG/PS-GSI/Pro-02 tâche 2.1 — « Qualifier la demande », point de
  // contrôle « vérification de l'état réel de la requête ». Précède la tâche 2.2
  // (résolution), que le backend refuse tant que le constat manque.
  const fieldCheckMut = useMutation({
    mutationFn: () => submitFieldCheck(id, {
      conformity: fieldCheckConformity,
      findings: fieldCheckFindings.trim(),
      // Bornés à l'écart : sinon des valeurs saisies puis masquées par un retour
      // à « conforme » partiraient quand même, contredisant le constat envoyé.
      observed_category: fieldCheckConformity === "ecart" ? observedCategory : undefined,
      observed_priority: fieldCheckConformity === "ecart" ? observedPriority : undefined,
    }),
    onSuccess: () => {
      toast.success(
        fieldCheckConformity === "ecart"
          ? "Constat enregistré — le chef de service a été prévenu de l'écart."
          : "Constat enregistré.",
      );
      setShowFieldCheckForm(false);
      setFieldCheckFindings("");
      setObservedCategory("");
      setObservedPriority("");
      setFieldCheckConformity("conforme");
    },
    onError: (err) => {
      toast.error(err instanceof Error ? err.message : "Impossible d'enregistrer le constat.");
    },
    onSettled: () => invalidate(),
  });

  // Procédure tâche 3.3 — « Soumettre le PV d'intervention au Chef de division ».
  // Le destinataire n'est pas choisi : c'est le chef de division qui a réparti
  // le ticket (tâche 1.4).
  const pvSubmitMut = useMutation({
    mutationFn: () => submitPvIntervention(id),
    onSuccess: () => toast.success("PV soumis au chef de division."),
    onError: (err) => toast.error(
      err instanceof Error ? err.message : "Impossible de soumettre le PV.",
    ),
    onSettled: () => invalidate(),
  });

  // Procédure tâche 3.4 — « Enregistrer et archiver le PV d'intervention ».
  const pvArchiveMut = useMutation({
    mutationFn: () => archivePvIntervention(id),
    onSuccess: () => toast.success("PV enregistré et archivé."),
    onError: (err) => toast.error(
      err instanceof Error ? err.message : "Impossible d'archiver le PV.",
    ),
    onSettled: () => invalidate(),
  });

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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de terminer le traitement.");
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de transmettre le traitement.");
    },
    onSettled: () => invalidate(),
  });

  const assignMut = useMutation({
    mutationFn: (assigneeId: string) => assignRequest(id, assigneeId),
    onMutate: async (assigneeId) => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      // BR-QUEUE-AUTO-START-001 : une assignation démarre directement le
      // traitement (`in_progress`), plus d'étape "assigned" intermédiaire.
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, assigneeId, status: "in_progress" } : old,
      );
      return { previous };
    },
    onSuccess: (_, assigneeId) => {
      const agent = agentPool.find((u) => u.id === assigneeId);
      toast.success(`Réassigné à ${agent?.name ?? assigneeId} — traitement démarré.`);
      setShowReassign(false);
    },
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de réassigner le ticket.");
    },
    onSettled: () => invalidate(),
  });

  const selfAssignMut = useMutation({
    mutationFn: () => assignRequest(id, String(sessionUser?.id ?? "")),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      // BR-QUEUE-AUTO-START-001 : "M'assigner" démarre directement le
      // traitement (`in_progress`), plus d'étape "assigned" intermédiaire.
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old
          ? {
              ...old,
              assigneeId: String(sessionUser?.id ?? ""),
              assigneeName: authorName,
              status: "in_progress",
            }
          : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Ticket pris en charge — traitement démarré.");
      setDirectTreatmentAction(null);
    },
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      // Le backend explique precisement le refus (ticket en cours de
      // repartition, hors perimetre, transition invalide...). Ecraser ce
      // message par un libelle generique laissait l'utilisateur sans la
      // moindre raison — on remonte donc le message reel, avec un repli
      // uniquement si l'erreur n'en porte pas (panne reseau, par exemple).
      toast.error(err instanceof Error ? err.message : "Impossible de vous assigner ce ticket.");
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

  // BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : un seul appel, motif
  // obligatoire, aucune approbation hiérarchique — le ticket retourne directement
  // en File d'attente pour un nouveau cycle de traitement.
  const requestReopenMut = useMutation({
    mutationFn: (reason: string) => reopenRequest(id, reason),
    onMutate: async () => {
      await qc.cancelQueries({ queryKey: requestQueryKey });
      const previous = qc.getQueryData<RequestItem>(requestQueryKey);
      qc.setQueryData<RequestItem>(requestQueryKey, (old) =>
        old ? { ...old, status: "reopened" } : old,
      );
      return { previous };
    },
    onSuccess: () => {
      toast.success("Ticket réouvert et replacé dans la File d'attente.");
      setShowReopenForm(false);
      setShowClosedRequestDialog(false);
      setReopenReason("");
    },
    onError: (err: unknown, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      const msg = (err as { message?: string })?.message;
      toast.error(msg ?? "Impossible de réouvrir le ticket.");
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de clôturer le ticket.");
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible d'annuler le ticket.");
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de changer la priorité.");
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de rejeter le ticket.");
    },
    onSettled: () => invalidate(),
  });

  const changeServiceMut = useMutation({
    mutationFn: (unit_id: string) => reassignService(id, unit_id, "Réaffectation depuis le détail ticket"),
    onSuccess: (_, s) => { toast.success(`Service changé → ${s}.`); setShowServicePicker(false); invalidate(); },
    onError: (err) => toast.error(err instanceof Error ? err.message : "Impossible de changer le service."),
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
    onError: (err, _vars, context) => {
      if (context?.previous) qc.setQueryData(requestQueryKey, context.previous);
      toast.error(err instanceof Error ? err.message : "Impossible de transférer le ticket.");
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
    queryFn: () => fetchUsers({ role: "chief-service", limit: 100 }),
    enabled: !isRequesterView,
    staleTime: 120_000,
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
  // BR-TRANSMIT-SCOPE-TECH-001 — le serveur décide qui un acteur peut viser.
  // Pour un technicien il renvoie `restricted: true` et la liste fermée de ses
  // cibles (collègues techniciens de son service + le responsable qui lui a
  // confié le ticket) : on masque alors les filtres direction/département/service
  // et la recherche libre, remplacés par une simple sélection. Le backend refuse
  // de toute façon une cible hors périmètre — l'interface ne fait que refléter
  // la règle, elle ne la porte pas.
  const { data: transmitScope } = useQuery({
    queryKey: ["transmit-targets", id],
    queryFn: () => fetchTransmitTargets(id),
    enabled: showTransmitForm,
    staleTime: 30_000,
  });
  const transmitRestricted = transmitScope?.restricted === true;
  const transmitTargets = useMemo(() => transmitScope?.items ?? [], [transmitScope]);

  const { data: transmitDirections = [] } = useQuery({
    queryKey: ["directions", "active"],
    queryFn: () => fetchDirections({ status: "active" }),
    enabled: showTransmitForm && !transmitRestricted,
    staleTime: 5 * 60_000,
  });
  const { data: transmitDepartments = [] } = useQuery({
    queryKey: ["departments", transmitDirectionId, "active"],
    queryFn: () => fetchDepartments({ directionId: transmitDirectionId, status: "active" }),
    enabled: showTransmitForm && !transmitRestricted && !!transmitDirectionId,
    staleTime: 5 * 60_000,
  });
  const { data: transmitUnits = [] } = useQuery({
    queryKey: ["units", transmitDepartmentId, "active"],
    queryFn: () => fetchUnits({ departmentId: transmitDepartmentId, status: "active" }),
    enabled: showTransmitForm && !transmitRestricted && !!transmitDepartmentId,
    staleTime: 5 * 60_000,
  });
  const currentUserId = String(sessionUser?.id ?? "");
  const requesterIdForFilter = r?.requesterId ? String(r.requesterId) : "";
  // BR-REQUESTER-NO-SELF-TREATMENT-001 — le demandeur du ticket ne doit jamais
  // être sélectionnable comme prochain intervenant (en plus de l'acteur courant).
  const filterCurrentUser = (users: AccountUser[]) =>
    users.filter((user) => String(user.id) !== currentUserId && String(user.id) !== requesterIdForFilter);
  // Sélecteur @mention — préfixe "@" facultatif (purement cosmétique, le champ est
  // entièrement dédié à la recherche de personne), débounce 400ms (même hook et
  // délai que app.admin.logs.tsx) avant de solliciter le backend.
  const debouncedTransmitSearch = useDebounce(transmitSearch, 400);
  const transmitSearchTerm = debouncedTransmitSearch.trim().replace(/^@+/, "").trim();
  const { data: transmitPeople = [], isFetching: transmitPeopleLoading } = useQuery({
    queryKey: [
      "transmit-people", transmitSearchTerm, transmitUnitId, transmitDepartmentId, transmitDirectionId, currentUserId,
    ],
    queryFn: async () => {
      if (transmitSearchTerm) {
        // Recherche libre combinée au filtre organigramme déjà posé (le plus
        // précis en premier) — le backend applique désormais les deux ensemble
        // au lieu de les ignorer (voir RepositoryAccount.search côté API).
        const scope = transmitUnitId
          ? { unit_id: transmitUnitId }
          : transmitDepartmentId
            ? { unit_id: transmitDepartmentId }
            : transmitDirectionId
              ? { direction_id: transmitDirectionId }
              : {};
        const res = await fetchUsers({ search: transmitSearchTerm, ...scope, limit: 50 });
        return filterCurrentUser(res.items.filter((u) => TREATING_ROLES.has(u.role)));
      }
      if (transmitUnitId) {
        const res = await fetchUsers({ role: "chief-service", unit_id: transmitUnitId, limit: 100 });
        return filterCurrentUser(res.items);
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
    enabled: showTransmitForm && !transmitRestricted,
    staleTime: 30_000,
  });
  const selectedTransmitPerson = useMemo(
    () => transmitPeople.find((person) => person.id === transmitTargetId),
    [transmitPeople, transmitTargetId],
  );

  // Résolution Direction/Département réelle de la personne sélectionnée : les
  // comptes non-directeurs n'exposent pas direction_id/department_id (aucune
  // colonne dédiée côté compte, cf. audit), donc on résout via /units/{id}
  // (déjà utilisé ailleurs, department_id/direction_id/*_name déjà résolus
  // côté backend) plutôt que de dépendre de champs vides sur la personne.
  const { data: selectedPersonUnit } = useQuery({
    queryKey: ["unit-detail", selectedTransmitPerson?.unit_id],
    queryFn: () => fetchUnit(selectedTransmitPerson!.unit_id!),
    enabled: !!transmitTargetId && !!selectedTransmitPerson?.unit_id,
    staleTime: 5 * 60_000,
  });

  useEffect(() => {
    if (!transmitTargetId || !selectedPersonUnit) return;
    if (selectedPersonUnit.direction_id && transmitDirectionId !== selectedPersonUnit.direction_id) {
      setTransmitDirectionId(selectedPersonUnit.direction_id);
    }
    if (selectedPersonUnit.department_id && transmitDepartmentId !== selectedPersonUnit.department_id) {
      setTransmitDepartmentId(selectedPersonUnit.department_id);
    }
    if (transmitUnitId !== selectedPersonUnit.id) {
      setTransmitUnitId(selectedPersonUnit.id);
    }
  }, [selectedPersonUnit, transmitTargetId, transmitDirectionId, transmitDepartmentId, transmitUnitId]);

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
  // Organisation TRAITANTE — les libellés figés à la qualification priment sur
  // ceux résolus depuis l'organigramme courant : un service renommé ou rattaché
  // à une autre direction ne doit pas réécrire l'historique des anciens tickets.
  const assignedUnit = units.find((u) => String(u.id) === String(r.serviceId));
  const unitName = r.handlerServiceLabel ?? assignedUnit?.name ?? "—";
  const departmentName = r.handlerDepartmentLabel ?? assignedUnit?.department_name ?? "—";
  const currentDirectionId = assignedUnit?.direction_id ?? r.directionId ?? r.serviceId;
  const directionName = r.handlerDirectionLabel ?? directions.find(
    (d) => String(d.id) === currentDirectionId,
  )?.name ?? "—";
  const transferDirectionOptions = directions.filter(
    (d) => String(d.id) !== String(currentDirectionId),
  );
  // Organisation DU DEMANDEUR — même règle : les libellés figés à la création
  // priment, pour qu'un changement de service du demandeur ne réécrive pas
  // l'origine de ses anciennes demandes.
  const requesterUnit = units.find((u) => String(u.id) === String(r.requesterServiceId));
  const requesterUnitName = r.requesterServiceLabel ?? requesterUnit?.name ?? "—";
  const requesterDepartmentName = r.requesterDepartmentLabel ?? requesterUnit?.department_name ?? "—";
  const requesterDirectionId = r.requesterDirectionId ?? requesterUnit?.direction_id;
  const requesterDirectionName = r.requesterDirectionLabel ?? directions.find(
    (d) => String(d.id) === String(requesterDirectionId),
  )?.name ?? "—";

  const isArchivedTicket = Boolean(r.deletedAt || r.isArchived);
  // Onglet "Tickets résolus" : le traitement est terminé, on ne propose plus
  // que la consultation du PV. `isArchived` porte déjà exactement cette
  // sémantique — « plus aucune action mutante » — et neutralise d'un coup les
  // quinze capacités calculées plus bas, sans avoir à en amender chacune.
  const isReadOnlyTreatment = READ_ONLY_TREATMENT_CONTEXTS.has(context);
  const isArchived = isArchivedTicket || isReadOnlyTreatment;
  const isFinal = isArchived || (["resolved", "closed", "rejected", "cancelled"] as const).includes(
    r.status as "resolved" | "closed" | "rejected" | "cancelled",
  );

  const agentPool = agentsData?.items ?? [];
  const availableServices = [...new Set(agentPool.map((a) => a.unit_id).filter((u): u is string => !!u))];

  const isAssignedToMe = isRequester(r.assigneeId, sessionUser?.id);
  const hasAssignee = Boolean(r.assigneeId);
  const participants = buildParticipants(r, assigneeUser?.name);

  // Fenêtre réouverture ticket fermé (7 jours après fermeture)
  const canReopenClosed = r.closedAt
    ? differenceInDays(new Date(), new Date(r.closedAt)) <= 7
    : false;
  const ownershipOptions = { isRequester: iAmRequester };
  const canEdit = !isArchived && iAmRequester && canTicketAction(role, "requester_edit", r.status, ownershipOptions);
  const canCancel = !isArchived && iAmRequester && canTicketAction(role, "cancel", r.status, ownershipOptions);
  const canClose = !isArchived && iAmRequester && canTicketAction(role, "close", r.status, ownershipOptions);
  const canRequestReopen = !isArchived && iAmRequester && canTicketAction(role, "reopen", r.status, {
    ...ownershipOptions,
    canReopenClosed,
  });
  const canSelfAssign = !isArchived && isAgentOnly && canTicketAction(role, "self_assign", r.status, {
    ...ownershipOptions,
    hasAssignee,
    isAssignedToMe,
  });
  // "Ouvrir une discussion" doit être visible pour quiconque possède réellement
  // le ticket au moment présent (l'a pris depuis la file d'attente OU se l'est
  // vu assigner par quelqu'un d'autre) — pas seulement chief-service : admin
  // traite aussi des tickets et doit avoir le même accès une fois assigné.
  const ownsTicket = !iAmRequester && isAssignedToMe && (role === "chief-service" || role === "technicien" || role === "chef-division-support" || role === "admin");
  const canRequestInfo = !isArchived && ownsTicket && canTicketAction(role, "request_info", r.status, ownershipOptions);
  // Escalade retirée le 2026-09-26 avec le statut "escalated" : l'endpoint
  // backend, le service et les modales n'existent plus. Les drapeaux
  // `canEscalateTicket` / `canEscalateToDirector` ont disparu avec eux.
  const canAssignTicket = !isArchived && !iAmRequester && canTicketAction(role, "assign", r.status, ownershipOptions);
  // BR-TRANSMIT-001 : "Terminer le traitement" et "Transmettre le traitement" sont
  // réservés à l'intervenant actuel (assignee_id == moi), quel que soit le rôle parmi
  // les rôles traitants — le rôle n'est plus qu'un filtre de sécurité général.
  const canResolveTicket = !isArchived && !iAmRequester && isAssignedToMe
    && canTicketAction(role, "resolve", r.status, { ...ownershipOptions, isAssignedToMe });
  const canTransmitTreatment = !isArchived && !iAmRequester && isAssignedToMe
    && canTicketAction(role, "transmit_treatment", r.status, { ...ownershipOptions, isAssignedToMe });
  // Procédure tâche 2.1 — le constat est l'affaire du TECHNICIEN : le document
  // place les tâches 2.1 et 2.2 sous sa seule responsabilité. Un chef de
  // service, un chef de division ou un chef de département qui termine un
  // traitement ne réalise pas une intervention de terrain. Aligné sur la règle
  // backend, qui ne pose `field_check_required` que pour un technicien.
  const canFieldCheck = !isArchived && !isFinal && !iAmRequester
    && isAssignedToMe && role === "technicien";
  // Le constat est rattaché à une INTERVENTION, pas au ticket : après une
  // transmission, l'intervenant suivant doit refaire le sien. On cible donc
  // celui de l'intervention en cours — sinon le bouton resterait masqué pour le
  // suivant, que le backend empêcherait ensuite de résoudre.
  const fieldChecks = r.timeline.filter((t) => t.type === "field_check");
  const currentInterventionId = r.interventions?.find((i) => !i.endedAt)?.interventionId;
  const lastFieldCheck = currentInterventionId
    ? fieldChecks
        .filter((t) => {
          const infos = (t.infos ?? {}) as Record<string, unknown>;
          return String(infos.intervention_id ?? "") === String(currentInterventionId);
        })
        .slice(-1)[0]
    // Repli — le backend laisse `intervention_id` à null sur les tickets
    // antérieurs au suivi par intervention : le dernier constat fait alors foi.
    : fieldChecks.slice(-1)[0];
  const fieldCheckInfos = (lastFieldCheck?.infos ?? {}) as Record<string, unknown>;

  // BR-TRAITEMENT-PROGRESSIF-001 — une seule action progressive à la fois. L'étape
  // est DÉRIVÉE du statut renvoyé par le backend, jamais d'un état local : le
  // serveur reste la source de vérité et refuse de toute façon les séquences
  // invalides. `pending` et `escalated` valent « démarré » : un ticket mis en
  // attente puis repris reste terminable, comme avant ce lot.
  // `canFieldCheck` vaut le rôle technicien : pour les autres traitants le
  // constat n'est pas exigé (règle backend `field_check_required`), ils passent
  // donc directement au démarrage — sans quoi ils resteraient bloqués.
  const fieldCheckPending = canFieldCheck && !lastFieldCheck;
  const treatmentStep: "field_check" | "start" | "finish" | "done" =
    r.status === "assigned"
      ? (fieldCheckPending ? "field_check" : "start")
      : ["in_progress", "pending", "escalated"].includes(r.status)
        ? "finish"
        : "done";
  const canStartTreatment = !isArchived && !iAmRequester && isAssignedToMe
    && treatmentStep === "start";
  // Lot 2.7 — la "Directive" (message dédié chef -> agent assigné) transitait par
  // la messagerie, retirée le 2026-09-25 : elle disparaît avec elle.
  const canChangePriority = !isArchived && !iAmRequester && canTicketAction(role, "change_priority", r.status, ownershipOptions);
  const canChangeService = !isArchived && !iAmRequester && canTicketAction(role, "change_service", r.status, ownershipOptions);
  const canTransferDirection = !isArchived && !iAmRequester && canTicketAction(role, "transfer_direction", r.status, ownershipOptions);
  const canRejectTicket = !isArchived && !iAmRequester && canTicketAction(role, "reject", r.status, ownershipOptions);
  const canShowClosedRequestAction = isRequesterView && r.status === "closed";
  const assigneeDisplayName = assigneeUser?.name ?? r.assigneeName ?? (r.assigneeId ? "Agent assigné" : "Non assigné");
  const createdAtLabel = formatTicketDateTime(r.createdAt);
  const updatedAtLabel = formatTicketDateTime(r.updatedAt);
  const canShowQuickActions = canEdit || canCancel || canClose || canRequestReopen || canShowClosedRequestAction;
  const hasRequestActions = canShowQuickActions;
  const hasTreatmentActions = !isRequesterView && (
    (r.status === "reopened" && !r.assigneeId) ||
    canSelfAssign ||
    canAssignTicket ||
    canChangePriority ||
    canRejectTicket ||
    canChangeService ||
    canTransferDirection ||
    canTransmitTreatment ||
    canFieldCheck ||
    canResolveTicket
  );
  const detailTabs: Array<{ key: DetailTab; label: string; count?: number; icon: LucideIcon }> = [
    { key: "description", label: "Description", icon: FileText },
    { key: "files", label: "Fichiers", count: attachments.length, icon: Paperclip },
    { key: "treatment", label: "Traitement", icon: Wrench },
  ];
  const sideParticipants = participants.slice(0, 4);
  const canToggleParticipants = participants.length > sideParticipants.length;
  const sideCardClass = "glass-strong rounded-[18px] p-4 sm:p-5";
  const directTreatmentActionConfig = (() => {
    switch (directTreatmentAction) {
      case "selfAssign":
        return {
          icon: UserCheck,
          title: "Vous assigner ce ticket",
          description: "Le ticket vous sera attribué pour prise en charge.",
          confirmLabel: "M'assigner",
          isPending: selfAssignMut.isPending,
        };
      default:
        return null;
    }
  })();
  const confirmDirectTreatmentAction = () => {
    switch (directTreatmentAction) {
      case "selfAssign":
        selfAssignMut.mutate();
        break;
    }
  };

  // Procédure tâche 3.1 — bouton PV. Toujours disponible à un intervenant, y
  // compris sur un ticket terminé : c'est justement APRÈS la résolution que le
  // PV s'imprime et s'archive. Le demandeur y a droit dès que le ticket est
  // résolu, puisque c'est lui qui valide le dépannage (tâche 3.2).
  const pvButton = (
    <button
      type="button"
      className="flex items-start gap-3 rounded-xl border border-border/60 bg-muted/30 p-3 text-left transition hover:bg-muted/50 disabled:opacity-60"
      onClick={isReadOnlyTreatment ? handlePreviewPv : handleDownloadPv}
      disabled={pvPending}
    >
      {pvPending
        ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
        : <FileText className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
      <span>
        <span className="block text-sm font-semibold">PV d'intervention</span>
        <span className="text-xs text-muted-foreground">
          {/* Plus de signature manuscrite à obtenir : depuis l'émargement
              électronique (2026-09-27), les validations faites dans
              l'application sont portées sur le document lui-même. */}
          {isReadOnlyTreatment
            ? "Consulter le PV en aperçu"
            : "Générer le PV à imprimer et archiver"}
        </span>
      </span>
    </button>
  );
  const canDownloadPv = !isRequesterView || isFinal;
  // Tâche 3.3 — l'intervenant qui a traité soumet le PV, une fois le traitement
  // terminé. Tâche 3.4 — le chef de division qui a réparti le ticket l'archive,
  // et seulement après soumission. Les deux gardes sont aussi appliquées côté
  // serveur ; ici on évite simplement de proposer une action vouée au refus.
  const pvValidated = Boolean(r.pvValidatedAt);
  const pvSubmitted = Boolean(r.pvSubmittedAt);
  const pvArchived = Boolean(r.pvArchivedAt);
  // Tâche 3.2 avant 3.3 : le demandeur valide le dépannage (via son
  // appréciation) avant que le PV puisse partir au chef de division.
  const pvAwaitingValidation = !isReadOnlyTreatment && !isRequesterView && isAssignedToMe && !pvValidated
    && (r.status === "resolved" || r.status === "closed");
  // BR-TRAITEMENT-PROGRESSIF-001 — la soumission est désormais AUTOMATIQUE dès
  // que le demandeur valide le dépannage. Dans le cas nominal `pvSubmitted` est
  // donc déjà vrai et ce bouton ne s'affiche jamais. Il subsiste comme filet de
  // sécurité : si la soumission automatique avait échoué, le traitant garde un
  // moyen de la relancer plutôt que de rester bloqué.
  const canSubmitPv = !isReadOnlyTreatment && !isRequesterView && isAssignedToMe && pvValidated && !pvSubmitted
    && (r.status === "resolved" || r.status === "closed");
  const canArchivePv = !isReadOnlyTreatment && !isRequesterView && pvSubmitted && !pvArchived
    && role === "chef-division-support";

  const pvCircuitButtons = (
    <>
      {pvAwaitingValidation && (
        <div className="col-span-full flex items-center gap-2 rounded-xl border border-border/50 bg-muted/30 px-4 py-2.5 text-sm text-muted-foreground">
          <Clock className="h-4 w-4 shrink-0" />
          En attente de la validation du dépannage par le requérant — le PV
          pourra ensuite être soumis au chef de division.
        </div>
      )}
      {canSubmitPv && (
        <button
          type="button"
          className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/10 p-3 text-left transition hover:bg-primary/15 disabled:opacity-60"
          onClick={() => pvSubmitMut.mutate()}
          disabled={pvSubmitMut.isPending}
        >
          {pvSubmitMut.isPending
            ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-primary" />
            : <Send className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
          <span>
            <span className="block text-sm font-semibold text-primary">Soumettre le PV</span>
            <span className="text-xs text-muted-foreground">
              Transmettre au chef de division pour archivage
            </span>
          </span>
        </button>
      )}
      {canArchivePv && (
        <button
          type="button"
          className="flex items-start gap-3 rounded-xl border border-success/40 bg-success/10 p-3 text-left transition hover:bg-success/15 disabled:opacity-60"
          onClick={() => pvArchiveMut.mutate()}
          disabled={pvArchiveMut.isPending}
        >
          {pvArchiveMut.isPending
            ? <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin text-success" />
            : <Archive className="mt-0.5 h-4 w-4 shrink-0 text-success" />}
          <span>
            <span className="block text-sm font-semibold text-success">Archiver le PV</span>
            <span className="text-xs text-muted-foreground">
              Enregistrer le PV d'intervention reçu
            </span>
          </span>
        </button>
      )}
      {pvArchived && !isRequesterView && (
        <div className="col-span-full flex items-center gap-2 rounded-xl border border-success/30 bg-success/8 px-4 py-2.5 text-sm">
          <Archive className="h-4 w-4 shrink-0 text-success" />
          PV d'intervention enregistré et archivé.
        </div>
      )}
    </>
  );

  const treatmentActionsPanel = (
    !isRequesterView && isFinal ? (
      <div className="space-y-3">
        <div className="flex w-full flex-wrap items-center gap-2 rounded-full border border-border/40 bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
          <Lock className="h-3.5 w-3.5" />
          Ticket {isArchived ? "archivé" : r.status === "closed" ? "clôturé" : r.status === "rejected" ? "rejeté" : "résolu"} — aucune action de traitement disponible
        </div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">{pvButton}{pvCircuitButtons}</div>
      </div>
    ) : (hasTreatmentActions || hasRequestActions || canDownloadPv) ? (
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3" role="group" aria-label="Actions de traitement">
        {/* BR-REOPEN-QUEUE-001 — assignee_id=null tant que personne n'a repris le
            ticket depuis la File d'attente : le rappeler explicitement. */}
        {!isRequesterView && r.status === "reopened" && !r.assigneeId && (
          <div className="col-span-full flex items-center gap-2 rounded-full border border-fuchsia-500/40 bg-fuchsia-500/10 px-4 py-2 text-sm text-fuchsia-700 dark:text-fuchsia-300">
            <RotateCcw className="h-3.5 w-3.5 shrink-0" />
            Ce ticket réouvert attend une nouvelle prise en charge.
          </div>
        )}
        {/* Procédure tâche 2.1 — seule l'INVITE subsiste ici : elle est
            actionnable et se tient auprès des boutons, alors que le backend
            refuse la résolution tant que le constat manque. Le récapitulatif du
            constat déjà consigné a été retiré de cet onglet (2026-09-27) : il
            faisait doublon avec le bloc « Constat d'intervention » de l'onglet
            Description, plus complet (catégorie et priorité constatées). */}
        {canFieldCheck && !lastFieldCheck && (
          <div className="col-span-full flex items-center gap-2 rounded-xl border border-info/40 bg-info/8 px-4 py-2.5 text-sm">
            <ClipboardCheck className="h-4 w-4 shrink-0 text-info" />
            <span>
              Vérifiez l'état réel de la requête et consignez votre constat avant
              de résoudre ce ticket.
            </span>
          </div>
        )}
        {canDownloadPv && pvButton}
        {pvCircuitButtons}
        {/* Étape 1 du workflow progressif. Une fois le constat consigné, le
            bouton cède la place à « Démarrer le traitement » : le constat reste
            consultable dans l'onglet Description. Il réapparaît pour
            l'intervenant suivant, dont l'intervention n'a pas encore le sien. */}
        {canFieldCheck && treatmentStep === "field_check" && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-info/40 bg-info/8 p-3 text-left transition hover:bg-info/12"
            onClick={() => setShowFieldCheckForm(true)}
          >
            <ClipboardCheck className="mt-0.5 h-4 w-4 shrink-0 text-info" />
            <span>
              <span className="block text-sm font-semibold text-info">
                Consigner mon constat
              </span>
              <span className="text-xs text-muted-foreground">
                Vérifier l'état réel de la requête
              </span>
            </span>
          </button>
        )}
        {/* Étape 2 du workflow progressif — le constat est fait, le traitement
            n'a pas encore commencé. Le lieu est saisi ici, la date et l'heure
            de début sont horodatées par le serveur. */}
        {canStartTreatment && (
          <button
            type="button"
            className="flex items-start gap-3 rounded-xl border border-primary/40 bg-primary/8 p-3 text-left transition hover:bg-primary/12"
            onClick={() => setShowStartForm(true)}
          >
            <PlayCircle className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
            <span>
              <span className="block text-sm font-semibold text-primary">
                Démarrer le traitement
              </span>
              <span className="text-xs text-muted-foreground">
                Indiquer le lieu de l'intervention
              </span>
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
        {/* C2 — Demander des informations : IN_PROGRESS, agent seulement.
            Volontairement indépendant de hasVisibleComments — c'est justement
            l'action qui crée le tout premier message de la conversation. */}
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
        {false && canTransferDirection && (
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
        {/* Étape 3 du workflow progressif — visible seulement une fois le
            traitement démarré, jamais en même temps que les étapes 1 et 2. */}
        {canResolveTicket && treatmentStep === "finish" && (
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
            onClick={() => setShowAppreciationDialog(true)}
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
      </div>
    ) : null
  );

  const nameForPeer = (peerId: string) =>
    (peerId === r.assigneeId ? assigneeUser?.name ?? r.assigneeName : undefined)
    ?? participants.find((p) => p.key === peerId)?.name
    ?? "Intervenant";

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
                onClick={() => void copyWithToast(r.ref, "Identifiant copié")}
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
        </div>

        {(context === "admin" || isArchived) && (
          <div className="flex flex-col items-stretch gap-3 lg:items-end">
            {context === "admin" && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-full"
                    disabled={exportPending}
                  >
                    {exportPending
                      ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                      : <Download className="mr-1.5 h-4 w-4" />}
                    Exporter la demande
                    <MoreHorizontal className="ml-1 h-3.5 w-3.5 opacity-60" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-44">
                  <DropdownMenuItem onSelect={() => void handleExportDossier("excel")}>
                    <FileSpreadsheet className="h-4 w-4" /> Excel
                  </DropdownMenuItem>
                  <DropdownMenuItem onSelect={() => void handleExportDossier("pdf")}>
                    <FileText className="h-4 w-4" /> PDF
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
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



          {/* Procédure EDG/PS-GSI/Pro-02 tâche 2.1 — « Qualifier la demande »,
              point de contrôle « vérification de l'état réel de la requête ».
              Le constat est visible du requérant (il porte sur son matériel),
              contrairement à la solution proposée par le chef de service. */}
          <Dialog
            open={showFieldCheckForm}
            onOpenChange={(open) => {
              setShowFieldCheckForm(open);
              if (!open) {
                setFieldCheckFindings("");
                setObservedCategory("");
                setObservedPriority("");
                setFieldCheckConformity("conforme");
              }
            }}
          >
            <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-info" />
                  Constat d'intervention
                </DialogTitle>
                <DialogDescription>
                  Comparez l'état réel de la requête à ce qui a été décrit, avant
                  d'intervenir. Votre constat est visible du requérant.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-3 py-2">
                <div className="space-y-1.5">
                  <Label className="text-sm font-medium">
                    État réel <span className="text-destructive">*</span>
                  </Label>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    {([
                      { value: "conforme", label: "Conforme à la demande" },
                      { value: "ecart", label: "Écart avec la demande" },
                    ] as const).map((option) => (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => setFieldCheckConformity(option.value)}
                        className={cn(
                          "rounded-xl border px-3 py-2.5 text-left text-sm transition",
                          fieldCheckConformity === option.value
                            ? "border-primary bg-primary/10 font-semibold text-primary"
                            : "border-border/50 hover:bg-foreground/5",
                        )}
                      >
                        {option.label}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="field-check-findings" className="text-sm font-medium">
                    Ce que vous avez constaté <span className="text-destructive">*</span>
                  </Label>
                  <Textarea
                    id="field-check-findings"
                    value={fieldCheckFindings}
                    onChange={(e) => setFieldCheckFindings(e.target.value)}
                    placeholder="Décrivez l'état réel trouvé sur place…"
                    className="min-h-24"
                  />
                </div>
                {fieldCheckConformity === "ecart" && (
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="observed-category" className="text-sm font-medium">
                        Catégorie observée <span className="text-destructive">*</span>
                      </Label>
                      <Select value={observedCategory} onValueChange={setObservedCategory}>
                        <SelectTrigger id="observed-category">
                          <SelectValue placeholder="Choisir" />
                        </SelectTrigger>
                        <SelectContent>
                          {observedCategories.map((c) => (
                            <SelectItem key={c} value={c}>{c}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-1.5">
                      <Label htmlFor="observed-priority" className="text-sm font-medium">
                        Priorité observée <span className="text-destructive">*</span>
                      </Label>
                      <Select value={observedPriority} onValueChange={setObservedPriority}>
                        <SelectTrigger id="observed-priority">
                          <SelectValue placeholder="Choisir" />
                        </SelectTrigger>
                        <SelectContent>
                          {(["low", "medium", "high", "critical"] as const).map((p) => (
                            <SelectItem key={p} value={priorityLabels[p]}>
                              {priorityLabels[p]}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <p className="sm:col-span-2 text-xs text-muted-foreground">
                      Le chef de service sera prévenu de l'écart : la qualification
                      lui appartient.
                    </p>
                  </div>
                )}
              </div>
              <DialogFooter>
                <Button
                  variant="ghost"
                  className="rounded-full"
                  onClick={() => setShowFieldCheckForm(false)}
                >
                  Annuler
                </Button>
                <Button
                  className="rounded-full"
                  disabled={!canSubmitFieldCheck || fieldCheckMut.isPending}
                  onClick={() => fieldCheckMut.mutate()}
                >
                  {fieldCheckMut.isPending
                    ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    : <ClipboardCheck className="mr-1.5 h-4 w-4" />}
                  Enregistrer le constat
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          {/* BR-TRAITEMENT-PROGRESSIF-001 — Modal « Démarrer le traitement ».
              Date et heure sont affichées à titre indicatif seulement : c'est le
              serveur qui les horodate au moment de la confirmation, ce qui évite
              de dépendre de l'horloge du poste. Seul le lieu est saisi. */}
          <Dialog
            open={showStartForm}
            onOpenChange={(open) => {
              setShowStartForm(open);
              if (!open) setStartLocation("");
            }}
          >
            <DialogContent className="sm:max-w-md">
              <DialogHeader>
                <DialogTitle>Démarrer le traitement</DialogTitle>
                <DialogDescription>
                  La date et l'heure de début sont enregistrées automatiquement par
                  le système au moment de la confirmation.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 rounded-xl border border-border/50 bg-muted/30 p-3 text-sm">
                  <div>
                    <div className="text-xs text-muted-foreground">Date de début</div>
                    <div className="font-medium">{new Date().toLocaleDateString("fr-FR")}</div>
                  </div>
                  <div>
                    <div className="text-xs text-muted-foreground">Heure de début</div>
                    <div className="font-medium">
                      {new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                    </div>
                  </div>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="start-location" className="text-sm font-medium">
                    Lieu de l'intervention <span className="text-destructive">*</span>
                  </Label>
                  <Input
                    id="start-location"
                    value={startLocation}
                    onChange={(e) => setStartLocation(e.target.value)}
                    placeholder="Ex. Siège EDG — 3e étage, bureau 312"
                  />
                </div>
              </div>
              <DialogFooter>
                <Button
                  variant="ghost"
                  className="rounded-full"
                  onClick={() => setShowStartForm(false)}
                >
                  Annuler
                </Button>
                <Button
                  className="rounded-full"
                  disabled={!startLocation.trim() || startMut.isPending}
                  onClick={() => startMut.mutate()}
                >
                  {startMut.isPending
                    ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                    : <PlayCircle className="mr-1.5 h-4 w-4" />}
                  Démarrer le traitement
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

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
                  L'ensemble du ticket est complètement traité. Le requérant sera notifié
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
              <Command
                shouldFilter={false}
                className="contents space-y-3 py-2"
                onKeyDown={(e) => {
                  // §17 — Échap ferme les suggestions (efface la recherche) sans
                  // fermer toute la modale ; flèches haut/bas + Entrée déjà gérées
                  // nativement par cmdk sur CommandInput/CommandItem.
                  if (e.key === "Escape" && transmitSearch) {
                    e.stopPropagation();
                    setTransmitSearch("");
                  }
                }}
              >
                {/* BR-TRANSMIT-SCOPE-TECH-001 — périmètre restreint (technicien) :
                    une sélection fermée remplace la recherche libre, et les filtres
                    direction/département/service disparaissent : ils n'ont plus
                    d'objet puisque les cibles se limitent à son propre service et
                    au responsable qui lui a confié le ticket. */}
                {transmitRestricted ? (
                  <div className="space-y-1.5">
                    <Label htmlFor="transmit-target" className="text-sm font-medium">
                      Destinataire <span className="text-destructive">*</span>
                    </Label>
                    <select
                      id="transmit-target"
                      value={transmitTargetId}
                      onChange={(e) => setTransmitTargetId(e.target.value)}
                      className="w-full rounded-xl border border-border/50 bg-background/60 px-2.5 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40"
                    >
                      <option value="">Sélectionner un destinataire</option>
                      {transmitTargets.map((person) => (
                        <option key={person.id} value={person.id}>
                          {[
                            person.name,
                            person.matricule,
                            roleLabels[person.role as keyof typeof roleLabels] ?? person.role,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </option>
                      ))}
                    </select>
                    <p className="text-[11px] text-muted-foreground">
                      {transmitTargets.length === 0
                        ? "Aucun destinataire disponible : ni collègue technicien dans votre service, ni responsable ayant confié ce ticket."
                        : "Vos collègues techniciens de ce service, et le responsable qui vous a confié ce ticket."}
                    </p>
                  </div>
                ) : (
                  <div className="space-y-1.5">
                    <Label htmlFor="transmit-search" className="text-sm font-medium">
                      Recherche
                    </Label>
                    <div className="rounded-xl border border-border/50 bg-background/60 focus-within:ring-2 focus-within:ring-primary/40">
                      <CommandInput
                        id="transmit-search"
                        value={transmitSearch}
                        onValueChange={(value) => {
                          setTransmitSearch(value);
                          setTransmitTargetId("");
                        }}
                        placeholder="@Nom, badge ou téléphone…"
                        className="h-9 border-b-0"
                      />
                    </div>
                  </div>
                )}
                <div className={cn("grid grid-cols-1 gap-2 sm:grid-cols-3", transmitRestricted && "hidden")}>
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
                <div className={cn("space-y-1.5", transmitRestricted && "hidden")}>
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
                            {selectedTransmitPerson.matricule ? `${selectedTransmitPerson.matricule} · ` : ""}
                            {roleLabels[selectedTransmitPerson.role as keyof typeof roleLabels] ?? selectedTransmitPerson.role}
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
                    <CommandList className="max-h-48 space-y-1 overflow-y-auto rounded-xl border border-border/40 bg-background/40 p-1.5">
                      {transmitPeopleLoading ? (
                        <CommandEmpty className="px-2 py-3 text-center text-xs text-muted-foreground">
                          Recherche en cours…
                        </CommandEmpty>
                      ) : transmitPeople.length === 0 ? (
                        <CommandEmpty className="px-2 py-3 text-center text-xs text-muted-foreground">
                          {transmitSearchTerm || transmitUnitId || transmitDepartmentId || transmitDirectionId
                            ? "Aucun intervenant actif trouvé pour ces critères."
                            : "Recherchez @Prénom Nom, un badge ou un téléphone, ou affinez par direction/département/service."}
                        </CommandEmpty>
                      ) : (
                        <CommandGroup>
                          {transmitPeople.map((person) => (
                            <CommandItem
                              key={person.id}
                              value={person.id}
                              onSelect={() => setTransmitTargetId(person.id)}
                              className={cn(
                                "flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm",
                                transmitTargetId === person.id && "bg-primary/15 text-primary",
                              )}
                            >
                              <span className="min-w-0">
                                <span className="block truncate font-medium">
                                  {[person.firstname, person.name].filter(Boolean).join(" ")}
                                </span>
                                <span className="block truncate text-xs text-muted-foreground">
                                  {person.matricule ? `${person.matricule} · ` : ""}
                                  {roleLabels[person.role as keyof typeof roleLabels] ?? person.role}
                                  {(person.service ?? person.direction) ? ` · ${person.service ?? person.direction}` : ""}
                                </span>
                              </span>
                              {transmitTargetId === person.id && <BadgeCheck className="h-4 w-4 shrink-0 text-primary" />}
                            </CommandItem>
                          ))}
                        </CommandGroup>
                      )}
                    </CommandList>
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
              </Command>
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
                  const startsVisualGroup = tab.key === "sla";

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

              {/* Procédure EDG/PS-GSI/Pro-02 tâche 1.3 — piste de résolution
                  décrite par le chef de service à l'imputation. Réservée aux
                  intervenants du support : jamais rendue pour le requérant
                  (la requête n'est même pas émise — voir canSeeProposedSolution). */}
              {proposedSolution && (
                <div className="mt-3 rounded-2xl border border-info/25 bg-info/8 p-4">
                  <h3 className="mb-2 flex items-center gap-2 font-semibold text-info">
                    <Lightbulb className="h-4 w-4" />
                    Solution proposée par le chef de service
                  </h3>
                  <p className="whitespace-pre-wrap text-sm leading-7">
                    {proposedSolution}
                  </p>
                </div>
              )}

              {/* Procédure EDG/PS-GSI/Pro-02 tâche 2.1 — constat du traitant
                  actuel. Contrairement à la solution proposée ci-dessus, il est
                  rendu pour tout le monde, requérant inclus : il dit ce qui a
                  réellement été trouvé sur place. */}
              {lastFieldCheck && (
                <div className={cn(
                  "mt-3 rounded-2xl border p-4",
                  fieldCheckInfos.conformity === "ecart"
                    ? "border-amber-500/40 bg-amber-500/8"
                    : "border-success/30 bg-success/8",
                )}>
                  <h3 className={cn(
                    "mb-2 flex items-center gap-2 font-semibold",
                    fieldCheckInfos.conformity === "ecart" ? "text-amber-600 dark:text-amber-400" : "text-success",
                  )}>
                    <ClipboardCheck className="h-4 w-4" />
                    Constat d'intervention
                    {lastFieldCheck.by && (
                      <span className="text-xs font-normal text-muted-foreground">
                        — {lastFieldCheck.by}
                      </span>
                    )}
                  </h3>
                  <p className="mb-2 text-sm font-medium">
                    {fieldCheckInfos.conformity === "ecart"
                      ? "Écart entre la demande et l'état réel constaté"
                      : "État réel conforme à la demande"}
                  </p>
                  <p className="whitespace-pre-wrap text-sm leading-7">
                    {String(fieldCheckInfos.findings ?? "")}
                  </p>
                  {Boolean(fieldCheckInfos.observed_category || fieldCheckInfos.observed_priority) && (
                    <dl className="mt-3 grid grid-cols-1 gap-2 border-t border-border/40 pt-3 text-sm sm:grid-cols-2">
                      {Boolean(fieldCheckInfos.observed_category) && (
                        <div>
                          <dt className="text-xs text-muted-foreground">Catégorie observée</dt>
                          <dd className="font-medium">{String(fieldCheckInfos.observed_category)}</dd>
                        </div>
                      )}
                      {Boolean(fieldCheckInfos.observed_priority) && (
                        <div>
                          <dt className="text-xs text-muted-foreground">Priorité observée</dt>
                          <dd className="font-medium">{String(fieldCheckInfos.observed_priority)}</dd>
                        </div>
                      )}
                    </dl>
                  )}
                  {lastFieldCheck.at && (
                    <p className="mt-3 text-xs text-muted-foreground">
                      {formatTicketDateTime(lastFieldCheck.at)}
                    </p>
                  )}
                </div>
              )}
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

            <section className={cn("order-2 border-t border-border/40 p-3 sm:p-4", activeDetailTab !== "sla" && "hidden")}>
              <div className="mb-4">
                <h3 className="font-semibold">Durée de traitement</h3>
                <p className="mt-1 text-xs text-muted-foreground">
                  Lecture basée sur les événements disponibles du ticket.
                </p>
              </div>
              <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Clock className="h-4 w-4 text-primary" />
                    <span className="truncate">Début</span>
                  </div>
                  <p className="mt-2 truncate text-sm text-muted-foreground" title={createdAtLabel}>{createdAtLabel}</p>
                </div>
                <div className="min-w-0 rounded-2xl border border-border/50 bg-background/55 p-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">Temps écoulé</span>
                  </div>
                  <p className="mt-2 truncate text-sm font-medium text-muted-foreground">
                    {formatElapsedHours(r.slaElapsed)}
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

              {/* BR-SLA-REOPEN-001 — cycles de traitement distincts : le 1er traitement et
                  chaque traitement après réouverture sont mesurés indépendamment, sans
                  jamais recalculer un cycle déjà clos. */}
              {(r.slaCycles?.length ?? 0) > 1 && (
                <div className="mt-5 space-y-3">
                  <div>
                    <h3 className="font-semibold">Cycles de traitement ({r.slaCycles!.length})</h3>
                    <p className="mt-1 text-xs text-muted-foreground">
                      Ce ticket a été réouvert {r.reopenCount ?? r.slaCycles!.length - 1} fois — chaque
                      traitement est mesuré indépendamment, le premier cycle n'est jamais recalculé.
                    </p>
                  </div>
                  <div className="space-y-3">
                    {r.slaCycles!.map((cycle) => (
                      <div
                        key={cycle.cycleNumber}
                        className="rounded-2xl border border-border/50 bg-background/55 p-3 sm:p-4"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <h4 className="text-sm font-semibold">
                            {cycle.cycleNumber === 1
                              ? "Premier traitement"
                              : `Traitement après réouverture n°${cycle.cycleNumber - 1}`}
                          </h4>
                          <span
                            className={cn(
                              "rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
                              cycle.closed
                                ? "bg-muted text-muted-foreground"
                                : "bg-fuchsia-500/15 text-fuchsia-600",
                            )}
                          >
                            {cycle.closed ? "Terminé" : "En cours"}
                          </span>
                        </div>
                        {cycle.reopenReason && (
                          <p className="mt-1.5 text-xs text-muted-foreground">
                            <span className="font-medium text-foreground">Motif de réouverture :</span>{" "}
                            {cycle.reopenReason}
                          </p>
                        )}
                        <dl className="mt-2.5 grid gap-2 text-xs sm:grid-cols-3">
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
                            <dt className="text-muted-foreground">Durée</dt>
                            <dd className="mt-0.5 font-medium">
                              {cycle.elapsedHours != null ? formatElapsedHours(cycle.elapsedHours) : "—"}
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
                        Réouvrir le ticket
                      </Button>
                    </div>
                  </div>
                )}
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
                    {r.status === "closed" ? "Ticket clôturé" : "Réouvrir le ticket"}
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
                      Réouvrir le ticket
                    </Button>
                  )}
                </DialogFooter>
              </DialogContent>
            </Dialog>
          )}

          {isRequesterView && (
            <Dialog open={showAppreciationDialog} onOpenChange={setShowAppreciationDialog}>
              <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2">
                    <CheckCircle2 className="h-5 w-5 text-success" />
                    Confirmer la résolution
                  </DialogTitle>
                  <DialogDescription>
                    Confirmez que votre ticket est résolu et évaluez la prise en charge — ou signalez que le problème persiste pour demander une réouverture.
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
                    if (data.resolvedConfirmed) {
                      // Clôture au mieux — l'échec de la clôture ne doit pas bloquer
                      // l'envoi de l'avis, closeMut gère déjà son propre toast d'erreur.
                      closeMut.mutate();
                    }
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

          {/* Dialog — Prévisualisation piece jointe (image zoomable / PDF) */}
          <Dialog open={!!previewFile} onOpenChange={(open) => { if (!open) closePreview(); }}>
            <DialogContent className="flex max-h-[90dvh] flex-col gap-0 overflow-hidden overflow-y-hidden p-0 sm:max-w-4xl">
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
            <DialogContent className="max-h-[80dvh] overflow-y-auto sm:max-w-md">
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
                    onClick={() => void copyWithToast(r.ref, "Identifiant copié")}
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                </dd>
              </div>
            </dl>
          </section>

          <Dialog open={showAllDetails} onOpenChange={setShowAllDetails}>
            <DialogContent className="max-h-[80dvh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Détails du ticket</DialogTitle>
                <DialogDescription>Requérant, traitement et délai de ce ticket.</DialogDescription>
              </DialogHeader>
              <div>
                <div className="mb-2 mt-2 flex items-center gap-2">
                  <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-sky-500/15 text-sky-500">
                    <Building2 className="h-3.5 w-3.5" />
                  </span>
                  <h4 className="text-xs font-bold uppercase tracking-wider text-sky-500">Requérant</h4>
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
                    <dt className="text-xs text-muted-foreground">Requérant</dt>
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
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-muted-foreground">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-muted text-muted-foreground">
                      <Clock className="h-3.5 w-3.5" />
                    </span>
                    Temps écoulé
                  </div>
                  <div className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground">
                    {formatElapsedHours(r.slaElapsed)}
                  </div>
                </div>
              </div>
            </DialogContent>
          </Dialog>

          </div>
        </aside>
      </div>

      {/* Aperçu du PV d'intervention — consultation seule, aucun enregistrement
          sur le poste. Le document est révoqué de la mémoire à la fermeture. */}
      <Dialog open={Boolean(pvPreviewUrl)} onOpenChange={(open) => { if (!open) closePvPreview(); }}>
        <DialogContent className="h-[90dvh] max-w-5xl p-0 sm:max-w-5xl">
          <DialogHeader className="border-b border-border/40 px-5 py-3">
            <DialogTitle className="flex items-center gap-2 text-base">
              <FileText className="h-4 w-4 text-primary" />
              PV d'intervention — {r.ref}
            </DialogTitle>
          </DialogHeader>
          {pvPreviewUrl && (
            <iframe
              src={pvPreviewUrl}
              title={`PV d'intervention ${r.ref}`}
              className="h-full w-full flex-1 rounded-b-lg border-0 bg-muted"
            />
          )}
        </DialogContent>
      </Dialog>

    </div>
  );
}

