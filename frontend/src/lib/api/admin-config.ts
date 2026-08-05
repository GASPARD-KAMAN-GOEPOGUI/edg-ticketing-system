/**
 * Module API — Admin Config (SLA, Priorités, Routage, Référentiels)
 * Tous les appels pointent vers /api/v1/admin/*
 */
import { apiFetch } from "./client";
import type { SLAPolicy, PriorityDefinition, RoutingRule } from "@/lib/mock-data";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawSlaPolicy = {
  id: string;
  category: string;
  priority: string;
  response_h: number;
  resolution_h: number;
  escalate_after_h: number;
  status: boolean;
  infos?: unknown;
  created_at: string;
  updated_at: string;
};

export type RawPriorityDef = {
  id: string;
  slug: string;
  label: string;
  description: string;
  color: string;
  sort_order: number;
  is_builtin: boolean;
  status: boolean;
  infos?: unknown;
  created_at: string;
  updated_at: string;
};

export type RawRoutingRule = {
  id: string;
  name: string;
  condition_field: string;
  condition_value: string;
  target_unity_id?: number | null;
  target_unity_codename?: string | null;
  target_unity_label?: string | null;
  target_unity_direction_id?: string | null;
  auto_assign: boolean;
  sort_order: number;
  status: boolean;
  infos?: { target_unity_codename?: string; target_unity_label?: string; target_unity_direction_id?: string; [k: string]: unknown } | null;
  created_at: string;
  updated_at: string;
};

export type RawRefItem = {
  id: string;
  code: string;
  label: string;
  sort_order: number;
  is_builtin: boolean;
  status: boolean;
  infos?: unknown;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
};

// ── Mappers ───────────────────────────────────────────────────────────────────

export function mapSlaPolicy(raw: RawSlaPolicy): SLAPolicy {
  return {
    id: raw.id,
    category: raw.category,
    priority: raw.priority as SLAPolicy["priority"],
    responseH: raw.response_h,
    resolutionH: raw.resolution_h,
    escalateAfterH: raw.escalate_after_h,
    active: raw.status,
  };
}

export function mapPriorityDef(raw: RawPriorityDef): PriorityDefinition {
  return {
    id: raw.id,
    slug: raw.slug,
    label: raw.label,
    description: raw.description,
    color: raw.color as PriorityDefinition["color"],
    order: raw.sort_order,
    active: raw.status,
    isBuiltin: raw.is_builtin,
  };
}

export function mapRoutingRule(raw: RawRoutingRule): RoutingRule {
  const codename = raw.target_unity_codename ?? raw.infos?.target_unity_codename ?? "";
  const label = raw.target_unity_label ?? raw.infos?.target_unity_label ?? codename;
  const dirId = raw.target_unity_direction_id ?? raw.infos?.target_unity_direction_id ?? "";
  return {
    id: raw.id,
    name: raw.name,
    conditionField: raw.condition_field as RoutingRule["conditionField"],
    conditionValue: raw.condition_value,
    targetDirection: dirId,
    targetService: codename,
    targetServiceLabel: label,
    autoAssign: raw.auto_assign,
    active: raw.status,
    order: raw.sort_order,
  };
}

// ── SLA Policies ──────────────────────────────────────────────────────────────

export async function fetchSlaPolicies(): Promise<SLAPolicy[]> {
  const raw = await apiFetch<RawSlaPolicy[]>("/admin/sla");
  return raw.map(mapSlaPolicy);
}

export async function createSlaPolicy(
  data: Pick<SLAPolicy, "category" | "priority" | "responseH" | "resolutionH" | "escalateAfterH" | "active">,
): Promise<SLAPolicy> {
  const raw = await apiFetch<RawSlaPolicy>("/admin/sla", {
    method: "POST",
    body: JSON.stringify({
      category: data.category,
      priority: data.priority,
      response_h: data.responseH,
      resolution_h: data.resolutionH,
      escalate_after_h: data.escalateAfterH,
      status: data.active,
    }),
  });
  return mapSlaPolicy(raw);
}

export async function updateSlaPolicy(
  id: string,
  data: Partial<Pick<SLAPolicy, "responseH" | "resolutionH" | "escalateAfterH" | "active">>,
): Promise<SLAPolicy> {
  const patch: Record<string, unknown> = {};
  if (data.responseH !== undefined) patch.response_h = data.responseH;
  if (data.resolutionH !== undefined) patch.resolution_h = data.resolutionH;
  if (data.escalateAfterH !== undefined) patch.escalate_after_h = data.escalateAfterH;
  if (data.active !== undefined) patch.status = data.active;
  const raw = await apiFetch<RawSlaPolicy>(`/admin/sla/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return mapSlaPolicy(raw);
}

export async function toggleSlaPolicy(id: string): Promise<SLAPolicy> {
  const raw = await apiFetch<RawSlaPolicy>(`/admin/sla/${id}/toggle`, {
    method: "PATCH",
    body: "{}",
  });
  return mapSlaPolicy(raw);
}

export async function deleteSlaPolicy(id: string): Promise<void> {
  await apiFetch<void>(`/admin/sla/${id}`, { method: "DELETE" });
}

// ── Priority Definitions ───────────────────────────────────────────────────────

export async function fetchPriorityDefs(): Promise<PriorityDefinition[]> {
  const raw = await apiFetch<RawPriorityDef[]>("/admin/priorities");
  return raw.map(mapPriorityDef);
}

export async function createPriorityDef(
  data: Omit<PriorityDefinition, "id" | "isBuiltin">,
): Promise<PriorityDefinition> {
  const raw = await apiFetch<RawPriorityDef>("/admin/priorities", {
    method: "POST",
    body: JSON.stringify({
      slug: data.slug,
      label: data.label,
      description: data.description,
      color: data.color,
      sort_order: data.order,
      is_builtin: false,
    }),
  });
  return mapPriorityDef(raw);
}

export async function updatePriorityDef(
  id: string,
  data: Partial<Pick<PriorityDefinition, "label" | "description" | "color" | "order" | "active">>,
): Promise<PriorityDefinition> {
  const patch: Record<string, unknown> = {};
  if (data.label !== undefined) patch.label = data.label;
  if (data.description !== undefined) patch.description = data.description;
  if (data.color !== undefined) patch.color = data.color;
  if (data.order !== undefined) patch.sort_order = data.order;
  if (data.active !== undefined) patch.status = data.active;
  const raw = await apiFetch<RawPriorityDef>(`/admin/priorities/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return mapPriorityDef(raw);
}

export async function reorderPriorityDefs(orderedIds: string[]): Promise<void> {
  await apiFetch<unknown>("/admin/priorities/reorder", {
    method: "PATCH",
    body: JSON.stringify({ ordered_ids: orderedIds.map(Number) }),
  });
}

export async function deletePriorityDef(id: string): Promise<void> {
  await apiFetch<void>(`/admin/priorities/${id}`, { method: "DELETE" });
}

// ── Routing Rules ─────────────────────────────────────────────────────────────

export async function fetchRoutingRules(): Promise<RoutingRule[]> {
  const res = await apiFetch<{ items: RawRoutingRule[] }>("/admin/routing");
  return res.items.map(mapRoutingRule);
}

export async function createRoutingRule(data: Omit<RoutingRule, "id">): Promise<RoutingRule> {
  const raw = await apiFetch<RawRoutingRule>("/admin/routing", {
    method: "POST",
    body: JSON.stringify({
      name: data.name,
      condition_field: data.conditionField,
      condition_value: data.conditionValue,
      target_unity_codename: data.targetService || undefined,
      auto_assign: data.autoAssign,
      sort_order: data.order,
      status: data.active,
    }),
  });
  return mapRoutingRule(raw);
}

export async function updateRoutingRule(
  id: string,
  data: Partial<Omit<RoutingRule, "id">>,
): Promise<RoutingRule> {
  const patch: Record<string, unknown> = {};
  if (data.name !== undefined) patch.name = data.name;
  if (data.conditionField !== undefined) patch.condition_field = data.conditionField;
  if (data.conditionValue !== undefined) patch.condition_value = data.conditionValue;
  if (data.targetService !== undefined) patch.target_unity_codename = data.targetService || undefined;
  if (data.autoAssign !== undefined) patch.auto_assign = data.autoAssign;
  if (data.order !== undefined) patch.sort_order = data.order;
  if (data.active !== undefined) patch.status = data.active;
  const raw = await apiFetch<RawRoutingRule>(`/admin/routing/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
  return mapRoutingRule(raw);
}

export async function toggleRoutingRule(id: string): Promise<RoutingRule> {
  const raw = await apiFetch<RawRoutingRule>(`/admin/routing/${id}/toggle`, {
    method: "PATCH",
    body: "{}",
  });
  return mapRoutingRule(raw);
}

export async function reorderRoutingRules(orderedIds: string[]): Promise<void> {
  await apiFetch<unknown>("/admin/routing/reorder", {
    method: "PATCH",
    body: JSON.stringify({ ordered_ids: orderedIds.map(Number) }),
  });
}

export async function deleteRoutingRule(id: string): Promise<void> {
  await apiFetch<void>(`/admin/routing/${id}`, { method: "DELETE" });
}

export async function testRoutingRule(data: Record<string, string>): Promise<{
  matched: boolean;
  rule_id?: string;
  rule_name?: string;
  target_direction_id?: string;
  target_unit_id?: string;
  auto_assign?: boolean;
}> {
  return apiFetch("/admin/routing/apply", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// ── Reference Tables ──────────────────────────────────────────────────────────

export const REF_TABLES = [
  "request_statuses",
  "request_categories",
  "account_statuses",
  "knowledge_categories",
  "announcement_categories",
  "announcement_priorities",
  "announcement_statuses",
] as const;

export type RefTableName = (typeof REF_TABLES)[number];

export const REF_TABLE_LABELS: Record<RefTableName, string> = {
  request_statuses:        "Statuts de ticket",
  request_categories:      "Catégories de ticket",
  account_statuses:        "Statuts de compte",
  knowledge_categories:    "Catégories de connaissance",
  announcement_categories: "Catégories d'annonce",
  announcement_priorities: "Priorités d'annonce",
  announcement_statuses:   "Statuts d'annonce",
};

export async function fetchRefTable(table: RefTableName): Promise<RawRefItem[]> {
  const res = await apiFetch<{ items: RawRefItem[] }>(`/admin/ref/${table}`);
  return res.items;
}

/** Endpoint public (tous rôles authentifiés) — utilisé dans les formulaires non-admin. */
export async function fetchRequestCategories(): Promise<RawRefItem[]> {
  const raw = await apiFetch<RawRefItem[]>("/references/request-categories");
  return Array.isArray(raw) ? raw : (raw as { items?: RawRefItem[] }).items ?? [];
}

/** Endpoint public (tous rôles authentifiés) — utilisé par /app/knowledge, accessible à tous. */
export async function fetchKnowledgeCategories(): Promise<RawRefItem[]> {
  const raw = await apiFetch<RawRefItem[]>("/references/knowledge-categories");
  return Array.isArray(raw) ? raw : (raw as { items?: RawRefItem[] }).items ?? [];
}

export async function createRefItem(
  table: RefTableName,
  data: { code: string; label: string; sort_order?: number },
): Promise<RawRefItem> {
  return apiFetch<RawRefItem>(`/admin/ref/${table}`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateRefItem(
  table: RefTableName,
  id: string,
  data: { label?: string; sort_order?: number; status?: boolean },
): Promise<RawRefItem> {
  return apiFetch<RawRefItem>(`/admin/ref/${table}/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteRefItem(
  table: RefTableName,
  id: string,
): Promise<void> {
  await apiFetch<void>(`/admin/ref/${table}/${id}`, { method: "DELETE" });
}

export async function restoreRefItem(
  table: RefTableName,
  id: string,
): Promise<RawRefItem> {
  return apiFetch<RawRefItem>(`/admin/ref/${table}/${id}/restore`, {
    method: "PATCH",
    body: "{}",
  });
}
