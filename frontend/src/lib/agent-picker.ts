/**
 * Liste de choix d'un agent (fenêtre « Réassigner le ticket ») : nom complet,
 * badge et recherche. Le nom seul (« Camara ») ne suffisait pas à distinguer
 * deux homonymes.
 */

type AgentLike = { name: string; firstname?: string | null; matricule?: string | null };

/** « Prénom Nom », comme dans le reste de l'application (PV, journal). */
export function agentFullName(agent: AgentLike): string {
  return [agent.firstname, agent.name].map((part) => part?.trim()).filter(Boolean).join(" ");
}

/** « Prénom Nom · BADGE », ou le nom complet seul sans badge. */
export function agentLabel(agent: AgentLike): string {
  const badge = agent.matricule?.trim();
  return badge ? `${agentFullName(agent)} · ${badge}` : agentFullName(agent);
}

export function agentInitials(agent: AgentLike): string {
  const parts = [agent.firstname, agent.name].map((part) => part?.trim()).filter(Boolean) as string[];
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0] ?? "").slice(0, 2).toUpperCase();
}

/** Sans majuscules ni accents : « kolie » trouve « Kolié ». */
function normalize(value: string): string {
  return value.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Prénom, nom ou badge contiennent chaque mot saisi. */
export function matchesAgentSearch(agent: AgentLike, query: string): boolean {
  const words = normalize(query).split(/\s+/).filter(Boolean);
  if (words.length === 0) return true;
  const haystack = normalize([agent.firstname, agent.name, agent.matricule].filter(Boolean).join(" "));
  return words.every((word) => haystack.includes(word));
}
