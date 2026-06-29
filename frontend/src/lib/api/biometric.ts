import { apiFetch } from "./client";

export interface BiometricVerifyResult {
  match: boolean;
  confidence: number; // 0–100
  accessToken?: string;
  refreshToken?: string;
  expiresIn?: number;
  user?: {
    id: string;
    name: string;
    email: string;
    role: string;
    phone?: string;
    avatar?: string;
    direction_id?: string | null;
    unit_id?: string | null;
  };
}

export async function verifyBiometric(payload: {
  image: string;
  identifier: string;
}): Promise<BiometricVerifyResult> {
  const raw = await apiFetch<{
    match: boolean;
    confidence: number;
    access_token?: string;
    refresh_token?: string;
    expires_in?: number;
    user?: {
      id: string;
      name: string;
      email: string;
      role: string;
      phone?: string;
      avatar?: string;
      direction_id?: string | null;
      unit_id?: string | null;
    };
  }>("/auth/biometric-verify", {
    method: "POST",
    body: JSON.stringify({ image: payload.image, identifier: payload.identifier }),
  });

  return {
    match: raw.match,
    confidence: raw.confidence,
    accessToken: raw.access_token,
    refreshToken: raw.refresh_token,
    expiresIn: raw.expires_in,
    user: raw.user,
  };
}

export async function reportSecurityIncident(payload: {
  identifier: string;
  captured_image: string;
  timestamp: string;
  user_agent: string;
  browser?: string;
  os_info?: string;
  device_type?: string;
  location_approx?: string;
  attempt_count?: number;
}): Promise<void> {
  await apiFetch<void>("/auth/security-incident", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
