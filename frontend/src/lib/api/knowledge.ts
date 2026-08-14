/**
 * Module API — Base de connaissance
 * Endpoints : /knowledge/*, PUT /knowledge/:id/publish
 */
import { apiFetch } from "./client";
import type { KnowledgeArticle } from "@/lib/mock-data";

// ── Types bruts backend ───────────────────────────────────────────────────────

export type RawKnowledgeArticle = {
  id: string;
  title: string;
  excerpt: string;
  body: string;
  category: string;
  read_time: number;
  author: string;
  author_id?: string | null;
  is_published: boolean;
  is_archived: boolean;
  tags?: string[] | null;
  published_at?: string | null;
  status: boolean;
  created_at: string;
  updated_at: string;
};

export type PaginatedKnowledge = {
  items: KnowledgeArticle[];
  total: number;
  page: number;
  pages: number;
};

// ── Mapper ────────────────────────────────────────────────────────────────────

export function mapArticle(raw: RawKnowledgeArticle): KnowledgeArticle {
  return {
    id: raw.id,
    title: raw.title,
    excerpt: raw.excerpt,
    body: raw.body,
    category: raw.category,
    readTime: raw.read_time,
    author: raw.author,
    updatedAt: raw.updated_at,
    published: raw.is_published,
    tags: Array.isArray(raw.tags) ? raw.tags : [],
  };
}

// ── Fonctions ─────────────────────────────────────────────────────────────────

export async function fetchArticles(params?: {
  published?: boolean;
  category?: string;
  q?: string;
  page?: number;
  limit?: number;
}): Promise<PaginatedKnowledge> {
  const qs = new URLSearchParams();
  if (params?.published !== undefined) qs.set("published", String(params.published));
  if (params?.category) qs.set("category", params.category);
  if (params?.q) qs.set("q", params.q);
  if (params?.page) qs.set("page", String(params.page));
  if (params?.limit) qs.set("limit", String(params.limit));
  const raw = await apiFetch<{
    items: RawKnowledgeArticle[];
    total: number;
    page: number;
    pages: number;
  }>(`/knowledge?${qs}`);
  return { ...raw, items: raw.items.map(mapArticle) };
}

export async function fetchArticle(id: string): Promise<KnowledgeArticle> {
  const raw = await apiFetch<RawKnowledgeArticle>(`/knowledge/${id}`);
  return mapArticle(raw);
}

export async function createArticle(
  data: Omit<KnowledgeArticle, "id" | "updatedAt">,
): Promise<KnowledgeArticle> {
  const raw = await apiFetch<RawKnowledgeArticle>("/knowledge", {
    method: "POST",
    body: JSON.stringify({
      title: data.title,
      excerpt: data.excerpt,
      body: data.body,
      category: data.category,
      read_time: data.readTime,
      author: data.author,
      is_published: data.published,
      tags: data.tags ?? [],
    }),
  });
  return mapArticle(raw);
}

export async function updateArticle(
  id: string,
  data: Partial<Omit<KnowledgeArticle, "id" | "updatedAt">>,
): Promise<KnowledgeArticle> {
  const payload: Record<string, unknown> = {};
  if (data.title !== undefined) payload.title = data.title;
  if (data.excerpt !== undefined) payload.excerpt = data.excerpt;
  if (data.body !== undefined) payload.body = data.body;
  if (data.category !== undefined) payload.category = data.category;
  if (data.readTime !== undefined) payload.read_time = data.readTime;
  if (data.author !== undefined) payload.author = data.author;
  if (data.published !== undefined) payload.is_published = data.published;
  if (data.tags !== undefined) payload.tags = data.tags;
  const raw = await apiFetch<RawKnowledgeArticle>(`/knowledge/${id}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return mapArticle(raw);
}

export async function publishArticle(
  id: string,
  published = true,
): Promise<KnowledgeArticle> {
  const raw = await apiFetch<RawKnowledgeArticle>(`/knowledge/${id}/publish`, {
    method: "PUT",
    body: JSON.stringify({ published }),
  });
  return mapArticle(raw);
}

export async function deleteArticle(id: string): Promise<void> {
  await apiFetch<void>(`/knowledge/${id}`, { method: "DELETE" });
}
