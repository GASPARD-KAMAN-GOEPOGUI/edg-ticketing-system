/**
 * Module API — Demandes EDG Support.
 *
 * Toutes les fonctions :
 *  - appellent le backend FastAPI via apiFetch
 *  - retournent des types compatibles avec les mocks (RequestItem etc.)
 *    pour que les composants UI n'aient pas besoin de changer
 */

import { apiFetch, apiFetchBlob } from "./client";
import type {
  RequestItem,
  RequestStatus,
  Priority,
  Appreciation,
  SlaCycle,
  Intervention,
} from "@/lib/mock-data";

// ── Types bruts backend (snake_case) ─────────────────────────────────────────

export type RawTimeline = {
  id: string;
  request_id?: string;
  event_type: string;
  label: string;
  comment?: string;
  infos?: Record<string, unknown>;
  agent_id?: number;
  actor_name?: string;
  workflow_id?: number;
  accepted?: boolean | null;
  activated: boolean;
  created_at: string;
  updated_at: string;
};

export type RawComment = {
  id: string;
  request_id: string;
  author_id: string;
  author_name: string;
  body: string;
  is_public: boolean;
  is_edited: boolean;
  created_at: string;
  updated_at: string;
};

export type RawAppreciation = {
  id: string;
  request_id: string;
  rating: number;
  comment?: string;
  resolved_confirmed?: boolean;
  created_at: string;
  updated_at: string;
};

export type RawAttachment = {
  id: string;
  request_id: string;
  uploader_id?: string;
  filename: string;
  storage_path: string;
  mime_type: string;
  size_bytes: number;
  scan_status: string;
  clamav_clean?: boolean;
  created_at: string;
  updated_at: string;
};

export type RawRequest = {
  id: string;
  deleted_at?: string | null;
  status?: boolean;
  ref: string;
  title: string;
  description: string;
  request_status: string;
  priority: string;
  category: string;
  unity_id?: number | null;
  unit_id?: number | string | null;   // alias backend de unity_id
  direction_id?: number | string | null; // réservé (null depuis le backend)
  assignee_id?: number | string | null;
  assignee_name?: string;
  in_triage: boolean;
  is_external: boolean;
  requester_type?: string;
  submission_mode: string;
  requester_name: string;
  requester_phone?: string;
  requester_email?: string;
  requester_address?: string;
  meter_number?: string;
  client_ref?: string;
  site_type?: string;
  lat?: number;
  lng?: number;
  location_label?: string;
  requester_id?: number | string | null;
  employee_matricule?: string;
  requester_job?: string;
  requester_direction_id?: string;
  requester_unit_id?: string;
  sla_hours: number;
  sla_elapsed: number;
  sla_breached: boolean;
  sla_response_at?: string;
  resolved_at?: string;
  closed_at?: string;
  created_at: string;
  updated_at: string;
  infos?: Record<string, unknown>;
  timelines: RawTimeline[];
  appreciation?: RawAppreciation;
  // BR-SLA-REOPEN-001 — détail ticket uniquement (absent des listes allégées).
  sla_cycles?: RawSlaCycle[];
  reopen_count?: number;
  // BR-TRACE-001 — détail ticket uniquement (absent des listes allégées).
  interventions?: RawIntervention[];
};

export type RawSlaCycle = {
  cycle_number: number;
  started_at?: string;
  ended_at?: string;
  sla_hours?: number;
  elapsed_hours?: number;
  response_hours?: number;
  breached?: boolean;
  resolved_by?: string;
  reopen_reason?: string;
  closed: boolean;
};

export type RawIntervention = {
  intervention_id: string;
  cycle_number: number;
  intervention_order?: number;
  actor_id?: string;
  actor_name?: string;
  actor_role?: string;
  actor_matricule?: string;
  actor_direction_label?: string;
  actor_department_label?: string;
  actor_service_label?: string;
  started_at?: string;
  ended_at?: string;
  duration_seconds?: number;
  work_done?: string;
  instruction?: string;
  transmission_reason?: string;
  decision?: "transmission" | "resolution";
  destination_id?: string;
  destination_name?: string;
  summary?: string;
  solution?: string;
  recommendations?: string;
  sla_hours?: number;
  sla_breached?: boolean;
  comment_count: number;
  attachment_count: number;
  event_ids: string[];
};

export type RawPaginated<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

// ── Types pour les filtres ────────────────────────────────────────────────────

export type RequestFilters = {
  page?: number;
  limit?: number;
  request_status?: string;
  exclude_status?: string;
  is_external?: boolean;
  direction_id?: string;
  unit_id?: string;
  assignee_id?: string;
  requester_id?: string;
  sla_breached?: boolean;
  in_triage?: boolean;
  search?: string;
  date_from?: string;
  date_to?: string;
};

// ── Mapper snake_case → camelCase (compatible RequestItem mock-data) ──────────

function asString(value: unknown): string | undefined {
  if (value === null || value === undefined || value === "") return undefined;
  return String(value);
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

export function mapRequest(raw: RawRequest): RequestItem {
  return {
    id: raw.id,
    ref: raw.ref,
    title: raw.title,
    description: raw.description,
    status: raw.request_status as RequestStatus,
    priority: raw.priority as Priority,
    category: raw.category,
    directionId: raw.direction_id != null ? String(raw.direction_id) : "",
    serviceId: raw.unit_id != null ? String(raw.unit_id) : (raw.unity_id != null ? String(raw.unity_id) : undefined),
    requesterId: raw.requester_id != null ? String(raw.requester_id) : "",
    requesterName: raw.requester_name,
    requesterType: raw.requester_type as "internal" | "external" | undefined,
    requesterPhone: raw.requester_phone ?? undefined,
    requesterEmail: raw.requester_email ?? undefined,
    requesterAddress: raw.requester_address ?? undefined,
    employeeMatricule: raw.employee_matricule ?? undefined,
    requesterJob: raw.requester_job ?? undefined,
    requesterDirectionId: raw.requester_direction_id ?? undefined,
    requesterServiceId: raw.requester_unit_id ?? undefined,
    meterNumber: raw.meter_number ?? undefined,
    clientRef: raw.client_ref ?? undefined,
    siteType: raw.site_type as "domicile" | "commerce" | "administration" | undefined,
    lat: raw.lat ?? undefined,
    lng: raw.lng ?? undefined,
    locationLabel: raw.location_label ?? undefined,
    inTriage: raw.in_triage,
    assigneeId: raw.assignee_id != null ? String(raw.assignee_id) : undefined,
    assigneeName: raw.assignee_name ?? undefined,
    isExternal: raw.is_external,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    deletedAt: raw.deleted_at ?? undefined,
    isArchived: Boolean(raw.deleted_at),
    resolvedAt: raw.resolved_at ?? undefined,
    closedAt: raw.closed_at ?? undefined,
    slaHours: raw.sla_hours,
    slaElapsed: raw.sla_elapsed,
    comments: (raw.timelines ?? [])
      .filter((t) => t.event_type === "comment_added")
      .map((t) => ({
        id: t.id,
        authorId: asString(t.infos?.actor_id) ?? (t.agent_id ? String(t.agent_id) : ""),
        author: t.actor_name ?? "Système",
        authorRole: asString(t.infos?.actor_role ?? t.infos?.source_role),
        body: t.comment ?? t.label ?? "",
        isPublic: t.infos?.is_public === true,
        isDirective: t.infos?.is_directive === true,
        replyToId: asString(t.infos?.reply_to_id),
        isEdited: false,
        createdAt: t.created_at,
      })),
    timeline: (raw.timelines ?? []).map((t) => {
      const infos = t.infos ?? {};
      return {
        id: t.id,
        type: t.event_type,
        label: t.label,
        at: t.created_at,
        by: t.actor_name ?? undefined,
        actorId: asString(infos.actor_id),
        actorRole: asString(infos.actor_role ?? infos.source_role),
        targetUserId: asString(infos.target_user_id ?? infos.to_user_id),
        targetUserName: asString(infos.target_user_name ?? infos.to_agent_name),
        targetRole: asString(infos.target_role ?? infos.dest_role),
        oldStatus: asString(infos.old_status ?? infos.old_workflow_status),
        newStatus: asString(infos.new_status ?? infos.new_workflow_status),
        comment: t.comment ?? undefined,
        isPublic: asBoolean(infos.is_public),
        infos,
      };
    }),
    infos: raw.infos ?? undefined,
    appreciation: raw.appreciation
      ? ({
          rating: raw.appreciation.rating as 1 | 2 | 3 | 4 | 5,
          comment: raw.appreciation.comment ?? undefined,
          resolvedConfirmed: raw.appreciation.resolved_confirmed ?? false,
          authorType: raw.is_external ? "external" : "internal",
          at: raw.appreciation.created_at,
        } as Appreciation)
      : undefined,
    slaCycles: (raw.sla_cycles ?? []).map(mapSlaCycle),
    reopenCount: raw.reopen_count ?? 0,
    interventions: (raw.interventions ?? []).map(mapIntervention),
  };
}

// BR-SLA-REOPEN-001
export function mapSlaCycle(c: RawSlaCycle): SlaCycle {
  return {
    cycleNumber: c.cycle_number,
    startedAt: c.started_at ?? undefined,
    endedAt: c.ended_at ?? undefined,
    slaHours: c.sla_hours ?? undefined,
    elapsedHours: c.elapsed_hours ?? undefined,
    responseHours: c.response_hours ?? undefined,
    breached: c.breached ?? undefined,
    resolvedBy: c.resolved_by ?? undefined,
    reopenReason: c.reopen_reason ?? undefined,
    closed: c.closed,
  };
}

// BR-TRACE-001
export function mapIntervention(i: RawIntervention): Intervention {
  return {
    interventionId: i.intervention_id,
    cycleNumber: i.cycle_number,
    interventionOrder: i.intervention_order ?? undefined,
    actorId: i.actor_id ? String(i.actor_id) : undefined,
    actorName: i.actor_name ?? undefined,
    actorRole: i.actor_role ?? undefined,
    actorMatricule: i.actor_matricule ?? undefined,
    actorDirectionLabel: i.actor_direction_label ?? undefined,
    actorDepartmentLabel: i.actor_department_label ?? undefined,
    actorServiceLabel: i.actor_service_label ?? undefined,
    startedAt: i.started_at ?? undefined,
    endedAt: i.ended_at ?? undefined,
    durationSeconds: i.duration_seconds ?? undefined,
    workDone: i.work_done ?? undefined,
    instruction: i.instruction ?? undefined,
    transmissionReason: i.transmission_reason ?? undefined,
    decision: i.decision ?? undefined,
    destinationId: i.destination_id ? String(i.destination_id) : undefined,
    destinationName: i.destination_name ?? undefined,
    summary: i.summary ?? undefined,
    solution: i.solution ?? undefined,
    recommendations: i.recommendations ?? undefined,
    slaHours: i.sla_hours ?? undefined,
    slaBreached: i.sla_breached ?? undefined,
    commentCount: i.comment_count ?? 0,
    attachmentCount: i.attachment_count ?? 0,
    eventIds: (i.event_ids ?? []).map(String),
  };
}

export function mapComment(t: RawTimeline) {
  return {
    id: t.id,
    authorId: asString(t.infos?.actor_id) ?? (t.agent_id ? String(t.agent_id) : ""),
    author: t.actor_name ?? "Système",
    body: t.comment ?? t.label ?? "",
    isPublic: t.infos?.is_public === true,
    isDirective: t.infos?.is_directive === true,
    replyToId: asString(t.infos?.reply_to_id),
    isEdited: false,
    createdAt: t.created_at,
    attachmentId: asString(t.infos?.attachment_id),
    attachmentName: typeof t.infos?.filename === "string" ? t.infos.filename : undefined,
    attachmentMime: typeof t.infos?.mime_type === "string" ? t.infos.mime_type : undefined,
    attachmentSize: typeof t.infos?.size_bytes === "number" ? t.infos.size_bytes : undefined,
  };
}

// ── API : Lectures ────────────────────────────────────────────────────────────

export type RequestStats = Record<string, number>;

export async function fetchRequestStats(): Promise<RequestStats> {
  return apiFetch<RequestStats>("/requests/stats/by-status");
}

export type AgentWorkload = { assigneeId: string; activeCount: number };

export async function fetchWorkloadByUnit(unitId: string): Promise<AgentWorkload[]> {
  const raw = await apiFetch<{ assignee_id: number | string; active_count: number }[]>(
    `/requests/workload-by-unit?unit_id=${encodeURIComponent(unitId)}`,
  );
  return (raw ?? []).map((row) => ({
    assigneeId: String(row.assignee_id),
    activeCount: row.active_count,
  }));
}

export async function fetchRequests(
  filters?: RequestFilters,
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null) {
        const value = String(v);
        if (value !== "") params.set(k, value);
      }
    }
  }
  const raw = await apiFetch<RawPaginated<RawRequest>>(
    `/requests/?${params.toString()}`,
  );
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
  };
}

export async function fetchTriage(
  filters?: { page?: number; limit?: number },
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null) {
        const value = String(v);
        if (value !== "") params.set(k, value);
      }
    }
  }
  const raw = await apiFetch<RawPaginated<RawRequest>>(
    `/requests/triage?${params.toString()}`,
  );
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
  };
}

export async function fetchRequest(
  id: string,
  options?: { includeDeleted?: boolean },
): Promise<RequestItem> {
  const params = options?.includeDeleted ? "?include_deleted=true" : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}${params}`);
  return mapRequest(raw);
}

export async function trackRequest(
  ref: string,
  credential: string,
): Promise<RequestItem> {
  const params = new URLSearchParams({ ref: ref.trim().toUpperCase() });
  const trimmed = credential.trim();
  if (trimmed.includes("@")) {
    params.set("email", trimmed);
  } else {
    params.set("phone", trimmed);
  }
  const raw = await apiFetch<RawRequest>(`/requests/track?${params.toString()}`);
  return mapRequest(raw);
}

// ── API : Mutations ───────────────────────────────────────────────────────────

export type CreateInternalRequestData = {
  title: string;
  description: string;
  category: string;
  priority: string;
  direction_id?: string;
  unity_id?: string | number;
  requester_name: string;
  requester_email?: string;
  requester_id?: string;
  employee_matricule?: string;
  requester_job?: string;
  requester_direction_id?: string;
  requester_unit_id?: string;
  submission_mode?: string;
  on_behalf_direction_id?: string;
  on_behalf_unit_id?: string;
  infos?: Record<string, unknown>;
  is_external: false;
};

export type SubmitExternalRequestData = {
  title: string;
  description: string;
  category: string;
  requester_name: string;
  requester_phone?: string;
  requester_email?: string;
  requester_address?: string;
  meter_number?: string;
  client_ref?: string;
  site_type?: string;
  lat?: number;
  lng?: number;
  location_label?: string;
  is_external: true;
};

export async function createRequest(
  data: CreateInternalRequestData,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>("/requests/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function submitExternalRequest(
  data: SubmitExternalRequestData,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>("/requests/submit", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function updateRequest(
  id: string,
  data: Partial<RawRequest> & { status_reason?: string },
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function changeRequestPriority(
  id: string,
  priority: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/priority`, {
    method: "POST",
    body: JSON.stringify({ priority }),
  });
  return mapRequest(raw);
}

// BR-TRANSMIT-001 — "Terminer le traitement" : résumé/solution/travail réalisé
// obligatoires pour tout intervenant actuel, quel que soit son rôle.
export type ResolveTreatmentData = {
  summary: string;
  solution: string;
  work_done: string;
  recommendations?: string;
  attachment_ids?: string[];
};

export async function resolveRequest(
  id: string,
  data: ResolveTreatmentData,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

// BR-TRANSMIT-001 — "Transmettre le traitement" : réservé à l'intervenant actuel,
// cible libre dans toute l'organisation (annuaire complet, backend seul juge).
export type TransmitTreatmentData = {
  to_user_id: string;
  work_done: string;
  reason: string;
  instruction?: string;
  attachment_ids?: string[];
};

export async function transmitTreatment(
  id: string,
  data: TransmitTreatmentData,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/transmit`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function assignRequest(
  id: string,
  assigneeId: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = new URLSearchParams({ assignee_id: assigneeId });
  if (actorId) params.set("actor_id", actorId);
  const raw = await apiFetch<RawRequest>(`/requests/${id}/assign?${params.toString()}`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}

export type QueueFilters = {
  page?: number;
  limit?: number;
  direction_id?: string;
  unit_id?: string;
  assignee_id?: string;
  unassigned_only?: boolean;
  priority?: string;
  request_status?: string;
  search?: string;
};

export async function fetchQueue(
  filters?: QueueFilters,
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== "") params.set(k, String(v));
    }
  }
  const raw = await apiFetch<RawPaginated<RawRequest>>(`/requests/queue?${params.toString()}`);
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
  };
}

export type QualifyTriageData = {
  category: string;
  priority: string;
  direction_id?: string;
  unit_id?: string;
  assignee_id?: string;
};

export async function qualifyTriage(
  id: string,
  data: QualifyTriageData,
  actorId?: string,
): Promise<RequestItem> {
  const params = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}/qualify${params}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function cancelRequest(
  id: string,
  reason: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = new URLSearchParams();
  if (actorId) params.set("actor_id", actorId);
  params.set("reason", reason);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}/cancel${qs}`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}

/** Phase 1 — L'utilisateur refuse la résolution (motif obligatoire). */
export async function requestReopen(
  id: string,
  reason: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/request-reopen`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return mapRequest(raw);
}

/** Phase 2 — Le chef approuve la réouverture (réservé chief/director/admin). */
export async function reopenRequest(
  id: string,
  reason?: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = new URLSearchParams();
  if (actorId) params.set("actor_id", actorId);
  const qs = params.toString() ? `?${params.toString()}` : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}/reopen${qs}`, {
    method: "POST",
    body: JSON.stringify(reason ? { reason } : {}),
  });
  return mapRequest(raw);
}

/** Phase 2 — Le chef refuse la réouverture avec motif obligatoire. */
export async function rejectReopenRequest(
  id: string,
  reason: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/reject-reopen`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return mapRequest(raw);
}

export async function closeRequest(
  id: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = actorId ? `?actor_id=${actorId}` : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}/close${params}`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}

// ── API : Commentaires ────────────────────────────────────────────────────────

export type CreateCommentData = {
  author_id: number | string;  // Le backend overrides depuis le JWT, envoyer 0 comme placeholder
  author_name: string;
  body: string;
  is_public: boolean;
  attachment_id?: string;
  is_directive?: boolean;
  reply_to_id?: string;
};

export async function fetchComments(requestId: string, publicOnly = false) {
  const params = publicOnly ? "?public_only=true" : "";
  const raw = await apiFetch<RawTimeline[]>(`/requests/${requestId}/comments${params}`);
  return (raw ?? []).map(mapComment);
}

export async function createComment(
  requestId: string,
  data: CreateCommentData,
) {
  const raw = await apiFetch<RawTimeline>(`/requests/${requestId}/comments`, {
    method: "POST",
    body: JSON.stringify({
      body: data.body,
      is_public: data.is_public,
      ...(data.attachment_id ? { attachment_id: data.attachment_id } : {}),
      ...(data.is_directive ? { is_directive: true } : {}),
      ...(data.reply_to_id ? { reply_to_id: data.reply_to_id } : {}),
    }),
  });
  return mapComment(raw);
}

export async function deleteComment(
  requestId: string,
  commentId: string,
): Promise<void> {
  await apiFetch<void>(`/requests/${requestId}/comments/${commentId}`, {
    method: "DELETE",
  });
}

// ── API : Pièces jointes ──────────────────────────────────────────────────────

export async function fetchAttachments(requestId: string): Promise<RawAttachment[]> {
  const raw = await apiFetch<RawAttachment[]>(
    `/requests/${requestId}/attachments`,
  );
  return raw ?? [];
}

export async function uploadAttachment(
  requestId: string,
  file: File,
  uploaderId?: string,
  skipTimelineEvent?: boolean,
): Promise<RawAttachment> {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams();
  if (uploaderId) params.set("uploader_id", uploaderId);
  if (skipTimelineEvent) params.set("skip_timeline_event", "true");
  const query = params.toString();
  return apiFetch<RawAttachment>(
    `/requests/${requestId}/attachments${query ? `?${query}` : ""}`,
    {
      method: "POST",
      body: form,
      skipContentType: true, // laisser le browser poser le boundary multipart
    },
  );
}

export async function deleteAttachment(
  requestId: string,
  attachmentId: string,
): Promise<void> {
  await apiFetch<void>(`/requests/${requestId}/attachments/${attachmentId}`, {
    method: "DELETE",
  });
}

export async function fetchAttachmentFile(
  attachment: RawAttachment,
): Promise<{ blob: Blob; filename: string; contentType?: string }> {
  const file = await apiFetchBlob(attachment.storage_path);
  return {
    blob: file.blob,
    filename: file.filename ?? attachment.filename,
    contentType: file.contentType ?? attachment.mime_type,
  };
}

/** Rejet d'un ticket par le chef de service — motif obligatoire. */
export async function rejectTicket(
  id: string,
  reason: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/reject`, {
    method: "POST",
    body: JSON.stringify({ reason }),
  });
  return mapRequest(raw);
}

/** Réaffectation d'un ticket à un autre service. */
export async function reassignService(
  id: string,
  targetUnityId: string,
  reason?: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/reassign`, {
    method: "POST",
    body: JSON.stringify({ target_unity_id: targetUnityId, reason }),
  });
  return mapRequest(raw);
}

/** Transfert d'un ticket vers une autre direction. */
export async function transferDirection(
  id: string,
  targetDirectionId: string,
  reason: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/transfer-direction`, {
    method: "POST",
    body: JSON.stringify({ target_direction_id: targetDirectionId, reason }),
  });
  return mapRequest(raw);
}

export async function escalateRequest(
  id: string,
  data: { reason: string },
): Promise<void> {
  await apiFetch<RawTimeline>(`/requests/${id}/escalate`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Lot 3.3 — "Escalade exceptionnelle" : réservée à chief-departement, cible
// directement le directeur (court-circuite la hiérarchie normale de /escalate).
export async function escalateToDirectorRequest(
  id: string,
  data: { reason: string },
): Promise<void> {
  await apiFetch<RawTimeline>(`/requests/${id}/escalate-to-director`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function requesterEditRequest(
  id: string,
  data: {
    title?: string;
    description?: string;
  },
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/requester-edit`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}
