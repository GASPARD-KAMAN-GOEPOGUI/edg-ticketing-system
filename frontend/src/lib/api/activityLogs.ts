/**
 * Module API — Journaux d'activité
 * Endpoints : /activity-logs/*
 */
import { apiFetch } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ActivityLogEntry = {
  id: string;
  actor: string;
  actor_id?: number | null;
  actor_role: string;
  action: string;
  category: string;
  target: string;
  ip_address?: string | null;
  user_agent?: string | null;
  log_status: "success" | "warning" | "error";
  created_at: string;
  updated_at: string;
};

export type PaginatedLogs = {
  items: ActivityLogEntry[];
  total: number;
  page: number;
  pages: number;
};

// ── Fonctions ─────────────────────────────────────────────────────────────────

export async function fetchActivityLogs(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedLogs> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<PaginatedLogs>(`/activity-logs?${qs}`);
  return raw;
}

export async function fetchActivityLogErrors(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedLogs> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch<PaginatedLogs>(`/activity-logs/errors?${qs}`);
}

export async function searchActivityLogs(q: string, params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedLogs> {
  const qs = new URLSearchParams({ q });
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch<PaginatedLogs>(`/activity-logs/search?${qs}`);
}

export async function fetchLogsByActor(actorId: string, params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedLogs> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch<PaginatedLogs>(`/activity-logs/by-actor/${actorId}?${qs}`);
}
