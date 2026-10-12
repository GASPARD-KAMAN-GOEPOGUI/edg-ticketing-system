import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ApiError } from "./api/client";
import {
  LOGOUT_MESSAGES,
  SESSION_REVOKED_EVENT,
  __resetForcedLogoutForTests,
  consumeLogoutReason,
  forceLogout,
  handleSessionRevokedEvent,
  onForcedLogout,
  revocationReasonFromBody,
} from "./forced-logout";
import { INVALIDATION_MAP } from "./realtime/invalidation-map";
import { sseClient } from "./realtime/sse-client";
import { getAccessToken, getUser, setTokens, setUser } from "./session";

// ── Environnement navigateur minimal (vitest tourne en "node") ───────────────

class MemoryStorage {
  private data = new Map<string, string>();
  getItem(key: string) {
    return this.data.has(key) ? this.data.get(key)! : null;
  }
  setItem(key: string, value: string) {
    this.data.set(key, String(value));
  }
  removeItem(key: string) {
    this.data.delete(key);
  }
  clear() {
    this.data.clear();
  }
}

/** EventSource simulé : le test pousse lui-même les événements serveur. */
class FakeEventSource {
  static last: FakeEventSource | null = null;
  listeners = new Map<string, Array<(e: { data: string }) => void>>();
  onerror: (() => void) | null = null;
  closed = false;
  constructor(public url: string) {
    FakeEventSource.last = this;
  }
  addEventListener(type: string, fn: (e: { data: string }) => void) {
    this.listeners.set(type, [...(this.listeners.get(type) ?? []), fn]);
  }
  emit(type: string, data: unknown) {
    this.listeners.get(type)?.forEach((fn) => fn({ data: JSON.stringify(data) }));
  }
  close() {
    this.closed = true;
  }
}

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function signIn() {
  setTokens("access-old", "refresh-old", 300);
  setUser({ id: "2", name: "A", email: "a@edg.gn", role: "chief-service" });
}

beforeEach(() => {
  vi.stubGlobal("window", { location: { pathname: "/app", assign: vi.fn() } });
  vi.stubGlobal("localStorage", new MemoryStorage());
  vi.stubGlobal("sessionStorage", new MemoryStorage());
  vi.stubGlobal("EventSource", FakeEventSource);
  __resetForcedLogoutForTests();
  FakeEventSource.last = null;
});

afterEach(() => {
  sseClient.disconnect();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

// ── Motifs ────────────────────────────────────────────────────────────────────

describe("revocationReasonFromBody", () => {
  it("reconnaît une session révoquée par changement de rôle", () => {
    expect(revocationReasonFromBody({ error_code: "SESSION_REVOKED", value: "role_changed" })).toBe(
      "role_changed",
    );
  });

  it("reconnaît un compte désactivé ou supprimé", () => {
    expect(revocationReasonFromBody({ error_code: "ACCOUNT_DISABLED", value: "disabled" })).toBe(
      "disabled",
    );
    expect(revocationReasonFromBody({ error_code: "ACCOUNT_DISABLED", value: "deleted" })).toBe(
      "deleted",
    );
  });

  it("ignore un 401 ordinaire (token expiré : un refresh suffit)", () => {
    expect(revocationReasonFromBody({ error_code: "UNAUTHORIZED" })).toBeNull();
    expect(revocationReasonFromBody(null)).toBeNull();
  });

  it("donne des messages explicites, jamais un 401 brut", () => {
    expect(LOGOUT_MESSAGES.role_changed).toMatch(/rôle a été modifié/);
    expect(LOGOUT_MESSAGES.disabled).toMatch(/désactivé/);
  });
});

// ── Déconnexion forcée ────────────────────────────────────────────────────────

describe("forceLogout", () => {
  it("efface la session, ferme le flux SSE et transmet le motif à /login", () => {
    signIn();
    const disconnect = vi.spyOn(sseClient, "disconnect");
    const listener = vi.fn();
    onForcedLogout(listener);

    forceLogout("role_changed");

    expect(getAccessToken()).toBeNull();
    expect(getUser()).toBeNull();
    expect(disconnect).toHaveBeenCalled();
    expect(listener).toHaveBeenCalledWith("role_changed");
    expect(consumeLogoutReason()).toBe("role_changed");
    // Lu une seule fois.
    expect(consumeLogoutReason()).toBeNull();
  });

  it("une salve de déclencheurs ne produit qu'une seule sortie", () => {
    const listener = vi.fn();
    onForcedLogout(listener);
    forceLogout("disabled");
    forceLogout("disabled");
    forceLogout("revoked");
    expect(listener).toHaveBeenCalledTimes(1);
  });

  it("hors du shell applicatif, redirige vers /login", () => {
    forceLogout("disabled");
    expect(window.location.assign).toHaveBeenCalledWith("/login");
  });
});

// ── Réception de l'événement temps réel ──────────────────────────────────────

describe("événement SSE user.session_revoked", () => {
  it("déconnecte immédiatement l'utilisateur concerné avec le bon motif", () => {
    signIn();
    const listener = vi.fn();
    onForcedLogout(listener);
    sseClient.on(SESSION_REVOKED_EVENT, handleSessionRevokedEvent);
    sseClient.connect(() => "access-old");

    FakeEventSource.last!.emit(SESSION_REVOKED_EVENT, {
      user_id: 2,
      reason: "role_changed",
      timestamp: "2026-10-06T08:00:00Z",
    });

    expect(listener).toHaveBeenCalledWith("role_changed");
    expect(getAccessToken()).toBeNull();
    expect(FakeEventSource.last!.closed).toBe(true);
  });

  it("un motif inconnu retombe sur un message générique", () => {
    const listener = vi.fn();
    onForcedLogout(listener);
    handleSessionRevokedEvent({ reason: "???" });
    expect(listener).toHaveBeenCalledWith("revoked");
  });
});

// ── Client HTTP : 401 typé ────────────────────────────────────────────────────

describe("apiFetch et session révoquée", () => {
  it("401 SESSION_REVOKED : aucune tentative de refresh, déconnexion forcée", async () => {
    signIn();
    const listener = vi.fn();
    onForcedLogout(listener);
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse(401, {
        success: false,
        error_code: "SESSION_REVOKED",
        value: "role_changed",
        message: LOGOUT_MESSAGES.role_changed,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/requests/")).rejects.toBeInstanceOf(ApiError);
    expect(fetchMock).toHaveBeenCalledTimes(1); // pas d'appel /auth/refresh
    expect(listener).toHaveBeenCalledWith("role_changed");
  });

  it("refresh refusé pour compte désactivé : motif « disabled »", async () => {
    signIn();
    const listener = vi.fn();
    onForcedLogout(listener);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { success: false, error_code: "UNAUTHORIZED" }))
      .mockResolvedValueOnce(
        jsonResponse(401, { success: false, error_code: "ACCOUNT_DISABLED", value: "disabled" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/requests/")).rejects.toBeInstanceOf(ApiError);
    expect(String(fetchMock.mock.calls[1][0])).toMatch(/\/auth\/refresh$/);
    expect(listener).toHaveBeenCalledWith("disabled");
  });

  it("401 ordinaire puis refresh réussi : aucune déconnexion", async () => {
    signIn();
    const listener = vi.fn();
    onForcedLogout(listener);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { success: false, error_code: "UNAUTHORIZED" }))
      .mockResolvedValueOnce(
        jsonResponse(200, { success: true, data: { access_token: "access-new", expires_in: 300 } }),
      )
      .mockResolvedValueOnce(jsonResponse(200, { success: true, data: { ok: true } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/requests/")).resolves.toEqual({ ok: true });
    expect(listener).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("access-new");
  });

  it("panne réseau pendant le refresh : la session n'est pas détruite", async () => {
    signIn();
    const listener = vi.fn();
    onForcedLogout(listener);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(401, { success: false, error_code: "UNAUTHORIZED" }))
      .mockRejectedValueOnce(new TypeError("Failed to fetch"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/requests/")).rejects.toBeInstanceOf(ApiError);
    expect(listener).not.toHaveBeenCalled();
    expect(getAccessToken()).toBe("access-old");
  });
});

// ── Synchronisation du Backoffice ────────────────────────────────────────────

describe("carte d'invalidation des comptes", () => {
  it("user.created/updated/deleted rafraîchissent le Backoffice et le profil", () => {
    for (const type of ["user.created", "user.updated", "user.deleted"]) {
      const keys = INVALIDATION_MAP[type].map((k) => JSON.stringify(k));
      expect(keys).toContain(JSON.stringify(["admin", "users"]));
      expect(keys).toContain(JSON.stringify(["me"]));
    }
  });
});
