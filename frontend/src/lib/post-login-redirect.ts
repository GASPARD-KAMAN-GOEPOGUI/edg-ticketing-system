/**
 * Destination à rouvrir après la connexion.
 *
 * Un bouton d'e-mail (« Voir le ticket », « Ouvrir la file d'attente ») ouvre
 * une page de /app. Sans session, le garde d'authentification envoie sur
 * /login : la page demandée est retenue ici, puis rouverte une fois la
 * connexion (et l'éventuel consentement) terminée — au lieu de l'accueil.
 *
 * sessionStorage : propre à l'onglet, comme le parcours lien → connexion.
 * Seuls les chemins internes /app… sont acceptés : un lien forgé ne doit
 * jamais rediriger vers un autre site après la connexion.
 */

const KEY = "edg.auth.post_login_redirect";

export function safeAppPath(value: unknown): string | null {
  if (typeof value !== "string" || value.length > 2048) return null;
  if (!/^\/app(?:[/?#]|$)/.test(value)) return null;
  if (value.includes("\\") || value.startsWith("//")) return null;
  return value;
}

export function rememberPostLoginTarget(value: unknown): void {
  const path = safeAppPath(value);
  if (!path) return;
  try {
    sessionStorage.setItem(KEY, path);
  } catch {
    /* stockage indisponible : on retombera sur l'accueil du rôle */
  }
}

/** Lit ET efface la destination : elle ne sert qu'une fois. */
export function consumePostLoginTarget(): string | null {
  try {
    const value = sessionStorage.getItem(KEY);
    sessionStorage.removeItem(KEY);
    return safeAppPath(value);
  } catch {
    return null;
  }
}
