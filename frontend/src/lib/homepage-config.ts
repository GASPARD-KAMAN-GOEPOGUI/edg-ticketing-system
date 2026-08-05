// Configuration dynamique de la page d'accueil — persistée via API.
// Seul l'administrateur système peut modifier ces paramètres.

const STORAGE_KEY = "edg.homepage.config";

export type KnownSectionId = "mission" | "services" | "how" | "for-who" | "trust";
export type SectionId = string;

export interface SectionConfig {
  id: SectionId;
  dbId?: number;
  label: string;
  desc: string;
  visible: boolean;
  order: number;
  editable?: boolean;
  title?: string;
  content?: string;
  expiresAt?: string | null;
  isCustom?: boolean;
}

export interface HomepageConfig {
  sections: SectionConfig[];
  missionText: string;
}

export const DEFAULT_SECTIONS: SectionConfig[] = [
  {
    id: "mission",
    label: "Bande de mission",
    desc: "Texte d'introduction court énonçant l'objectif global de la plateforme.",
    visible: true,
    order: 1,
    editable: true,
  },
  {
    id: "services",
    label: "Trois façons d'être accompagné",
    desc: "Les 3 cartes services : Signaler une panne, Demander un document, Poser une question.",
    visible: true,
    order: 2,
  },
  {
    id: "how",
    label: "Comment ça marche",
    desc: "Les 4 étapes du parcours client, du ticket à la résolution.",
    visible: true,
    order: 3,
  },
  {
    id: "for-who",
    label: "Pour qui ?",
    desc: "Deux cartes : Citoyen / Client et Agent / Employé EDG avec leurs CTAs respectifs.",
    visible: true,
    order: 4,
  },
  {
    id: "trust",
    label: "Confiance",
    desc: "Indicateurs de confiance (Sécurisé, Temps réel, Transparent, Humain) et CTA inscription.",
    visible: true,
    order: 5,
  },
];

export const DEFAULT_CONFIG: HomepageConfig = {
  sections: DEFAULT_SECTIONS,
  missionText:
    "EDG Support est la plateforme unique et officielle qui centralise tous vos tickets, incidents et réclamations vers la bonne direction — pour les citoyens, les clients et les agents d'Électricité de Guinée.",
};

export function loadHomepageConfig(): HomepageConfig {
  if (typeof window === "undefined") return DEFAULT_CONFIG;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_CONFIG;
    const parsed = JSON.parse(raw) as Partial<HomepageConfig>;
    const storedIds = new Set((parsed.sections ?? []).map((s) => s.id));
    const mergedSections: SectionConfig[] = [
      ...(parsed.sections ?? []),
      ...DEFAULT_SECTIONS.filter((s) => !storedIds.has(s.id)),
    ].sort((a, b) => a.order - b.order);
    return {
      sections: mergedSections,
      missionText: parsed.missionText ?? DEFAULT_CONFIG.missionText,
    };
  } catch {
    return DEFAULT_CONFIG;
  }
}

export function saveHomepageConfig(config: HomepageConfig): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {}
}

export function resetHomepageConfig(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {}
}

export function isSectionExpired(expiresAt?: string | null): boolean {
  if (!expiresAt) return false;
  return new Date(expiresAt) < new Date();
}
