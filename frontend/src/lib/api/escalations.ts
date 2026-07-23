/**
 * Module API — Escalades
 * Endpoints : /escalations/*, /requests/:id/escalate
 */
import { apiFetch } from "./client";
import type { EscalationItem } from "@/lib/mock-data";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawEscalation = {
  id: string;
  request_id: string;
  request_ref: string;
  title: string;
  from_user_id?: string | null;
  from_agent_name: string;
  to_user_id?: string | null;
  to_agent_name: string;
  level: string;
  reason: string;
  sla_over_hours: number;
  priority: string;
  escalation_status: string;
  decision_comment?: string | null;
  dg_comment?: string | null;
  status: boolean;
  infos?: unknown;
  created_at: string;
  updated_at: string;
};

export type PaginatedEscalations = {
  items: EscalationItem[];
  total: number;
  page: number;
  pages: number;
};

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapEscalation(raw: RawEscalation): EscalationItem {
  const status = raw.escalation_status === "reviewed" ? "in_review" : raw.escalation_status;
  const level = raw.level === "DG" ? "L3" : raw.level;
  return {
    id: raw.id,
    requestId: raw.request_id ?? undefined,
    requestRef: raw.request_ref,
    title: raw.title,
    fromAgent: raw.from_agent_name,
    toAgent: raw.to_agent_name === "Direction Générale" ? "Directeur" : raw.to_agent_name,
    level: level as EscalationItem["level"],
    reason: raw.reason,
    slaOverHours: raw.sla_over_hours,
    priority: raw.priority as EscalationItem["priority"],
    at: raw.created_at,
    status: status as EscalationItem["status"],
    decisionComment: raw.decision_comment ?? raw.dg_comment ?? undefined,
  };
}

// ── Fonctions ─────────────────────────────────────────────────────────────────

export async function fetchEscalations(params?: {
  status?: string;
  level?: string;
  page?: number;
  limit?: number;
}): Promise<PaginatedEscalations> {
  const qs = new URLSearchParams();
  if (params?.status) qs.set("status", params.status === "in_review" ? "reviewed" : params.status);
  if (params?.level) qs.set("level", params.level);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawEscalation[];
    total: number;
    page: number;
    pages: number;
  }>(`/escalations?${qs}`);
  return { ...raw, items: raw.items.map(mapEscalation) };
}

export async function fetchEscalation(id: string): Promise<EscalationItem> {
  const raw = await apiFetch<RawEscalation>(`/escalations/${id}`);
  return mapEscalation(raw);
}

export async function reviewEscalation(id: string): Promise<EscalationItem> {
  const raw = await apiFetch<RawEscalation>(`/escalations/${id}/review`, {
    method: "PATCH",
    body: "{}",
  });
  return mapEscalation(raw);
}

export async function resolveEscalation(
  id: string,
  options?: { comment?: string; action?: "resolve" | "reject" },
): Promise<EscalationItem> {
  const raw = await apiFetch<RawEscalation>(`/escalations/${id}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({
      decision_comment: options?.comment ?? null,
      action: options?.action ?? "resolve",
    }),
  });
  return mapEscalation(raw);
}

export async function escalateRequest(
  requestId: string,
  data: {
    level: string;
    reason: string;
    from_agent_name?: string;
    to_agent_name?: string;
    to_user_id?: string;
    sla_over_hours?: number;
  },
): Promise<EscalationItem> {
  const raw = await apiFetch<RawEscalation>(`/requests/${requestId}/escalate`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapEscalation(raw);
}
