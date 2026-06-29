/**
 * Module API — Rapports EDG Support.
 * Fonctions JSON + téléchargement binaire (CSV / Excel / PDF).
 */

import { apiFetch } from "./client";

const API_BASE =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "http://localhost:8000/api/v1" : "/api/v1");

// ── Types ──────────────────────────────────────────────────────────────────────

export type AgentReportRow = {
  agent_name: string;
  unity_label: string;
  assigned_total: number;
  resolved_total: number;
  escalated_total: number;
  avg_resolution_hours: number;
  resolution_rate: number;
};

export type DailyReport = {
  date: string;
  summary: {
    total_created: number;
    total_resolved: number;
    sla_breached: number;
  };
  by_category: Array<{ category: string; total: number }>;
};

export type MonthlyReport = {
  year: number;
  month: number;
  summary: {
    total_created: number;
    resolution_rate: number;
    sla_compliance_rate: number;
  };
  daily_evolution: Array<{ day: string; created: number; resolved: number }>;
};

export type UnityReportRow = {
  unity_id: string;
  unity_label: string;
  assigned_total: number;
  resolved_total: number;
  pending_total: number;
  escalated_total: number;
  avg_resolution_hours: number;
  resolution_rate: number;
};

export type ExportReportType = "daily" | "monthly" | "by-agent" | "by-unity" | "sla" | "csat";
export type ExportFormat = "csv" | "excel" | "pdf";

// ── Lectures JSON ─────────────────────────────────────────────────────────────

export async function fetchDailyReport(date?: string): Promise<DailyReport> {
  const qs = date ? `?date=${date}` : "";
  return apiFetch<DailyReport>(`/reports/daily${qs}`);
}

export async function fetchMonthlyReport(year?: number, month?: number): Promise<MonthlyReport> {
  const params = new URLSearchParams();
  if (year) params.set("year", String(year));
  if (month) params.set("month", String(month));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<MonthlyReport>(`/reports/monthly${qs}`);
}

export async function fetchAgentReport(
  start?: string,
  end?: string,
  unity_id?: number,
): Promise<AgentReportRow[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  if (unity_id) params.set("unity_id", String(unity_id));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<AgentReportRow[]>(`/reports/by-agent${qs}`);
}

export async function fetchUnityReport(
  start?: string,
  end?: string,
): Promise<UnityReportRow[]> {
  const params = new URLSearchParams();
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch<UnityReportRow[]>(`/reports/by-unity${qs}`);
}

// ── Export binaire (déclenche un téléchargement navigateur) ───────────────────

export async function downloadReport(
  type: ExportReportType,
  format: ExportFormat,
  params: Record<string, string> = {},
): Promise<void> {
  const { getAccessToken } = await import("../session");
  const token = getAccessToken();
  const qs = new URLSearchParams({ format, ...params });
  const url = `${API_BASE}/reports/${type}/export?${qs.toString()}`;

  const res = await fetch(url, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });

  if (!res.ok) {
    throw new Error(`Erreur export ${type} (${res.status})`);
  }

  const blob = await res.blob();
  const ext = format === "csv" ? "csv" : format === "excel" ? "xlsx" : "pdf";
  const cd = res.headers.get("Content-Disposition");
  const filename =
    cd?.match(/filename="?([^";\r\n]+)"?/)?.[1] ??
    `rapport_${type}_${new Date().toISOString().slice(0, 10)}.${ext}`;

  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objUrl);
}
