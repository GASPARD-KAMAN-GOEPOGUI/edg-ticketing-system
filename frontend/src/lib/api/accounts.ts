/**
 * Module API — Comptes utilisateurs
 * Endpoints : /users/*, /users/me
 */
import { apiFetch } from "./client";
import { normalizeRole } from "../session";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawAccount = {
  id: string;
  keycloak_id?: string | null;
  unity_id?: string | number | null;
  name: string;
  firstname?: string | null;
  email: string;
  phone?: string | null;
  role: string;
  account_status: string;
  matricule?: string | null;
  job?: string | null;
  direction_id?: string | number | null;
  department_id?: string | number | null;
  unit_id?: string | number | null;
  avatar_url?: string | null;
  is_edg_employee: boolean;
  email_verified: boolean;
  activated_at?: string | null;
  mfa_enabled: boolean;
  availability?: string | null;
  notif_sla_alerts: boolean;
  notif_escalations: boolean;
  notif_comments: boolean;
  notif_resolutions: boolean;
  status: boolean;
  created_at: string;
  updated_at: string;
};

export type AccountUser = {
  id: string;
  name: string;
  firstname?: string;
  email: string;
  phone?: string;
  role: string;
  direction?: string;
  service?: string;
  avatar?: string;
  matricule?: string;
  job?: string;
  availability?: string;
  notif_sla_alerts: boolean;
  notif_escalations: boolean;
  notif_comments: boolean;
  notif_resolutions: boolean;
  account_status: string;
  direction_id?: string;
  department_id?: string;
  unit_id?: string;
};

export type PaginatedAccounts = {
  items: AccountUser[];
  total: number;
  page: number;
  pages: number;
};

// ── Avatar URL helper ─────────────────────────────────────────────────────────

export const _BACKEND_ORIGIN =
  import.meta.env.VITE_API_URL?.replace("/api/v1", "") ??
  (import.meta.env.DEV ? "http://localhost:8000" : "");

export function buildAvatarUrl(avatarPath: string | undefined): string | undefined {
  if (!avatarPath) return undefined;
  if (avatarPath.startsWith("blob:") || avatarPath.startsWith("http")) return avatarPath;
  return `${_BACKEND_ORIGIN}${avatarPath}`;
}

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapAccount(raw: RawAccount): AccountUser {
  const role = normalizeRole(raw.role);
  const unitId = raw.unit_id != null
    ? String(raw.unit_id)
    : raw.unity_id != null
      ? String(raw.unity_id)
      : undefined;
  const directionId = raw.direction_id != null
    ? String(raw.direction_id)
    : role === "director"
      ? unitId
      : undefined;

  return {
    id: raw.id,
    name: raw.name,
    firstname: raw.firstname ?? undefined,
    email: raw.email,
    phone: raw.phone ?? undefined,
    role,
    avatar: raw.avatar_url ?? undefined,
    matricule: raw.matricule ?? undefined,
    job: raw.job ?? undefined,
    availability: raw.availability ?? undefined,
    notif_sla_alerts: raw.notif_sla_alerts,
    notif_escalations: raw.notif_escalations,
    notif_comments: raw.notif_comments,
    notif_resolutions: raw.notif_resolutions,
    account_status: raw.account_status,
    direction_id: directionId,
    department_id: raw.department_id != null ? String(raw.department_id) : undefined,
    unit_id: unitId,
  };
}

// ── Fonctions ─────────────────────────────────────────────────────────────────

export async function fetchUsers(params?: {
  role?: string;
  search?: string;
  direction_id?: string;
  unit_id?: string;
  page?: number;
  limit?: number;
}): Promise<PaginatedAccounts> {
  const qs = new URLSearchParams();
  if (params?.role) qs.set("role", params.role);
  if (params?.search) qs.set("search", params.search);
  if (params?.direction_id) qs.set("direction_id", params.direction_id);
  if (params?.unit_id) qs.set("unit_id", params.unit_id);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawAccount[];
    total: number;
    page: number;
    pages: number;
  }>(`/users/?${qs}`);
  return { ...raw, items: raw.items.map(mapAccount) };
}

export async function fetchUser(id: string): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/${id}`);
  return mapAccount(raw);
}

export async function fetchMe(): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/me`);
  return mapAccount(raw);
}

export async function updateMe(
  data: Partial<{
    name: string;
    firstname: string;
    phone: string;
    avatar_url: string;
    job: string;
    matricule: string;
    notif_sla_alerts: boolean;
    notif_escalations: boolean;
    notif_comments: boolean;
    notif_resolutions: boolean;
  }>,
): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/me`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapAccount(raw);
}

export async function uploadAvatar(file: File): Promise<AccountUser> {
  const form = new FormData();
  form.append("file", file);
  const raw = await apiFetch<RawAccount>(`/users/me/avatar`, {
    method: "POST",
    body: form,
    skipContentType: true,
  });
  return mapAccount(raw);
}

export async function deleteAvatar(): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/me/avatar`, { method: "DELETE" });
  return mapAccount(raw);
}

export async function setMyAvailability(availability: string): Promise<AccountUser> {
  const qs = new URLSearchParams({ availability });
  const raw = await apiFetch<RawAccount>(`/users/me/availability?${qs}`, {
    method: "PATCH",
  });
  return mapAccount(raw);
}

export async function updateUser(
  id: string,
  data: Partial<{
    name: string;
    firstname: string;
    job: string;
    matricule: string;
    role: string;
    direction_id: string;
    department_id: string;
    unit_id: string;
    account_status: string;
    availability: string;
  }>,
): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapAccount(raw);
}

export async function setUserRole(
  id: string,
  role: string,
): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/${id}/role`, {
    method: "PATCH",
    body: JSON.stringify({ role }),
  });
  return mapAccount(raw);
}

export async function createUser(data: {
  name: string;
  firstname?: string;
  email: string;
  role?: string;
  matricule?: string;
  job?: string;
  direction_id?: string;
  department_id?: string;
  unit_id?: string;
  is_edg_employee?: boolean;
}): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>(`/users/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapAccount(raw);
}

export async function activateUser(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/users/${id}/activate`, { method: "POST", body: "{}" });
}

export async function deactivateUser(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/users/${id}/deactivate`, { method: "POST", body: "{}" });
}

export async function resetUserPassword(id: string, newPassword: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/users/${id}/reset-password`, {
    method: "POST",
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export async function deleteUser(id: string): Promise<void> {
  await apiFetch<void>(`/users/${id}`, { method: "DELETE" });
}

export async function checkMatricule(matricule: string): Promise<boolean> {
  const res = await apiFetch<{ matricule?: boolean }>(`/accounts/check-duplicate?matricule=${encodeURIComponent(matricule)}`);
  return res.matricule === true;
}
