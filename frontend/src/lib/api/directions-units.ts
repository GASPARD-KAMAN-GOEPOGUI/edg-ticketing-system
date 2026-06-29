/**
 * Module API — Directions & Unités/Services
 * Endpoints : /directions/*, /units/*
 */
import { apiFetch } from "./client";

// ── Types ─────────────────────────────────────────────────────────────────────

export type Direction = {
  id: string;
  name: string;
  code?: string;
  description?: string;
  status: boolean;
  parent_direction_id?: string;
};

export type Unit = {
  id: string;
  name: string;
  code?: string;
  direction_id?: string;
  description?: string;
  status: boolean;
};

type RawDirection = {
  id: string;
  name: string;
  code?: string | null;
  description?: string | null;
  status: boolean;
  parent_direction_id?: string | null;
};

type RawUnit = {
  id: string;
  name: string;
  code?: string | null;
  direction_id?: string | null;
  description?: string | null;
  status: boolean;
};

// ── Compteur public ───────────────────────────────────────────────────────────

export async function fetchActiveDirectionsCount(): Promise<number> {
  const res = await apiFetch<{ count: number }>("/public/directions/count", { skipAuth: true });
  return res.count;
}

// ── Directions ────────────────────────────────────────────────────────────────

export async function fetchDirections(): Promise<Direction[]> {
  const res = await apiFetch<{ items: RawDirection[] }>("/directions/?limit=200");
  return res.items.map((d) => ({
    id: String(d.id),
    name: d.name,
    code: d.code ?? undefined,
    description: d.description ?? undefined,
    status: d.status,
    parent_direction_id: d.parent_direction_id ?? undefined,
  }));
}

export async function createDirection(data: {
  name: string;
  code?: string;
  description?: string;
  parent_direction_id?: string;
}): Promise<Direction> {
  const raw = await apiFetch<RawDirection>("/directions/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return { id: raw.id, name: raw.name, code: raw.code ?? undefined, description: raw.description ?? undefined, status: raw.status, parent_direction_id: raw.parent_direction_id ?? undefined };
}

export async function updateDirection(
  id: string,
  data: { name?: string; code?: string; description?: string; status?: boolean; parent_direction_id?: string | null },
): Promise<Direction> {
  const raw = await apiFetch<RawDirection>(`/directions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return { id: raw.id, name: raw.name, code: raw.code ?? undefined, description: raw.description ?? undefined, status: raw.status, parent_direction_id: raw.parent_direction_id ?? undefined };
}

export async function deleteDirection(id: string): Promise<void> {
  await apiFetch<void>(`/directions/${id}`, { method: "DELETE" });
}

// ── Units ─────────────────────────────────────────────────────────────────────

export async function fetchUnits(directionId?: string): Promise<Unit[]> {
  const url = directionId
    ? `/units/by-direction/${directionId}?limit=200`
    : "/units?limit=200";
  const res = await apiFetch<{ items: RawUnit[] }>(url);
  return res.items.map((u) => ({
    id: String(u.id),
    name: u.name,
    code: u.code ?? undefined,
    direction_id: u.direction_id != null ? String(u.direction_id) : undefined,
    description: u.description ?? undefined,
    status: u.status,
  }));
}

export async function createUnit(data: {
  name: string;
  direction_id?: string;
  code?: string;
  description?: string;
}): Promise<Unit> {
  const raw = await apiFetch<RawUnit>("/units/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return { id: raw.id, name: raw.name, code: raw.code ?? undefined, direction_id: raw.direction_id ?? undefined, description: raw.description ?? undefined, status: raw.status };
}

export async function updateUnit(
  id: string,
  data: { name?: string; code?: string; direction_id?: string; description?: string; status?: boolean },
): Promise<Unit> {
  const raw = await apiFetch<RawUnit>(`/units/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return { id: raw.id, name: raw.name, code: raw.code ?? undefined, direction_id: raw.direction_id ?? undefined, description: raw.description ?? undefined, status: raw.status };
}

export async function deleteUnit(id: string): Promise<void> {
  await apiFetch<void>(`/units/${id}`, { method: "DELETE" });
}
