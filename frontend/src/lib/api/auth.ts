/**
 * Module API — Authentification JWT.
 * Endpoints :
 *   POST /auth/register  → TokenResponse
 *   POST /auth/login     → TokenResponse
 *   POST /auth/refresh   → AccessTokenResponse
 *   POST /auth/logout    → 204
 *   GET  /auth/me        → AccountUser
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
  password: string;
  phone?: string;
  role?: string;
  matricule?: string;
  job?: string;
  direction_id?: number;
  unit_id?: number;
  is_edg_employee?: boolean;
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: RawAccount;
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

export async function loginUser(payload: LoginPayload): Promise<AuthResult> {
  const raw = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify({
      identifier: payload.identifier,
      password: payload.password,
    }),
  });
  return mapTokenResponse(raw);
}

export async function registerUser(payload: RegisterPayload): Promise<AuthResult> {
  const raw = await apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    skipAuth: true,
    body: JSON.stringify(payload),
  });
  return mapTokenResponse(raw);
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

export async function changePassword(payload: {
  current_password: string;
  new_password: string;
}): Promise<void> {
  await apiFetch<void>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
