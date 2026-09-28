/**
 * Module API — Authentification via la plateforme centrale manager-user.
 * Endpoints :
 *   POST /auth/register        → compte créé (pas de session — connexion explicite ensuite)
 *   POST /auth/login           → TokenResponse, ou ConsentRequiredResponse si
 *                                 l'utilisateur central n'a aucun compte local
 *                                 NI groupe support de cette application
 *   POST /auth/consent/accept  → TokenResponse, après acceptation explicite
 *   POST /auth/refresh         → AccessTokenResponse
 *   POST /auth/logout          → 204
 *   GET  /auth/me              → AccountUser
 */
import { apiFetch } from "./client";
import { mapAccount } from "./accounts";
import type { RawAccount, AccountUser } from "./accounts";

// ── Types ─────────────────────────────────────────────────────────────────────

export type LoginPayload = {
  identifier: string;    // email ou matricule
  password: string;
};

export type RegisterPayload = {
  name: string;
  firstname?: string;
  email: string;
  phone?: string;
  password: string;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: RawAccount;
};

export type ConsentRequiredResponse = {
  needs_consent: true;
  access_token: string;
  refresh_token: string;
  expires_in: number;
  email: string;
  suggested_name?: string | null;
  suggested_firstname?: string | null;
  suggested_phone?: string | null;
  consent_version: string;
};

export type AccessTokenResponse = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type AuthResult = {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: AccountUser;
};

/** Rattachement requis avant accès à l'application — voir routes/consent.tsx.
 * Porte le bearer central déjà valide (obtenu au login), à réutiliser tel
 * quel pour POST /auth/consent/accept une fois le consentement donné. */
export type ConsentRequired = {
  needsConsent: true;
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  email: string;
  suggestedName?: string;
  suggestedFirstname?: string;
  suggestedPhone?: string;
  consentVersion: string;
};

export type LoginResult = ({ needsConsent: false } & AuthResult) | ConsentRequired;

export type AcceptConsentPayload = {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  consentVersion: string;
  name: string;
  firstname?: string;
  phone?: string;
};

// ── Mappers ───────────────────────────────────────────────────────────────────

function mapTokenResponse(raw: TokenResponse): AuthResult {
  return {
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
    expiresIn: raw.expires_in,
    user: mapAccount(raw.user),
  };
}

// ── API functions ─────────────────────────────────────────────────────────────

export async function loginUser(payload: LoginPayload): Promise<LoginResult> {
  const raw = await apiFetch<TokenResponse | ConsentRequiredResponse>("/auth/login", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({
      identifier: payload.identifier,
      password: payload.password,
    }),
  });
  if ("needs_consent" in raw) {
    return {
      needsConsent: true,
      accessToken: raw.access_token,
      refreshToken: raw.refresh_token,
      expiresIn: raw.expires_in,
      email: raw.email,
      suggestedName: raw.suggested_name ?? undefined,
      suggestedFirstname: raw.suggested_firstname ?? undefined,
      suggestedPhone: raw.suggested_phone ?? undefined,
      consentVersion: raw.consent_version,
    };
  }
  return { needsConsent: false, ...mapTokenResponse(raw) };
}

/** Rattachement après consentement explicite (voir routes/consent.tsx). Le
 * bearer central de `payload.accessToken` n'est pas encore en session (voir
 * ConsentRequired) — passé explicitement en en-tête plutôt que via le JWT
 * auto-injecté par apiFetch. */
export async function acceptConsent(payload: AcceptConsentPayload): Promise<AuthResult> {
  const raw = await apiFetch<TokenResponse>("/auth/consent/accept", {
    method: "POST",
    skipAuth: true,
    headers: { Authorization: `Bearer ${payload.accessToken}` },
    body: JSON.stringify({
      refresh_token: payload.refreshToken,
      expires_in: payload.expiresIn,
      consent_version: payload.consentVersion,
      name: payload.name,
      firstname: payload.firstname || undefined,
      phone: payload.phone || undefined,
    }),
  });
  return mapTokenResponse(raw);
}

export async function registerUser(payload: RegisterPayload): Promise<void> {
  await apiFetch<unknown>("/auth/register", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(payload),
  });
}

export async function refreshAccessToken(refreshToken: string): Promise<AccessTokenResponse> {
  return apiFetch<AccessTokenResponse>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function logoutUser(refreshToken: string): Promise<void> {
  await apiFetch<void>("/auth/logout", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
}

export async function getMe(): Promise<AccountUser> {
  const raw = await apiFetch<RawAccount>("/auth/me");
  return mapAccount(raw);
}

/** Changement de mot de passe depuis l'espace connecté (page Profil).
 *  Aucun email ni code de vérification : l'utilisateur est déjà authentifié.
 *  Le mot de passe n'existe que sur la plateforme centrale, la mise à jour y est
 *  donc immédiatement valable partout. */
export async function changeMyPassword(
  newPassword: string,
  confirmPassword: string,
): Promise<void> {
  await apiFetch<{ changed: boolean }>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      new_password: newPassword,
      confirm_password: confirmPassword,
    }),
  });
}
