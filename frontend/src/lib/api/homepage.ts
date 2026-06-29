/**
 * Module API — Configuration de la page d'accueil
 */
import { apiFetch } from "./client";
import type { HomepageConfig, SectionConfig } from "@/lib/homepage-config";
import { DEFAULT_SECTIONS, DEFAULT_CONFIG } from "@/lib/homepage-config";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawSection = {
  id?: number;
  section_id: string;
  visible: boolean;
  sort_order: number;
  editable: boolean;
  title?: string | null;
  content?: string | null;
  expires_at?: string | null;
  is_custom?: boolean;
};

export type RawHomepageConfig = {
  sections: RawSection[];
  mission_text: string;
};

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapConfig(raw: RawHomepageConfig): HomepageConfig {
  const mapped = raw.sections.map((r): SectionConfig => {
    const def = DEFAULT_SECTIONS.find((d) => d.id === r.section_id);
    return {
      id: r.section_id,
      dbId: r.id,
      label: r.title ?? def?.label ?? r.section_id,
      desc: def?.desc ?? "",
      visible: r.visible,
      order: r.sort_order,
      editable: r.editable,
      title: r.title ?? undefined,
      content: r.content ?? undefined,
      expiresAt: r.expires_at ?? null,
      isCustom: r.is_custom ?? false,
    };
  });
  // Defensive: add built-in sections missing from the backend response
  const ids = new Set(mapped.map((s) => s.id));
  DEFAULT_SECTIONS.filter((d) => !ids.has(d.id)).forEach((d) => mapped.push({ ...d }));
  mapped.sort((a, b) => a.order - b.order);
  return { sections: mapped, missionText: raw.mission_text };
}

// ── API calls — lecture ───────────────────────────────────────────────────────

export async function fetchHomepageConfig(): Promise<HomepageConfig> {
  try {
    const raw = await apiFetch<RawHomepageConfig>("/homepage-config/");
    return mapConfig(raw);
  } catch {
    return DEFAULT_CONFIG;
  }
}

// ── API calls — admin bulk ────────────────────────────────────────────────────

export async function saveHomepageConfigApi(config: HomepageConfig): Promise<HomepageConfig> {
  const raw = await apiFetch<RawHomepageConfig>("/admin/homepage-config", {
    method: "PATCH",
    body: JSON.stringify({
      sections: config.sections.map((s) => ({
        section_id: s.id,
        visible: s.visible,
        sort_order: s.order,
        editable: s.editable ?? false,
        title: s.title ?? null,
        content: s.content ?? null,
        expires_at: s.expiresAt ?? null,
      })),
      mission_text: config.missionText,
    }),
  });
  return mapConfig(raw);
}

export async function resetHomepageConfigApi(): Promise<HomepageConfig> {
  const raw = await apiFetch<RawHomepageConfig>("/admin/homepage-config", {
    method: "DELETE",
  });
  return mapConfig(raw);
}

// ── API calls — admin par section ─────────────────────────────────────────────

export async function createSectionApi(data: {
  section_id: string;
  title: string;
  content?: string;
  visible?: boolean;
  expires_at?: string | null;
}): Promise<HomepageConfig> {
  const raw = await apiFetch<RawHomepageConfig>("/admin/homepage-config/sections", {
    method: "POST",
    body: JSON.stringify(data),
  });
  return mapConfig(raw);
}

export async function updateSectionByIdApi(
  id: number,
  data: {
    title?: string;
    content?: string;
    mission_text?: string;
    visible?: boolean;
    sort_order?: number;
    expires_at?: string | null;
  }
): Promise<HomepageConfig> {
  const raw = await apiFetch<RawHomepageConfig>(`/admin/homepage-config/sections/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  return mapConfig(raw);
}

export async function deleteSectionApi(id: number): Promise<HomepageConfig> {
  const raw = await apiFetch<RawHomepageConfig>(`/admin/homepage-config/sections/${id}`, {
    method: "DELETE",
  });
  return mapConfig(raw);
}

// ── Slides du carrousel d'accueil ─────────────────────────────────────────────

export type HomepageSlide = {
  id: number;
  title?: string | null;
  message?: string | null;
  cta_label?: string | null;
  cta_url?: string | null;
  image_url?: string | null;
  sort_order: number;
  visible: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
};

export async function fetchSlides(): Promise<HomepageSlide[]> {
  try {
    return await apiFetch<HomepageSlide[]>("/homepage/slides/");
  } catch {
    return [];
  }
}

export async function fetchAdminSlides(): Promise<HomepageSlide[]> {
  return apiFetch<HomepageSlide[]>("/admin/homepage/slides/");
}

export async function createSlideApi(data: Partial<HomepageSlide>): Promise<HomepageSlide> {
  return apiFetch<HomepageSlide>("/admin/homepage/slides/", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateSlideApi(id: number, data: Partial<HomepageSlide>): Promise<HomepageSlide> {
  return apiFetch<HomepageSlide>(`/admin/homepage/slides/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteSlideApi(id: number): Promise<void> {
  await apiFetch<void>(`/admin/homepage/slides/${id}`, { method: "DELETE" });
}
