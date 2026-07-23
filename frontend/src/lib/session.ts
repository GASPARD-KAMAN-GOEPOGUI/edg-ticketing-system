import { useEffect, useState } from "react";
import type { Role } from "./mock-data";
import { roleLabels } from "./mock-data";

export const AUTH_DISABLED = import.meta.env.DEV && import.meta.env.VITE_DISABLE_AUTH === "true";

const _DEV_USER: SessionUser = {
  id: "1",
  name: "Admin EDG",
  firstname: "Admin",
  email: "gaspardKamangoepogui@gmail.com",
  role: "admin",
};

// ── Clés de stockage ──────────────────────────────────────────────────────────

const ROLE_KEY          = "edg.session.role";
const USER_KEY          = "edg.session.user";
const ACCESS_TOKEN_KEY  = "edg.auth.access_token";
const REFRESH_TOKEN_KEY = "edg.auth.refresh_token";
const TOKEN_EXP_KEY     = "edg.auth.expires_at";   // timestamp ms

// ── Types ─────────────────────────────────────────────────────────────────────

type RoleListener = (role: Role) => void;
type UserListener = (user: SessionUser | null) => void;

export type SessionUser = {
  id: string;
  name: string;
  firstname?: string;
  email: string;
  role: Role;
  phone?: string;
  avatar?: string;
  direction_id?: string;
  unit_id?: string;
};

export function normalizeRole(role: string | null | undefined): Role {
  const value = String(role ?? "user").trim().toLowerCase();
  if (value === "dg") return "director";
  if (["public", "user", "agent", "chief", "director", "admin"].includes(value)) {
    return value as Role;
  }
  return "user";
}

// ── Bus d'événements interne ──────────────────────────────────────────────────

const roleListeners = new Set<RoleListener>();
const userListeners = new Set<UserListener>();

// ── Rôle ─────────────────────────────────────────────────────────────────────

/** 4.1 — décode le claim "role" du JWT d'accès (source de vérité serveur). */
function decodeJwtRole(token: string): Role | null {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return normalizeRole(JSON.parse(json).role);
  } catch {
    return null;
  }
}

export function getRole(): Role {
  if (AUTH_DISABLED) return _DEV_USER.role;
  if (typeof window === "undefined") return "user";
  // Priorité : rôle décodé du JWT courant (plus frais après un refresh de token)
  const token = getAccessToken();
  if (token) {
    const jwtRole = decodeJwtRole(token);
    if (jwtRole) return jwtRole;
  }
  // Fallback : rôle du profil utilisateur stocké au login
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (raw) return normalizeRole((JSON.parse(raw) as SessionUser).role);
  } catch { /* donnée corrompue */ }
  return "user";
}

export function setRole(role: Role) {
  if (typeof window === "undefined") return;
  const nextRole = normalizeRole(role);
  // En prod, cette fonction n'a d'effet que via setUser() (login).
  // En dev (AUTH_DISABLED), elle permet de basculer de rôle librement.
  if (AUTH_DISABLED) localStorage.setItem(ROLE_KEY, nextRole);
  roleListeners.forEach((l) => l(nextRole));
}

export function useRole(): [Role, (r: Role) => void] {
  const [role, setLocal] = useState<Role>(getRole());
  useEffect(() => {
    setLocal(getRole());
    if (AUTH_DISABLED) {
      // Dev : écoute les changements manuels de rôle (RoleSwitcher)
      const l: RoleListener = (r) => setLocal(r);
      roleListeners.add(l);
      return () => { roleListeners.delete(l); };
    }
    // Prod : rôle dérivé du profil utilisateur — se met à jour au login/logout
    const l: UserListener = (u) => setLocal(u?.role ?? "user");
    userListeners.add(l);
    return () => { userListeners.delete(l); };
  }, []);
  return [role, setRole];
}

// ── Utilisateur ───────────────────────────────────────────────────────────────

export function getUser(): SessionUser | null {
  if (AUTH_DISABLED) return _DEV_USER;
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    const user = JSON.parse(raw) as SessionUser;
    return { ...user, role: normalizeRole(user.role) };
  } catch {
    return null;
  }
}

export function setUser(user: SessionUser): void {
  if (typeof window === "undefined") return;
  const nextUser = { ...user, role: normalizeRole(user.role) };
  localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
  setRole(nextUser.role);
  userListeners.forEach((l) => l(nextUser));
}

export function clearUser(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ROLE_KEY);
  userListeners.forEach((l) => l(null));
  roleListeners.forEach((l) => l("user"));
}

export function useUser(): SessionUser | null {
  const [user, setLocal] = useState<SessionUser | null>(() => getUser());
  useEffect(() => {
    const l: UserListener = (u) => setLocal(u);
    userListeners.add(l);
    return () => { userListeners.delete(l); };
  }, []);
  return user;
}

// ── Tokens JWT ────────────────────────────────────────────────────────────────

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function isTokenExpired(): boolean {
  if (typeof window === "undefined") return true;
  const exp = localStorage.getItem(TOKEN_EXP_KEY);
  if (!exp) return true;
  // Considère expiré 30 secondes avant l'expiration réelle (marge de sécurité)
  return Date.now() > parseInt(exp, 10) - 30_000;
}

export function setTokens(accessToken: string, refreshToken: string, expiresIn: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  // expiresIn = secondes avant expiration
  localStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + expiresIn * 1000));
}

export function updateAccessToken(accessToken: string, expiresIn: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(TOKEN_EXP_KEY, String(Date.now() + expiresIn * 1000));
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(TOKEN_EXP_KEY);
}

/** Déconnexion complète — supprime tokens + session utilisateur. */
export function clearSession(): void {
  clearTokens();
  clearUser();
}

/** Retourne true si l'utilisateur est authentifié (token présent et non expiré). */
export function isAuthenticated(): boolean {
  if (AUTH_DISABLED) return true;
  return !!getAccessToken() && !isTokenExpired();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

export function getInitials(name: string): string {
  return name
    .trim()
    .split(/\s+/)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("")
    .slice(0, 2) || "?";
}

export { roleLabels };

// ── Routing par rôle — source de vérité unique ────────────────────────────────
// Toute logique de redirection doit référencer ce mapping, jamais de chemins en dur.

export const ROLE_DEFAULT_ROUTES: Record<Role, string> = {
  public:   "/app",
  user:     "/app",
  agent:    "/app",
  chief:    "/app",
  director: "/app",
  admin:    "/app",
};

export function getDefaultRouteForRole(role: Role | string): string {
  return ROLE_DEFAULT_ROUTES[normalizeRole(role)] ?? "/app";
}
