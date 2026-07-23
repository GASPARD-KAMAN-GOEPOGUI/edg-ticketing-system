/**
 * Module API - Directions, Departements & Unites/Services
 * Endpoints : /directions/*, /departments/*, /units/*
 */
import { apiFetch } from "./client";

// -- Types --------------------------------------------------------------------

export type OrgStatusFilter = "all" | "active" | "inactive";

export type Direction = {
  id: string;
  name: string;
  code?: string;
  description?: string;
  status: boolean;
  parent_direction_id?: string;
  active_children_count?: number;
  type?: "direction";
};

export type Department = {
  id: string;
  name: string;
  code?: string;
  direction_id?: string;
  direction_name?: string;
  description?: string;
  status: boolean;
  active_children_count?: number;
  type?: "department";
};

export type Unit = {
  id: string;
  name: string;
  code?: string;
  direction_id?: string;
  direction_name?: string;
  department_id?: string;
  department_name?: string;
  description?: string;
  status: boolean;
  active_children_count?: number;
  type?: "unit";
};

type RawDirection = {
  id: string;
  name: string;
  code?: string | null;
  description?: string | null;
  status: boolean;
  parent_direction_id?: string | null;
  active_children_count?: number | null;
  type?: "direction";
};

type RawDepartment = {
  id: string;
  name: string;
  code?: string | null;
  direction_id?: string | null;
  direction_name?: string | null;
  description?: string | null;
  status: boolean;
  active_children_count?: number | null;
  type?: "department";
};

type RawUnit = {
  id: string;
  name: string;
  code?: string | null;
  direction_id?: string | null;
  direction_name?: string | null;
  department_id?: string | null;
  department_name?: string | null;
  description?: string | null;
  status: boolean;
  active_children_count?: number | null;
  type?: "unit";
};

function statusParam(status?: OrgStatusFilter): string {
  return status && status !== "all" ? `&status=${status}` : "";
}

function mapDirection(d: RawDirection): Direction {
  return {
    id: String(d.id),
    name: d.name,
    code: d.code ?? undefined,
    description: d.description ?? undefined,
    status: d.status,
    parent_direction_id: d.parent_direction_id ?? undefined,
    active_children_count: d.active_children_count ?? 0,
    type: "direction",
  };
}

function mapDepartment(d: RawDepartment): Department {
  return {
    id: String(d.id),
    name: d.name,
    code: d.code ?? undefined,
    direction_id: d.direction_id != null ? String(d.direction_id) : undefined,
    direction_name: d.direction_name ?? undefined,
    description: d.description ?? undefined,
    status: d.status,
    active_children_count: d.active_children_count ?? 0,
    type: "department",
  };
}

function mapUnit(u: RawUnit): Unit {
  return {
    id: String(u.id),
    name: u.name,
    code: u.code ?? undefined,
    direction_id: u.direction_id != null ? String(u.direction_id) : undefined,
    direction_name: u.direction_name ?? undefined,
    department_id: u.department_id != null ? String(u.department_id) : undefined,
    department_name: u.department_name ?? undefined,
    description: u.description ?? undefined,
    status: u.status,
    active_children_count: u.active_children_count ?? 0,
    type: "unit",
  };
}

// -- Compteur public ----------------------------------------------------------

export async function fetchActiveDirectionsCount(): Promise<number> {
  const res = await apiFetch<{ count: number }>("/public/directions/count", { skipAuth: true });
  return res.count;
}

// -- Directions ---------------------------------------------------------------

export async function fetchDirections(options?: { status?: OrgStatusFilter }): Promise<Direction[]> {
  const res = await apiFetch<{ items: RawDirection[] }>(
    `/directions/?limit=200${statusParam(options?.status)}`,
  );
  return res.items.map(mapDirection);
}

export async function fetchDirection(id: string): Promise<Direction> {
  return mapDirection(await apiFetch<RawDirection>(`/directions/${id}`));
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
  return mapDirection(raw);
}

export async function updateDirection(
  id: string,
  data: {
    name?: string;
    code?: string;
    description?: string;
    status?: boolean;
    parent_direction_id?: string | null;
  },
): Promise<Direction> {
  const raw = await apiFetch<RawDirection>(`/directions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapDirection(raw);
}

export async function deactivateDirection(id: string, force = false): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/directions/${id}/deactivate?force=${force ? "true" : "false"}`, {
    method: "POST",
    body: "{}",
  });
}

export async function activateDirection(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/directions/${id}/activate`, {
    method: "POST",
    body: "{}",
  });
}

export async function deleteDirection(id: string, force = false): Promise<void> {
  await deactivateDirection(id, force);
}

// -- Departements -------------------------------------------------------------

export async function fetchDepartments(options?: {
  directionId?: string;
  status?: OrgStatusFilter;
}): Promise<Department[]> {
  const byDirection = options?.directionId
    ? `/departments/by-direction/${options.directionId}?limit=200${statusParam(options.status)}`
    : `/departments/?limit=200${statusParam(options?.status)}`;
  const res = await apiFetch<{ items: RawDepartment[] }>(byDirection);
  return res.items.map(mapDepartment);
}

export async function fetchDepartment(id: string): Promise<Department> {
  return mapDepartment(await apiFetch<RawDepartment>(`/departments/${id}`));
}

export async function createDepartment(data: {
  name: string;
  direction_id: string;
  code?: string;
  description?: string;
}): Promise<Department> {
  const raw = await apiFetch<RawDepartment>("/departments/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapDepartment(raw);
}

export async function updateDepartment(
  id: string,
  data: { name?: string; code?: string; direction_id?: string; description?: string; status?: boolean },
): Promise<Department> {
  const raw = await apiFetch<RawDepartment>(`/departments/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapDepartment(raw);
}

export async function deactivateDepartment(id: string, force = false): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/departments/${id}/deactivate?force=${force ? "true" : "false"}`, {
    method: "POST",
    body: "{}",
  });
}

export async function activateDepartment(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/departments/${id}/activate`, {
    method: "POST",
    body: "{}",
  });
}

export async function deleteDepartment(id: string, force = false): Promise<void> {
  await deactivateDepartment(id, force);
}

// -- Units --------------------------------------------------------------------

export async function fetchUnits(options?: {
  directionId?: string;
  departmentId?: string;
  status?: OrgStatusFilter;
} | string): Promise<Unit[]> {
  const normalized = typeof options === "string" ? { directionId: options } : options;
  let url = `/units/?limit=200${statusParam(normalized?.status)}`;
  if (normalized?.departmentId) {
    url = `/units/by-department/${normalized.departmentId}?limit=200${statusParam(normalized.status)}`;
  } else if (normalized?.directionId) {
    url = `/units/by-direction/${normalized.directionId}?limit=200${statusParam(normalized.status)}`;
  }
  const res = await apiFetch<{ items: RawUnit[] }>(url);
  return res.items.map(mapUnit);
}

export async function fetchUnit(id: string): Promise<Unit> {
  return mapUnit(await apiFetch<RawUnit>(`/units/${id}`));
}

export async function createUnit(data: {
  name: string;
  department_id: string;
  code?: string;
  description?: string;
}): Promise<Unit> {
  const raw = await apiFetch<RawUnit>("/units/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapUnit(raw);
}

export async function updateUnit(
  id: string,
  data: { name?: string; code?: string; department_id?: string; description?: string; status?: boolean },
): Promise<Unit> {
  const raw = await apiFetch<RawUnit>(`/units/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapUnit(raw);
}

export async function deactivateUnit(id: string, force = false): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/units/${id}/deactivate?force=${force ? "true" : "false"}`, {
    method: "POST",
    body: "{}",
  });
}

export async function activateUnit(id: string): Promise<void> {
  await apiFetch<{ ok: boolean }>(`/units/${id}/activate`, {
    method: "POST",
    body: "{}",
  });
}

export async function deleteUnit(id: string, force = false): Promise<void> {
  await deactivateUnit(id, force);
}
