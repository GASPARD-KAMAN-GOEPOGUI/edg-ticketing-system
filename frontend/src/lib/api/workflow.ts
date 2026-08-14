/**
 * Module API — Workflow
 * Endpoints : /requests/:id/workflow, /workflows/:id/*
 */
import { apiFetch } from "./client";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawWorkflow = {
  id: string;
  request_id: string;
  workflow_status: string;
  status: boolean;
  infos?: unknown;
  created_at: string;
  updated_at: string;
};

export type RawWorkflowDetail = {
  id: string;
  workflow_id: string;
  unit_id?: string | null;
  agent_id?: string | null;
  task_id?: string | null;
  parent_id?: string | null;
  accepted: boolean;
  activated: boolean;
  workflow_status: string;
  status: boolean;
  infos?: unknown;
  created_at: string;
  updated_at: string;
};

// ── Types frontend ────────────────────────────────────────────────────────────

export type WorkflowItem = {
  id: string;
  requestId: string;
  workflowStatus: string;
  active: boolean;
  createdAt: string;
};

export type WorkflowDetailItem = {
  id: string;
  workflowId: string;
  unitId?: string | null;
  agentId?: string | null;
  taskId?: string | null;
  parentId?: string | null;
  accepted: boolean;
  activated: boolean;
  workflowStatus: string;
  createdAt: string;
};

// ── Mappers ───────────────────────────────────────────────────────────────────

export function mapWorkflow(raw: RawWorkflow): WorkflowItem {
  return {
    id: raw.id,
    requestId: raw.request_id,
    workflowStatus: raw.workflow_status,
    active: raw.status,
    createdAt: raw.created_at,
  };
}

export function mapWorkflowDetail(raw: RawWorkflowDetail): WorkflowDetailItem {
  return {
    id: raw.id,
    workflowId: raw.workflow_id,
    unitId: raw.unit_id,
    agentId: raw.agent_id,
    taskId: raw.task_id,
    parentId: raw.parent_id,
    accepted: raw.accepted,
    activated: raw.activated,
    workflowStatus: raw.workflow_status,
    createdAt: raw.created_at,
  };
}

// ── Workflows ─────────────────────────────────────────────────────────────────

export async function fetchRequestWorkflows(requestId: string): Promise<WorkflowItem[]> {
  const raw = await apiFetch<RawWorkflow[]>(`/requests/${requestId}/workflow`);
  return raw.map(mapWorkflow);
}

export async function createRequestWorkflow(
  requestId: string,
  data: { workflow_status?: string } = {},
): Promise<WorkflowItem> {
  const raw = await apiFetch<RawWorkflow>(`/requests/${requestId}/workflow`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapWorkflow(raw);
}

export async function fetchWorkflow(id: string): Promise<WorkflowItem> {
  const raw = await apiFetch<RawWorkflow>(`/workflows/${id}`);
  return mapWorkflow(raw);
}

export async function updateWorkflow(
  id: string,
  data: { workflow_status?: string },
): Promise<WorkflowItem> {
  const raw = await apiFetch<RawWorkflow>(`/workflows/${id}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return mapWorkflow(raw);
}

// ── Workflow Details ──────────────────────────────────────────────────────────

export async function fetchWorkflowDetails(workflowId: string): Promise<WorkflowDetailItem[]> {
  const raw = await apiFetch<RawWorkflowDetail[]>(`/workflows/${workflowId}/details`);
  return raw.map(mapWorkflowDetail);
}

export async function createWorkflowDetail(
  workflowId: string,
  data: {
    unit_id?: string;
    agent_id?: string;
    task_id?: string;
    parent_id?: string;
    accepted?: boolean;
    activated?: boolean;
  },
): Promise<WorkflowDetailItem> {
  const raw = await apiFetch<RawWorkflowDetail>(`/workflows/${workflowId}/details`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapWorkflowDetail(raw);
}

export async function updateWorkflowDetail(
  workflowId: string,
  detailId: string,
  data: { accepted?: boolean; activated?: boolean; workflow_status?: string },
): Promise<WorkflowDetailItem> {
  const raw = await apiFetch<RawWorkflowDetail>(
    `/workflows/${workflowId}/details/${detailId}`,
    { method: "PUT", body: JSON.stringify(data) },
  );
  return mapWorkflowDetail(raw);
}

// ── Workflow search (pattern edgrh /search/) ──────────────────────────────────

export async function searchWorkflows(params?: {
  request_id?: number;
  workflow_status?: string;
  uuid?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: WorkflowItem[]; total: number; page: number; pages: number }> {
  const qs = new URLSearchParams();
  if (params?.request_id != null) qs.set("request_id", String(params.request_id));
  if (params?.workflow_status) qs.set("workflow_status", params.workflow_status);
  if (params?.uuid) qs.set("uuid", params.uuid);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{ items: RawWorkflow[]; total: number; page: number; pages: number }>(
    `/workflows/search/?${qs}`,
  );
  return { ...raw, items: raw.items.map(mapWorkflow) };
}

// ── Workflow Details — accept / search (pattern edgrh /detail-workflow/) ──────

export async function acceptWorkflowStep(
  workflowId: string,
  detailId: string,
  data: { accepted: boolean; comment?: string },
): Promise<WorkflowDetailItem> {
  const raw = await apiFetch<RawWorkflowDetail>(
    `/workflows/${workflowId}/details/${detailId}/accept`,
    { method: "POST", body: JSON.stringify(data) },
  );
  return mapWorkflowDetail(raw);
}

export async function acceptWorkflowDetailById(data: {
  id: number;
  accepted: boolean;
  comment?: string;
}): Promise<WorkflowDetailItem> {
  const raw = await apiFetch<RawWorkflowDetail>(`/workflow-details/accepted`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
  return mapWorkflowDetail(raw);
}

export async function searchWorkflowDetails(params?: {
  workflow_id?: number;
  request_id?: number;
  agent_id?: number;
  unit_id?: number;
  activated?: boolean;
  accepted?: boolean;
  page?: number;
  limit?: number;
}): Promise<{ items: WorkflowDetailItem[]; total: number; page: number; pages: number }> {
  const qs = new URLSearchParams();
  if (params?.workflow_id != null) qs.set("workflow_id", String(params.workflow_id));
  if (params?.request_id != null) qs.set("request_id", String(params.request_id));
  if (params?.agent_id != null) qs.set("agent_id", String(params.agent_id));
  if (params?.unit_id != null) qs.set("unit_id", String(params.unit_id));
  if (params?.activated != null) qs.set("activated", String(params.activated));
  if (params?.accepted != null) qs.set("accepted", String(params.accepted));
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawWorkflowDetail[];
    total: number;
    page: number;
    pages: number;
  }>(`/workflow-details/search/?${qs}`);
  return { ...raw, items: raw.items.map(mapWorkflowDetail) };
}

