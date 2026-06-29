/**
 * Guards de route centralisés — EDG Support.
 *
 * À utiliser dans beforeLoad de chaque route TanStack Router.
 *
 * Règles :
 *  - Utilisateur non authentifié → redirect /login
 *  - Utilisateur authentifié mais rôle insuffisant → redirect vers son espace par défaut
 */
import { redirect } from "@tanstack/react-router";
import {
  AUTH_DISABLED,
  isAuthenticated,
  getRole,
  getDefaultRouteForRole,
} from "./session";
import type { Role } from "./mock-data";

/**
 * Exige uniquement que l'utilisateur soit authentifié.
 * Aucune contrainte de rôle.
 */
export function requireAuth(): void {
  if (AUTH_DISABLED) return;
  if (!isAuthenticated()) {
    throw redirect({ to: "/login" });
  }
}

/**
 * Exige que l'utilisateur soit authentifié ET ait l'un des rôles listés.
 * Redirect vers /login si non authentifié.
 * Redirect vers l'espace par défaut du rôle si rôle insuffisant.
 */
export function requireRole(...roles: Role[]): void {
  if (AUTH_DISABLED) return;
  if (!isAuthenticated()) {
    throw redirect({ to: "/login" });
  }
  const role = getRole();
  if (!roles.includes(role)) {
    throw redirect({ to: getDefaultRouteForRole(role) as "/" });
  }
}

/**
 * Exige que l'utilisateur soit authentifié ET ait exactement le rôle admin.
 */
export function requireAdmin(): void {
  requireRole("admin");
}
