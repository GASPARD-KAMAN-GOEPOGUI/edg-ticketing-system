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
  // Procédure tâche 1.3 — présent UNIQUEMENT sur la file Distribution du chef
  // de division (endpoint gardé). Partout ailleurs il est absent par
  // construction : le demandeur ne doit jamais le recevoir.
  proposed_solution?: string | null;
  // PV d'intervention (taches 3.3/3.4) — presents sur le TSI uniquement.
  pv_validated_at?: string | null;
  pv_submitted_at?: string | null;
  pv_archived_at?: string | null;
  intervenant_name?: string | null;
  intervenant_badge?: string | null;
  employee_matricule?: string;
  requester_job?: string;
  requester_direction_id?: number | string | null;
  requester_unit_id?: number | string | null;
  // Libellés organisationnels figés au moment des faits (création pour le
  // demandeur, qualification pour le traitant) — absents des tickets antérieurs
  // au figeage, que l'on continue alors de résoudre depuis les identifiants.
  requester_direction_label?: string | null;
  requester_department_label?: string | null;
  requester_service_label?: string | null;
  handler_direction_label?: string | null;
  handler_department_label?: string | null;
  handler_service_label?: string | null;
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
  // Avatars des intervenants (demandeur, assigné, acteurs/destinataires du journal),
  // cle = account id (string) -> avatar_url. Détail ticket uniquement.
  participant_avatars?: Record<string, string>;
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
    proposedSolution: raw.proposed_solution ?? undefined,
    pvValidatedAt: raw.pv_validated_at ?? undefined,
    pvSubmittedAt: raw.pv_submitted_at ?? undefined,
    pvArchivedAt: raw.pv_archived_at ?? undefined,
    intervenantName: raw.intervenant_name ?? undefined,
    intervenantBadge: raw.intervenant_badge ?? undefined,
    employeeMatricule: raw.employee_matricule ?? undefined,
    requesterJob: raw.requester_job ?? undefined,
    requesterDirectionId: raw.requester_direction_id != null ? String(raw.requester_direction_id) : undefined,
    requesterServiceId: raw.requester_unit_id != null ? String(raw.requester_unit_id) : undefined,
    requesterDirectionLabel: raw.requester_direction_label ?? undefined,
    requesterDepartmentLabel: raw.requester_department_label ?? undefined,
    requesterServiceLabel: raw.requester_service_label ?? undefined,
    handlerDirectionLabel: raw.handler_direction_label ?? undefined,
    handlerDepartmentLabel: raw.handler_department_label ?? undefined,
    handlerServiceLabel: raw.handler_service_label ?? undefined,
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
    // Messagerie retirée le 2026-09-25 : le backend ne renvoie plus les
    // événements `comment_added` (conservés en base comme historique), ce
    // champ reste donc toujours vide. Gardé sur le type pour ne pas imposer
    // un refactor à la trentaine d'entrées de `mock-data.ts`.
    comments: [],
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
    participantAvatars: raw.participant_avatars ?? undefined,
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

export async function fetchTransmittedByMe(
  filters?: { page?: number; limit?: number; search?: string; retransmitted_only?: boolean },
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
    `/requests/transmitted?${params.toString()}`,
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

// BR-TRACE-001 — lookup admin par référence (accès global, contrairement à
// trackRequest qui exige un identifiant citoyen email/téléphone).
export async function getRequestByRef(ref: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/ref/${encodeURIComponent(ref.trim().toUpperCase())}`);
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
    method: "PUT",
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

/** BR-TRANSMIT-SCOPE-TECH-001 — destinataire possible pour une transmission. */
export type TransmitTarget = {
  id: string;
  name: string;
  /** « Badge » du formulaire : le matricule du personnel. */
  matricule?: string | null;
  role: string;
  /** Vrai pour le responsable qui a confié le ticket (remontée hiérarchique). */
  is_distributor: boolean;
};

/**
 * Destinataires autorisés pour « Transmettre le traitement », calculés par le
 * serveur selon le rôle de l'acteur et le ticket.
 *
 * `restricted: true` (technicien) → `items` est une liste fermée : le client
 * affiche une sélection et masque les filtres direction/département/service.
 * `restricted: false` → annuaire libre, comportement inchangé.
 */
export async function fetchTransmitTargets(
  id: string,
): Promise<{ restricted: boolean; items: TransmitTarget[] }> {
  const res = await apiFetch<{ restricted: boolean; items: TransmitTarget[] }>(
    `/requests/${id}/transmit-targets`,
  );
  return { restricted: !!res.restricted, items: res.items ?? [] };
}

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

// BR-DISTRIBUTION-001 — file "Distribution" du chef de division support : tickets
// que le chef de service lui a orientés et qui n'ont pas encore de responsable
// opérationnel. Le périmètre est forcé côté backend depuis l'acteur authentifié.
export async function fetchDistribution(
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
    `/requests/distribution?${params.toString()}`,
  );
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
  };
}

export type DistributionTechnician = {
  id: string;
  name: string;
  email?: string | null;
  avatar?: string | null;
};

/** Techniciens actifs de la division du chef de division — liste métier dédiée,
 *  déjà filtrée côté backend (aucun filtrage de sécurité côté client). */
export async function fetchDistributionTechnicians(): Promise<DistributionTechnician[]> {
  return apiFetch<DistributionTechnician[]>(`/requests/distribution/technicians`);
}

/** Le chef de division prend le ticket pour son propre traitement. */
export async function takeFromDistribution(id: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/distribution/take`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}

/** Le chef de division assigne le ticket à un technicien de sa division. */
export async function assignFromDistribution(
  id: string,
  technicianId: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/distribution/assign`, {
    method: "POST",
    body: JSON.stringify({ technician_id: technicianId }),
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
  /** Procédure tâche 1.3 — exigé par le backend uniquement à l'imputation vers
   *  un chef de division support (pas pour une prise en charge personnelle). */
  proposed_solution?: string;
};

/** Procédure EDG/PS-GSI/Pro-02, tâche 2.1 — constat d'intervention.
 *  L'intervenant confronte l'état réel de la requête à ce qui a été décrit,
 *  AVANT de la résoudre (tâche 2.2). À ne pas confondre avec `qualifyTriage`,
 *  qui est la qualification du chef de service depuis la File d'attente. */
export type FieldCheckData = {
  conformity: "conforme" | "ecart";
  findings: string;
  observed_category?: string;
  observed_priority?: string;
};

export async function submitFieldCheck(
  id: string,
  data: FieldCheckData,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/field-check`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}

/** BR-TRAITEMENT-PROGRESSIF-001 — « Démarrer le traitement », deuxième geste du
 *  workflow progressif, entre le constat et la terminaison.
 *
 *  Seul le lieu est transmis : la date et l'heure de début sont prises côté
 *  serveur, jamais envoyées par le navigateur. */
export async function startTreatment(
  id: string,
  location: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/start-treatment`, {
    method: "POST",
    body: JSON.stringify({ location }),
  });
  return mapRequest(raw);
}

/** Descriptif de la solution proposée par le chef de service à l'imputation.
 *  Endpoint séparé et gardé : ce descriptif n'est jamais inclus dans la fiche
 *  du ticket, que le demandeur peut lire. Renvoie 403 pour le demandeur. */
export async function fetchProposedSolution(id: string): Promise<string | undefined> {
  const raw = await apiFetch<{ proposed_solution?: string | null }>(
    `/requests/${id}/proposed-solution`,
  );
  return raw.proposed_solution ?? undefined;
}

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

/**
 * BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : réservé au demandeur,
 * motif obligatoire, aucune approbation hiérarchique. Le ticket retourne
 * directement dans la File d'attente pour un nouveau cycle.
 */
export async function reopenRequest(
  id: string,
  reason: string,
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/reopen`, {
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

// ── API : Commentaires — SUPPRIMÉE ────────────────────────────────────────────
//
// La messagerie de ticket a été retirée de l'application le 2026-09-25 : les
// endpoints `/requests/{id}/comments` (lecture, écriture, suppression)
// n'existent plus côté serveur, et les événements `comment_added` déjà
// enregistrés ne sortent plus par l'API — ils restent en base comme historique.
// `RequestItem.comments` est donc désormais toujours vide.

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

/** Dossier fonctionnel complet d'une demande (Excel ou PDF, logo EDG en
 * en-tête + filigrane pour le PDF) — réservé à l'espace Administration. */
export async function exportRequestDossier(
  id: string,
  format: "excel" | "pdf" = "excel",
): Promise<{ blob: Blob; filename: string }> {
  const file = await apiFetchBlob(`/requests/${id}/export?format=${format}`);
  const ext = format === "pdf" ? "pdf" : "xlsx";
  return { blob: file.blob, filename: file.filename ?? `dossier-${id}.${ext}` };
}

/** PV d'intervention au format officiel EDG/PS-GSI/PV-01 (procédure tâche 3.1).
 *  Accessible au demandeur également : c'est lui qui valide le dépannage et
 *  signe le PV (tâche 3.2). Le document n'expose jamais la solution proposée. */
export async function downloadPvIntervention(
  id: string,
): Promise<{ blob: Blob; filename: string }> {
  const file = await apiFetchBlob(`/requests/${id}/pv`);
  return { blob: file.blob, filename: file.filename ?? `PV-${id}.pdf` };
}

/** Procédure tâche 3.3 — « Soumettre le PV d'intervention au Chef de division ».
 *  Le destinataire n'est pas choisi : c'est le chef de division qui a réparti le
 *  ticket. Pièces jointes facultatives : le PV signé et scanné. */
export async function submitPvIntervention(
  id: string,
  attachmentIds?: string[],
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/pv/submit`, {
    method: "POST",
    body: JSON.stringify({ attachment_ids: attachmentIds ?? undefined }),
  });
  return mapRequest(raw);
}

/** Procédure tâche 3.4 — « Enregistrer et archiver le PV d'intervention ».
 *  Réservé au chef de division qui a réparti le ticket. */
export async function archivePvIntervention(id: string): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/pv/archive`, {
    method: "POST",
    body: "{}",
  });
  return mapRequest(raw);
}

/** TSI — Tableau de Suivi des Interventions (livrable de la tâche 3.4).
 *  Suit les tickets répartis par ce chef de division jusqu'à l'archivage de
 *  leur PV. Distinct du rapport statistique `/reports/interventions`. */
/** Onglet « Tickets résolus » — les tickets dont je suis l'intervenant courant
 *  et dont le traitement est terminé (`resolved` ou `closed`). Le périmètre est
 *  forcé côté serveur depuis le jeton : aucun paramètre ne le déplace. */
export async function fetchResolvedByMe(
  filters?: { page?: number; limit?: number },
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters ?? {})) {
    if (v !== undefined && v !== null) params.set(k, String(v));
  }
  const raw = await apiFetch<RawPaginated<RawRequest>>(
    `/requests/resolved-by-me?${params.toString()}`,
  );
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
  };
}

export async function fetchPvTracking(
  filters?: { page?: number; limit?: number },
): Promise<{ items: RequestItem[]; total: number; page: number; pages: number; pageSize: number }> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters ?? {})) {
    if (v !== undefined && v !== null) params.set(k, String(v));
  }
  const raw = await apiFetch<RawPaginated<RawRequest>>(
    `/requests/pv-tracking?${params.toString()}`,
  );
  return {
    items: raw.items.map(mapRequest),
    total: raw.total,
    page: raw.page,
    pages: raw.pages,
    pageSize: raw.page_size,
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

// Escalade retiree le 2026-09-26 : elle ciblait exclusivement
// chief-departement et director, deux roles supprimes du projet — elle
// n'avait donc plus aucun destinataire possible. Endpoints, service et
// statut `escalated` retires avec elle.

export async function requesterEditRequest(
  id: string,
  data: {
    title?: string;
    description?: string;
  },
): Promise<RequestItem> {
  const raw = await apiFetch<RawRequest>(`/requests/${id}/requester-edit`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return mapRequest(raw);
}
