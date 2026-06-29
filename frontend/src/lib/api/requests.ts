/**
 * Module API — Demandes EDG Support.
 *
 * Toutes les fonctions :
 *  - appellent le backend FastAPI via apiFetch
 *  - retournent des types compatibles avec les mocks (RequestItem etc.)
 *    pour que les composants UI n'aient pas besoin de changer
 */

import { apiFetch } from "./client";
import type {
  RequestItem,
  RequestStatus,
  Priority,
  Appreciation,
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
  ref: string;
  title: string;
  description: string;
  request_status: string;
  priority: string;
  category: string;
  unity_id?: number | null;
  unit_id?: number | string | null;   // alias backend de unity_id
  direction_id?: number | string | null; // réservé (null depuis le backend)
  assignee_id?: string;
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
  requester_id?: string;
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
    requesterId: raw.requester_id ?? "",
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
    assigneeId: raw.assignee_id ?? undefined,
    assigneeName: raw.assignee_name ?? undefined,
    isExternal: raw.is_external,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    slaHours: raw.sla_hours,
    slaElapsed: raw.sla_elapsed,
    comments: (raw.timelines ?? [])
      .filter((t) => t.event_type === "comment_added")
      .map((t) => ({
        id: t.id,
        authorId: t.agent_id ? String(t.agent_id) : "",
        author: t.actor_name ?? "Système",
        body: t.comment ?? t.label ?? "",
        isPublic: t.infos?.is_public === true,
        isEdited: false,
        createdAt: t.created_at,
      })),
    timeline: (raw.timelines ?? []).map((t) => ({
      id: t.id,
      type: t.event_type,
      label: t.label,
      at: t.created_at,
      by: t.actor_name ?? undefined,
    })),
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
  };
}

export function mapComment(t: RawTimeline) {
  return {
    id: t.id,
    authorId: t.agent_id ? String(t.agent_id) : "",
    author: t.actor_name ?? "Système",
    body: t.comment ?? t.label ?? "",
    isPublic: t.infos?.is_public === true,
    isEdited: false,
    createdAt: t.created_at,
  };
}

// ── API : Lectures ────────────────────────────────────────────────────────────

export type RequestStats = Record<string, number>;

export async function fetchRequestStats(): Promise<RequestStats> {
  return apiFetch<RequestStats>("/requests/stats/by-status");
}

export async function fetchRequests(
  filters?: RequestFilters,
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  if (filters) {
    for (const [k, v] of Object.entries(filters)) {
      if (v !== undefined && v !== null && v !== "") {
        params.set(k, String(v));
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

export async function fetchRequest(id: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}`);
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
  data: Partial<RawRequest>,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function resolveRequest(
  id: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = actorId ? `?actor_id=${actorId}` : "";
  const raw = await apiFetch<RawRequest>(`/requests/${id}/resolve${params}`, {
    method: "POST",
    body: "{}",
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
  direction_id: string;
  unit_id?: string;
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
  reason?: string,
  actorId?: string,
): Promise<RequestItem> {
  const params = new URLSearchParams();
  if (actorId) params.set("actor_id", actorId);
  if (reason) params.set("reason", reason);
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

/** Phase 2 — Le chef approuve la réouverture (réservé agent/chief/admin). */
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
    body: JSON.stringify({ body: data.body, is_public: data.is_public }),
  });
  return mapComment(raw);
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
): Promise<RawAttachment> {
  const form = new FormData();
  form.append("file", file);
  const params = uploaderId ? `?uploader_id=${uploaderId}` : "";
  return apiFetch<RawAttachment>(
    `/requests/${requestId}/attachments${params}`,
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

export async function escalateRequest(
  id: string,
  data: { level: string; reason: string; from_agent_name?: string },
  actorId?: string,
): Promise<void> {
  const params = actorId ? `?actor_id=${encodeURIComponent(actorId)}` : "";
  await apiFetch<RawTimeline>(`/requests/${id}/escalate${params}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function mergeRequest(id: string, targetId: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/merge`, {
    method: "POST",
    body: JSON.stringify({ target_id: targetId }),
  });
  return mapRequest(raw);
}

export async function requesterEditRequest(
  id: string,
  data: {
    title?: string;
    description?: string;
    category?: string;
    priority?: string;
    direction_id?: string;
    unit_id?: string;
    unity_id?: string | number;
  },
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/requester-edit`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

export async function duplicateRequest(id: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/duplicate`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}
