/**
 * Utilitaire d'export — XLSX et CSV
 * Génère les fichiers côté client depuis les données chargées.
 */
import * as XLSX from "xlsx";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import type { RequestItem } from "@/lib/mock-data";
import { statusLabels, priorityLabels } from "@/lib/mock-data";

// ── Colonnes export ────────────────────────────────────────────────────────────

function toRow(r: RequestItem, directionMap: Map<string, string>) {
  const slaOk = r.slaHours > 0 ? (r.slaElapsed <= r.slaHours ? "Oui" : "Non") : "—";
  const dateClosed = r.updatedAt && r.updatedAt !== r.createdAt
    ? format(new Date(r.updatedAt), "dd/MM/yyyy HH:mm", { locale: fr })
    : "—";
  return {
    "Référence":          r.ref,
    "Date création":      format(new Date(r.createdAt), "dd/MM/yyyy HH:mm", { locale: fr }),
    "Titre":              r.title,
    "Catégorie":          r.category,
    "Priorité":           priorityLabels[r.priority] ?? r.priority,
    "Statut":             statusLabels[r.status as keyof typeof statusLabels] ?? r.status,
    "Requérant":          r.requesterName,
    "Direction":          (r.directionId ? directionMap.get(String(r.directionId)) : undefined) ?? "—",
    "Agent assigné":      r.assigneeName ?? "—",
    "Date résolution":    dateClosed,
    "SLA respecté":       slaOk,
    "Note CSAT":          r.appreciation?.rating != null ? String(r.appreciation.rating) : "—",
  };
}

function buildFilename(prefix: string, ext: string, dateFrom?: string, dateTo?: string): string {
  const today = format(new Date(), "yyyy-MM-dd");
  if (dateFrom && dateTo) return `${prefix}_${dateFrom}_au_${dateTo}.${ext}`;
  if (dateFrom) return `${prefix}_depuis_${dateFrom}.${ext}`;
  if (dateTo) return `${prefix}_jusqu_au_${dateTo}.${ext}`;
  return `${prefix}_${today}.${ext}`;
}

// ── Export XLSX ────────────────────────────────────────────────────────────────

export function exportXLSX(
  items: RequestItem[],
  directionMap: Map<string, string>,
  options?: { dateFrom?: string; dateTo?: string; sheetName?: string },
) {
  const rows = items.map((r) => toRow(r, directionMap));
  const ws = XLSX.utils.json_to_sheet(rows);

  // Largeurs de colonnes
  ws["!cols"] = [
    { wch: 16 }, // Référence
    { wch: 18 }, // Date création
    { wch: 40 }, // Titre
    { wch: 20 }, // Catégorie
    { wch: 10 }, // Priorité
    { wch: 14 }, // Statut
    { wch: 24 }, // Requérant
    { wch: 22 }, // Direction
    { wch: 16 }, // Agent assigné
    { wch: 18 }, // Date résolution
    { wch: 12 }, // SLA respecté
    { wch: 10 }, // Note CSAT
  ];

  const wb = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(wb, ws, options?.sheetName ?? "Tickets EDG");
  const filename = buildFilename("tickets_edg", "xlsx", options?.dateFrom, options?.dateTo);
  XLSX.writeFile(wb, filename);
}

// ── Export CSV ─────────────────────────────────────────────────────────────────

export function exportCSV(
  items: RequestItem[],
  directionMap: Map<string, string>,
  options?: { dateFrom?: string; dateTo?: string },
) {
  const rows = items.map((r) => toRow(r, directionMap));
  const ws = XLSX.utils.json_to_sheet(rows);
  const csv = XLSX.utils.sheet_to_csv(ws, { FS: ";" });
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = buildFilename("tickets_edg", "csv", options?.dateFrom, options?.dateTo);
  a.click();
  URL.revokeObjectURL(url);
}
