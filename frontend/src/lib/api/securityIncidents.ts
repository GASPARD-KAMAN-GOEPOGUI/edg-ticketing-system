import { apiFetch } from "./client";

export type SecurityIncident = {
  id: number;
  uuid: string;
  email_attempted: string | null;
  ip_address: string | null;
  user_agent: string | null;
  browser: string | null;
  os_info: string | null;
  device_type: string | null;
  location_approx: string | null;
  photo_path: string | null;
  occurred_at: string | null;
  attempt_count: number;
  resolved: boolean;
  resolved_at: string | null;
  resolved_by: number | null;
  notes: string | null;
  created_at: string;
};

export type PaginatedIncidents = {
  items: SecurityIncident[];
  total: number;
  page: number;
  pages: number;
};

export async function fetchSecurityIncidents(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedIncidents> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  return apiFetch<PaginatedIncidents>(`/admin/security-incidents?${qs}`);
}

export async function resolveIncident(
  id: number,
  notes?: string,
): Promise<{ id: number; resolved: boolean }> {
  return apiFetch(`/admin/security-incidents/${id}/resolve`, {
    method: "PATCH",
    body: JSON.stringify({ notes: notes ?? null }),
  });
}

export async function deleteIncident(id: number): Promise<void> {
  await apiFetch(`/admin/security-incidents/${id}`, { method: "DELETE" });
}
