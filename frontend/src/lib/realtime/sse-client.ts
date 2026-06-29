/**
 * Client SSE — connexion temps réel EDG Support.
 *
 * Fonctionnalités :
 *  - Connexion EventSource avec JWT en query param (limitation navigateur)
 *  - Reconnexion automatique avec backoff exponentiel (1s → 30s)
 *  - Abonnement typé aux événements applicatifs via on()
 *  - Re-registration automatique des handlers après reconnexion
 *  - Déconnexion propre
 */

const API_BASE: string =
  (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) ||
  (typeof import.meta !== "undefined" && import.meta.env?.DEV
    ? "http://localhost:8000/api/v1"
    : "/api/v1");

export type EventPayload = Record<string, unknown>;
export type EventHandler<T = EventPayload> = (payload: T) => void;

class SSEClient {
  private es: EventSource | null = null;
  private readonly handlers = new Map<string, Set<EventHandler>>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private reconnectDelay = 1_000;
  private readonly maxDelay = 30_000;
  private _connected = false;
  private _enabled = false;
  private _getToken: (() => string | null) | null = null;

  /** Démarre la connexion SSE. getToken est appelé à chaque tentative de connexion. */
  connect(getToken: () => string | null): void {
    this._enabled = true;
    this._getToken = getToken;
    this._createSource();
  }

  private _createSource(): void {
    if (this.es) {
      this.es.close();
      this.es = null;
    }
    if (!this._enabled || !this._getToken) return;

    const token = this._getToken();
    if (!token) {
      // Pas de token disponible — réessayer plus tard
      if (this._enabled) this._scheduleReconnect();
      return;
    }

    const url = `${API_BASE}/events?token=${encodeURIComponent(token)}`;
    const es = new EventSource(url);
    this.es = es;

    // Méta-événements de connexion
    es.addEventListener("connected", () => {
      this._connected = true;
      this.reconnectDelay = 1_000; // reset backoff
      this._dispatch("_connected", {});
    });

    es.addEventListener("ping", () => { /* keepalive, ignoré */ });

    // Re-enregistrer tous les handlers connus sur ce nouvel EventSource
    for (const [eventType, fns] of this.handlers.entries()) {
      if (eventType.startsWith("_")) continue;
      for (const fn of fns) {
        this._addNativeListener(es, eventType, fn);
      }
    }

    es.onerror = () => {
      this._connected = false;
      this._dispatch("_disconnected", {});
      if (this._enabled) this._scheduleReconnect();
    };
  }

  private _addNativeListener(es: EventSource, eventType: string, fn: EventHandler): void {
    es.addEventListener(eventType, (e: Event) => {
      try {
        fn(JSON.parse((e as MessageEvent).data) as EventPayload);
      } catch (err) { console.warn("[SSE] Erreur de parsing événement :", err); }
    });
  }

  private _scheduleReconnect(): void {
    if (this.reconnectTimer !== null) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this._createSource();
    }, this.reconnectDelay);
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay);
  }

  /**
   * Abonne un handler à un type d'événement.
   * Retourne une fonction de désabonnement.
   */
  on<T = EventPayload>(eventType: string, handler: EventHandler<T>): () => void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, new Set());
    }
    this.handlers.get(eventType)!.add(handler as EventHandler);

    // Si déjà connecté, enregistrer immédiatement sur l'EventSource actif
    if (this.es && !eventType.startsWith("_")) {
      this._addNativeListener(this.es, eventType, handler as EventHandler);
    }

    return () => this.handlers.get(eventType)?.delete(handler as EventHandler);
  }

  private _dispatch(eventType: string, payload: EventPayload): void {
    this.handlers.get(eventType)?.forEach((fn) => {
      try { fn(payload); } catch { /* ignore */ }
    });
  }

  /** Déconnexion propre — annule les reconnexions en attente. */
  disconnect(): void {
    this._enabled = false;
    this._getToken = null;
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.es) {
      this.es.close();
      this.es = null;
    }
    this._connected = false;
  }

  get isConnected(): boolean {
    return this._connected;
  }
}

/** Singleton global — partagé par toute l'application. */
export const sseClient = new SSEClient();
