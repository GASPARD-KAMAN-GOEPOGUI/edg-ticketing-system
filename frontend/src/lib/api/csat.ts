/**
 * Module API — CSAT / Appréciation
 * Endpoints : /requests/:id/appreciation, /stats/csat*
 */
import { apiFetch } from "./client";
import type { Appreciation } from "@/lib/mock-data";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawAppreciation = {
  id: string;
  request_id: string;
  rating: number;
  comment?: string | null;
  resolved_confirmed: boolean;
  is_modified: boolean;
  author_type: "internal" | "external";
  created_at: string;
  updated_at: string;
};

export type CsatGlobal = {
  global: number;
  count: number;
  internal: number;
  external: number;
  distribution: Record<string, number>;
};

export type CsatByEntity = {
  entity_id: string;
  label: string;
  avg: number;
  count: number;
  internal: number;
  external: number;
};

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapAppreciation(raw: RawAppreciation): Appreciation {
  return {
    rating: raw.rating as 1 | 2 | 3 | 4 | 5,
    comment: raw.comment ?? undefined,
    resolvedConfirmed: raw.resolved_confirmed,
    authorType: raw.author_type,
    at: raw.created_at,
  };
}

// ── Appreciation par demande ──────────────────────────────────────────────────

export async function fetchRequestAppreciation(requestId: string): Promise<Appreciation | null> {
  const raw = await apiFetch<RawAppreciation | null>(`/requests/${requestId}/appreciation`);
  if (!raw) return null;
  return mapAppreciation(raw);
}

export async function submitAppreciation(
  requestId: string,
  data: {
    rating: number;
    comment?: string;
    resolvedConfirmed: boolean;
    authorType: "internal" | "external";
  },
): Promise<Appreciation> {
  const raw = await apiFetch<RawAppreciation>(`/requests/${requestId}/appreciation`, {
    method: "POST",
    body: JSON.stringify({
      rating: data.rating,
      comment: data.comment ?? null,
      resolved_confirmed: data.resolvedConfirmed,
      author_type: data.authorType,
    }),
  });
  return mapAppreciation(raw);
}

export async function updateRequestAppreciation(
  requestId: string,
  data: { rating?: number; comment?: string; resolvedConfirmed?: boolean },
): Promise<Appreciation> {
  const payload: Record<string, unknown> = {};
  if (data.rating !== undefined) payload.rating = data.rating;
  if (data.comment !== undefined) payload.comment = data.comment ?? null;
  if (data.resolvedConfirmed !== undefined) payload.resolved_confirmed = data.resolvedConfirmed;
  const raw = await apiFetch<RawAppreciation>(`/requests/${requestId}/appreciation`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return mapAppreciation(raw);
}

// ── Stats CSAT ────────────────────────────────────────────────────────────────

export async function fetchCsatStats(): Promise<CsatGlobal> {
  return apiFetch<CsatGlobal>("/stats/csat");
}

export async function fetchCsatByAgent(): Promise<CsatByEntity[]> {
  return apiFetch<CsatByEntity[]>("/stats/csat/by-agent");
}

export async function fetchCsatByDirection(): Promise<CsatByEntity[]> {
  return apiFetch<CsatByEntity[]>("/stats/csat/by-direction");
}

export async function fetchCsatByCategory(): Promise<CsatByEntity[]> {
  return apiFetch<CsatByEntity[]>("/stats/csat/by-category");
}

export type CsatMonthlyPoint = {
  month: string;
  avg: number;
  count: number;
};

export async function fetchCsatMonthly(months = 12): Promise<CsatMonthlyPoint[]> {
  return apiFetch<CsatMonthlyPoint[]>(`/stats/csat/monthly?months=${months}`);
}
