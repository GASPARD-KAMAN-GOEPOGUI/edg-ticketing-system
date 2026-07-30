/**
 * Module API — Notifications
 * Endpoints : /notifications/*, /notifications/read-all
 */
import { apiFetch } from "./client";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawNotification = {
  id: string | number;
  recipient_id: string | number;
  type: "info" | "success" | "warning";
  channel: string;
  title: string;
  body: string;
  request_id?: number | string | null;
  action_label?: string | null;
  action_url?: string | null;
  is_read: boolean;
  read_at?: string | null;
  status: boolean;
  created_at: string;
  updated_at: string;
};

export type NotifItem = {
  id: string;
  type: "info" | "success" | "warning";
  title: string;
  body: string;
  at: string;
  read: boolean;
  requestId?: string;
  actionUrl?: string;
  source: "request" | "announcement";
};

export type PaginatedNotifications = {
  items: NotifItem[];
  total: number;
  page: number;
  pages: number;
};

// ── Formatter de date relative ────────────────────────────────────────────────

function formatRelativeTime(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const min = Math.floor(diff / 60_000);
  if (min < 1) return "à l'instant";
  if (min < 60) return `il y a ${min} min`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `il y a ${hours}h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "hier";
  if (days < 7) return `il y a ${days}j`;
  return new Date(isoString).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "short",
  });
}

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapNotification(raw: RawNotification): NotifItem {
  const requestId = raw.request_id != null ? String(raw.request_id) : undefined;
  return {
    id: String(raw.id),
    type: raw.type,
    title: raw.title,
    body: raw.body,
    at: formatRelativeTime(raw.created_at),
    read: raw.is_read,
    requestId,
    actionUrl: raw.action_url ?? undefined,
    source: requestId ? "request" : "announcement",
  };
}

// ── Fonctions ─────────────────────────────────────────────────────────────────

export async function fetchNotifications(params?: {
  meId?: string;
  unread?: boolean;
  nature?: "annonce" | "demande";
  archived?: boolean;
  page?: number;
  limit?: number;
}): Promise<PaginatedNotifications> {
  const qs = new URLSearchParams();
  if (params?.meId) qs.set("me_id", params.meId);
  if (params?.unread) qs.set("unread", "true");
  if (params?.nature) qs.set("nature", params.nature);
  if (params?.archived) qs.set("archived", "true");
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawNotification[];
    total: number;
    page: number;
    pages: number;
  }>(`/notifications?${qs}`);
  return { ...raw, items: raw.items.map(mapNotification) };
}

export async function markNotificationRead(id: string): Promise<NotifItem> {
  const raw = await apiFetch<RawNotification>(`/notifications/${id}/read`, {
    method: "PATCH",
  });
  return mapNotification(raw);
}

export async function markAllNotificationsRead(meId?: string): Promise<{ updated: number }> {
  const qs = meId ? `?me_id=${encodeURIComponent(meId)}` : "";
  return apiFetch<{ updated: number }>(`/notifications/read-all${qs}`, {
    method: "POST",
  });
}

export async function deleteNotification(id: string): Promise<void> {
  await apiFetch<void>(`/notifications/${id}`, { method: "DELETE" });
}

export async function restoreNotification(id: string): Promise<NotifItem> {
  const raw = await apiFetch<RawNotification>(`/notifications/${id}/restore`, {
    method: "POST",
  });
  return mapNotification(raw);
}
