import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function initialsFor(value?: string): string {
  if (!value?.trim()) return "??";
  return value
    .trim()
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

// Durée de traitement écoulée, affichée seule — volontairement sans comparaison
// à une limite SLA (indicateur SLA désactivé temporairement à la demande du
// métier, cf. session 2026-08-10).
export function formatElapsedHours(hours?: number): string {
  if (hours == null || hours < 0) return "—";
  const totalMinutes = Math.round(hours * 60);
  const days = Math.floor(totalMinutes / 1440);
  const remHours = Math.floor((totalMinutes % 1440) / 60);
  if (days > 0) return remHours > 0 ? `${days} j ${remHours} h` : `${days} j`;
  if (remHours > 0) return `${remHours} h`;
  return `${totalMinutes} min`;
}
