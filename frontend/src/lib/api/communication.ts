/**
 * Module API — Communication institutionnelle
 * Endpoints : /announcements/*, /communication-settings
 */
import { apiFetch } from "./client";
import type {
  Announcement,
  AnnouncementCategory,
  AnnouncementChannel,
  AnnouncementPriority,
  AnnouncementStatus,
  AnnouncementAudience,
  CommunicationSettings,
} from "@/lib/mock-data";
import type { Role } from "@/lib/mock-data";
import { normalizeRole } from "../session";

// ── Types bruts backend ───────────────────────────────────────────────────────

type _RawChannelItem = { channel: string };
type _RawTargetRoleItem = { role: string };
type _RawTargetDirectionItem = { direction_id: string };
type _RawMetricItem = {
  emails_sent: number;
  sms_sent: number;
  notifications_sent: number;
  view_count: number;
  consultation_rate: number;
};

export type RawAnnouncement = {
  id: string;
  title: string;
  description: string;
  announcement_category: string;
  announcement_priority: string;
  announcement_status: string;
  audience: string;
  published_at: string;
  expires_at?: string | null;
  attachment_name?: string | null;
  author_id: string;
  closed_at?: string | null;
  channels: _RawChannelItem[];
  target_roles: _RawTargetRoleItem[];
  target_directions: _RawTargetDirectionItem[];
  metric?: _RawMetricItem | null;
  created_at: string;
  updated_at: string;
};

export type PaginatedAnnouncements = {
  items: Announcement[];
  total: number;
  page: number;
  pages: number;
};

export type RawCommunicationSettings = {
  id: string;
  internal_notif_on: boolean;
  email_on: boolean;
  sms_on: boolean;
  banner_on: boolean;
  whatsapp_on: boolean;
  push_mobile_on: boolean;
  sender_email: string;
  sender_sms: string;
  reply_to: string;
};

// ── Mappers ───────────────────────────────────────────────────────────────────

export function mapAnnouncement(raw: RawAnnouncement): Announcement {
  const metric = raw.metric;
  const targetRoles = Array.from(
    new Set((raw.target_roles ?? []).map((r) => normalizeRole(r.role))),
  ) as Role[];
  return {
    id: raw.id,
    title: raw.title,
    description: raw.description,
    category: raw.announcement_category as AnnouncementCategory,
    priority: raw.announcement_priority as AnnouncementPriority,
    status: raw.announcement_status as AnnouncementStatus,
    publishedAt: raw.published_at,
    expiresAt: raw.expires_at ?? undefined,
    attachmentName: raw.attachment_name ?? undefined,
    targets: {
      audience: raw.audience as AnnouncementAudience,
      roles: targetRoles,
      directions: (raw.target_directions ?? []).map((d) => d.direction_id),
      services: [],
    },
    channels: (raw.channels ?? []).map((c) => c.channel as AnnouncementChannel),
    authorId: raw.author_id,
    authorName: raw.author_id,
    metrics: metric
      ? {
          emailsSent: metric.emails_sent,
          smsSent: metric.sms_sent,
          notificationsSent: metric.notifications_sent,
          viewCount: metric.view_count,
          consultationRate: Number(metric.consultation_rate),
        }
      : { emailsSent: 0, smsSent: 0, notificationsSent: 0, viewCount: 0, consultationRate: 0 },
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
    closedAt: raw.closed_at ?? undefined,
  };
}

export function mapSettings(raw: RawCommunicationSettings): CommunicationSettings {
  return {
    channels: {
      internal_notif: raw.internal_notif_on,
      email: raw.email_on,
      sms: raw.sms_on,
      banner: raw.banner_on,
      whatsapp: raw.whatsapp_on,
      push_mobile: raw.push_mobile_on,
    },
    senderEmail: raw.sender_email,
    senderSms: raw.sender_sms,
    replyTo: raw.reply_to,
  };
}

// ── Announcements ─────────────────────────────────────────────────────────────

export async function fetchAnnouncements(params?: {
  page?: number;
  limit?: number;
}): Promise<PaginatedAnnouncements> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawAnnouncement[];
    total: number;
    page: number;
    pages: number;
  }>(`/announcements?${qs}`);
  return { ...raw, items: raw.items.map(mapAnnouncement) };
}

export async function fetchAnnouncement(id: string): Promise<Announcement> {
  const raw = await apiFetch<RawAnnouncement>(`/announcements/${id}`);
  return mapAnnouncement(raw);
}

export type CreateAnnouncementPayload = {
  title: string;
  description: string;
  announcement_category: string;
  announcement_priority: string;
  announcement_status: string;
  audience: string;
  author_id: string;
  expires_at?: string | null;
  channel_names: string[];
  role_names: string[];
  direction_ids: string[];
};

export async function createAnnouncement(
  payload: CreateAnnouncementPayload,
): Promise<Announcement> {
  const raw = await apiFetch<RawAnnouncement>("/announcements", {
    method: "POST",
    body: JSON.stringify(payload),
  });
  return mapAnnouncement(raw);
}

export type UpdateAnnouncementPayload = Partial<{
  title: string;
  description: string;
  announcement_category: string;
  announcement_priority: string;
  announcement_status: string;
  audience: string;
  expires_at: string | null;
  channel_names: string[];
  role_names: string[];
  direction_ids: string[];
}>;

export async function updateAnnouncement(
  id: string,
  payload: UpdateAnnouncementPayload,
): Promise<Announcement> {
  const raw = await apiFetch<RawAnnouncement>(`/announcements/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return mapAnnouncement(raw);
}

export async function publishAnnouncement(id: string): Promise<Announcement> {
  const raw = await apiFetch<RawAnnouncement>(`/announcements/${id}/publish`, {
    method: "POST",
  });
  return mapAnnouncement(raw);
}

export async function closeAnnouncement(id: string): Promise<Announcement> {
  const raw = await apiFetch<RawAnnouncement>(`/announcements/${id}/close`, {
    method: "POST",
  });
  return mapAnnouncement(raw);
}

export async function deleteAnnouncement(id: string): Promise<void> {
  await apiFetch<void>(`/announcements/${id}`, { method: "DELETE" });
}

/**
 * Retourne les annonces publiées et non expirées pour une audience donnée.
 * Utilise GET /announcements/active/{audience} qui inclut également les annonces "all".
 * Si audience omise, retombe sur GET /announcements/published.
 */
export async function fetchPublishedAnnouncements(params?: {
  audience?: string;
  limit?: number;
  page?: number;
}): Promise<PaginatedAnnouncements> {
  const qs = new URLSearchParams();
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const qstr = qs.toString() ? `?${qs.toString()}` : "";
  if (params?.audience) {
    const raw = await apiFetch<{
      items: RawAnnouncement[];
      total: number;
      page: number;
      pages: number;
    }>(`/announcements/active/${encodeURIComponent(params.audience)}${qstr}`);
    return { ...raw, items: raw.items.map(mapAnnouncement) };
  }
  const raw = await apiFetch<{
    items: RawAnnouncement[];
    total: number;
    page: number;
    pages: number;
  }>(`/announcements/published${qstr}`);
  return { ...raw, items: raw.items.map(mapAnnouncement) };
}

/** Mappe un rôle utilisateur vers l'audience d'annonce correspondante. */
export function roleToAnnounceAudience(role: Role): string {
  return role === "user" ? "external" : "internal";
}

export async function fetchActiveAlerts(): Promise<Announcement[]> {
  const raw = await apiFetch<{
    items: RawAnnouncement[];
    total: number;
    page: number;
    pages: number;
  }>("/announcements/active-alerts");
  return raw.items.map(mapAnnouncement);
}

// ── Communication settings ────────────────────────────────────────────────────

export async function fetchCommSettings(): Promise<CommunicationSettings> {
  const raw = await apiFetch<RawCommunicationSettings>("/communication-settings");
  return mapSettings(raw);
}

export type UpdateSettingsPayload = Partial<{
  internal_notif_on: boolean;
  email_on: boolean;
  sms_on: boolean;
  banner_on: boolean;
  whatsapp_on: boolean;
  push_mobile_on: boolean;
  sender_email: string;
  sender_sms: string;
  reply_to: string;
}>;

export async function updateCommSettings(
  payload: UpdateSettingsPayload,
): Promise<CommunicationSettings> {
  const raw = await apiFetch<RawCommunicationSettings>("/communication-settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return mapSettings(raw);
}
