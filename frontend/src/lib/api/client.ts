/**
 * Client HTTP de base — EDG Support.
 * Toutes les requêtes API passent par apiFetch.
 *
 * Fonctionnalités :
 *  - Injection automatique du JWT dans Authorization: Bearer
 *  - Désencapsulation { success, message, data } → data
 *  - Refresh automatique du token sur 401 (une seule tentative)
 *  - Redirection vers /login si le refresh échoue
 */

import {
  AUTH_DISABLED,
  clearSession,
  getAccessToken,
  getRefreshToken,
  isTokenExpired,
  updateAccessToken,
} from "../session";

const API_BASE =
  import.meta.env.VITE_API_URL ??
  (import.meta.env.DEV ? "http://localhost:8000/api/v1" : "/api/v1");

// Le endpoint /health vit à la racine du backend (health.py, non préfixé par
// /api/v1 dans main.py — voir CLAUDE.md), d'où ce base URL dédié.
const API_ROOT = API_BASE.replace(/\/api\/v1$/, "");

const REQUEST_TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly errorCode: string,
    message: string,
    public readonly field?: string,
    public readonly value?: string,
    public readonly details?: Array<{ field: string; message: string }>,
    public readonly hint?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ── Refresh lock — évite les appels parallèles ────────────────────────────────

let _refreshPromise: Promise<string | null> | null = null;

async function _attemptRefresh(): Promise<string | null> {
  if (_refreshPromise) return _refreshPromise;

  _refreshPromise = (async () => {
    try {
      const refreshToken = getRefreshToken();
      if (!refreshToken) {
        clearSession();
        return null;
      }

      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!res.ok) {
        clearSession();
        if (typeof window !== "undefined") {
          window.location.href = "/login";
        }
        return null;
      }

      const json = await res.json();
      const data = json?.data ?? json;
      const { access_token, expires_in } = data as {
        access_token: string;
        expires_in: number;
      };
      updateAccessToken(access_token, expires_in);
      return access_token;
    } catch {
      clearSession();
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      return null;
    } finally {
      _refreshPromise = null;
    }
  })();

  return _refreshPromise;
}

// ── Fetch principal ───────────────────────────────────────────────────────────

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { skipContentType?: boolean; skipAuth?: boolean },
): Promise<T> {
  const { skipContentType, skipAuth, headers: extraHeaders, signal: externalSignal, ...rest } = init ?? {};

  const headers: Record<string, string> = skipContentType
    ? {}
    : { "Content-Type": "application/json" };

  // Injection automatique du JWT
  if (!skipAuth) {
    if (!AUTH_DISABLED) {
      let token = getAccessToken();

      // Pre-emptive refresh si le token va bientôt expirer
      if (token && isTokenExpired()) {
        const refreshToken = getRefreshToken();
        if (refreshToken) {
          token = await _attemptRefresh();
        } else {
          token = null;
        }
      }

      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }
    }
  }

  if (extraHeaders) {
    Object.assign(headers, extraHeaders);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  if (externalSignal) {
    externalSignal.addEventListener("abort", () => controller.abort());
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      headers,
      ...rest,
      signal: controller.signal,
    });
  } catch (err) {
    clearTimeout(timer);
    if ((err as Error).name === "AbortError") {
      throw new Error("La requête a expiré. Vérifiez que le serveur backend est démarré.");
    }
    throw new Error("Impossible de contacter le serveur. Vérifiez votre connexion.");
  } finally {
    clearTimeout(timer);
  }

  // ── Retry automatique sur 401 ─────────────────────────────────────────────
  if (res.status === 401 && !skipAuth) {
    const newToken = await _attemptRefresh();
    if (newToken) {
      // Retry la requête originale avec le nouveau token
      const retryHeaders = { ...headers, Authorization: `Bearer ${newToken}` };
      const retryController = new AbortController();
      const retryTimer = setTimeout(() => retryController.abort(), REQUEST_TIMEOUT_MS);
      try {
        res = await fetch(`${API_BASE}${path}`, {
          headers: retryHeaders,
          ...rest,
          signal: retryController.signal,
        });
      } catch (err) {
        if ((err as Error).name === "AbortError") {
          throw new Error("La requête de retry a expiré. Vérifiez que le serveur backend est démarré.");
        }
        throw new Error("Impossible de contacter le serveur lors du retry.");
      } finally {
        clearTimeout(retryTimer);
      }
    }
  }

  let json: unknown;
  try {
    json = await res.json();
  } catch {
    if (!res.ok) throw new ApiError(res.status, "PARSE_ERROR", res.statusText);
    return undefined as T;
  }

  if (!res.ok) {
    const body = json as Record<string, unknown>;
    throw new ApiError(
      res.status,
      (body.error_code as string) ?? "UNKNOWN",
      (body.message as string) ?? "Erreur inattendue",
      body.field as string | undefined,
      body.value as string | undefined,
      body.details as ApiError["details"],
      body.hint as string | undefined,
    );
  }

  // Désencapsuler { success, message, data }
  if (json && typeof json === "object" && "data" in (json as object)) {
    return (json as { data: T }).data;
  }
  return json as T;
}

function normalizeApiBlobPath(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  if (path.startsWith("/api/v1")) return path.slice("/api/v1".length) || "/";
  return path.startsWith("/") ? path : `/${path}`;
}

function filenameFromContentDisposition(value: string | null): string | undefined {
  if (!value) return undefined;
  const utf8 = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8?.[1]) return decodeURIComponent(utf8[1].replace(/"/g, ""));
  const ascii = value.match(/filename="?([^";]+)"?/i);
  return ascii?.[1];
}

export async function apiFetchBlob(
  path: string,
  init?: RequestInit & { skipAuth?: boolean },
): Promise<{ blob: Blob; filename?: string; contentType?: string }> {
  const { skipAuth, headers: extraHeaders, signal: externalSignal, ...rest } = init ?? {};
  const headers: Record<string, string> = {};

  if (!skipAuth) {
    if (!AUTH_DISABLED) {
      let token = getAccessToken();
      if (token && isTokenExpired()) {
        token = getRefreshToken() ? await _attemptRefresh() : null;
      }
      if (token) headers.Authorization = `Bearer ${token}`;
    }
  }

  if (extraHeaders) Object.assign(headers, extraHeaders);

  const normalizedPath = normalizeApiBlobPath(path);
  const url = /^https?:\/\//i.test(normalizedPath) ? normalizedPath : `${API_BASE}${normalizedPath}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  if (externalSignal) externalSignal.addEventListener("abort", () => controller.abort());

  let res: Response;
  try {
    res = await fetch(url, { headers, ...rest, signal: controller.signal });
  } catch (err) {
    clearTimeout(timer);
    if ((err as Error).name === "AbortError") {
      throw new Error("La requête a expiré. Vérifiez que le serveur backend est démarré.");
    }
    throw new Error("Impossible de contacter le serveur. Vérifiez votre connexion.");
  } finally {
    clearTimeout(timer);
  }

  if (res.status === 401 && !skipAuth) {
    const newToken = await _attemptRefresh();
    if (newToken) {
      res = await fetch(url, {
        headers: { ...headers, Authorization: `Bearer ${newToken}` },
        ...rest,
      });
    }
  }

  if (!res.ok) {
    let message = res.statusText || "Erreur inattendue";
    try {
      const body = await res.json();
      message = body.message ?? body.detail ?? message;
    } catch {
      try {
        message = await res.text();
      } catch { /* ignore */ }
    }
    throw new ApiError(res.status, "FILE_DOWNLOAD_FAILED", message);
  }

  return {
    blob: await res.blob(),
    filename: filenameFromContentDisposition(res.headers.get("content-disposition")),
    contentType: res.headers.get("content-type") ?? undefined,
  };
}

/** Vérifie la disponibilité du backend et de la base de données. Endpoint public, sans JWT. */
export async function checkHealth(): Promise<{ status: string; database: string }> {
  const res = await fetch(`${API_ROOT}/health`);
  if (!res.ok) throw new ApiError(res.status, "HEALTH_CHECK_FAILED", res.statusText);
  return res.json();
}
