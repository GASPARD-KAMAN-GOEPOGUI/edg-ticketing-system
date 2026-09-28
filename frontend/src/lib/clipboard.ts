import { toast } from "sonner";

/**
 * Copie dans le presse-papier, y compris hors contexte sécurisé.
 *
 * `navigator.clipboard` n'existe QUE dans un contexte sécurisé : HTTPS, ou
 * localhost. Quand l'application est servie sur le réseau local — un téléphone
 * qui ouvre http://192.168.x.x:3000 — l'objet est absent et l'appel direct lève
 * un TypeError. Les boutons « Copier » devenaient donc inutilisables sur tous
 * les appareils du réseau, alors qu'ils servent notamment à récupérer le mot de
 * passe temporaire après une réinitialisation de compte.
 *
 * Deux niveaux, dans cet ordre :
 *   1. l'API moderne quand elle est disponible ;
 *   2. `document.execCommand("copy")` sur un textarea hors écran — obsolète mais
 *      universellement supporté, et sans exigence de contexte sécurisé.
 *
 * Retourne `false` si les deux échouent, à l'appelant d'en informer l'utilisateur
 * (voir `copyWithToast`).
 */
export async function copyToClipboard(text: string): Promise<boolean> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // Permission refusée ou document non focalisé — on tente le repli.
    }
  }

  if (typeof document === "undefined") return false;

  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    // Hors écran plutôt que display:none — un élément non rendu n'est pas
    // sélectionnable, donc la copie échouerait.
    textarea.setAttribute("readonly", "");
    textarea.style.position = "fixed";
    textarea.style.top = "-9999px";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    textarea.setSelectionRange(0, text.length); // iOS ignore select() seul
    const ok = document.execCommand("copy");
    document.body.removeChild(textarea);
    return ok;
  } catch {
    return false;
  }
}

/**
 * Copie + retour utilisateur. En cas d'échec, la valeur est affichée dans le
 * toast pour rester récupérable à la main — indispensable pour un mot de passe
 * temporaire, qui n'est montré qu'une fois.
 */
export async function copyWithToast(text: string, successMessage = "Copié"): Promise<void> {
  if (await copyToClipboard(text)) {
    toast.success(successMessage);
    return;
  }
  toast.error("Copie impossible sur cet appareil", {
    description: text,
    duration: 15_000,
  });
}
