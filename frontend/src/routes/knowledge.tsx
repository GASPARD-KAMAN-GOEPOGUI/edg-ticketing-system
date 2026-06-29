import { createFileRoute, Link } from "@tanstack/react-router";
import { PublicLayout } from "@/components/public-layout";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { KnowledgeArticle } from "@/lib/mock-data";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchArticles } from "@/lib/api/knowledge";
import { BookOpen, Search, Clock, User, ArrowLeft, Tag, Sparkles, ChevronRight } from "lucide-react";

// Route publique — base de connaissance en lecture seule, sans authentification
export const Route = createFileRoute("/knowledge")({
  head: () => ({
    meta: [
      { title: "Base de connaissance — EDG Support" },
      {
        name: "description",
        content: "Consultez les articles, guides et procédures EDG Support.",
      },
    ],
  }),
  component: PublicKnowledgePage,
});

// ── Vue détail d'un article ───────────────────────────────────────────────────

function ArticleDetail({
  article,
  onBack,
}: {
  article: KnowledgeArticle;
  onBack: () => void;
}) {
  return (
    <PublicLayout>
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-20">
        <Button
          variant="ghost"
          size="sm"
          className="mb-5 rounded-full"
          onClick={onBack}
        >
          <ArrowLeft className="mr-1 h-4 w-4" /> Retour
        </Button>

        <GlassCard strong className="space-y-5 p-7 sm:p-10">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-primary/10 px-2.5 py-1 font-medium text-primary">
              {article.category}
            </span>
            <span className="text-muted-foreground inline-flex items-center gap-1">
              <Clock className="h-3 w-3" /> {article.readTime} min de lecture
            </span>
            <span className="text-muted-foreground inline-flex items-center gap-1">
              <User className="h-3 w-3" /> {article.author}
            </span>
            {article.updatedAt && (
              <span className="text-muted-foreground">
                {new Date(article.updatedAt).toLocaleDateString("fr-FR", {
                  day: "numeric", month: "long", year: "numeric",
                })}
              </span>
            )}
          </div>

          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{article.title}</h1>
          <p className="text-muted-foreground leading-relaxed">{article.excerpt}</p>

          {(article.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(article.tags ?? []).map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary"
                >
                  <Tag className="h-3 w-3" />
                  {tag}
                </span>
              ))}
            </div>
          )}

          <div className="prose prose-sm max-w-none whitespace-pre-wrap text-foreground/90 border-t border-border/40 pt-5">
            {article.body}
          </div>

          <div className="flex justify-end border-t border-border/40 pt-4">
            <Button asChild className="rounded-full gradient-primary">
              <Link to="/login">Se connecter pour accéder à l'espace complet</Link>
            </Button>
          </div>
        </GlassCard>
      </section>
    </PublicLayout>
  );
}

// ── Carte article ─────────────────────────────────────────────────────────────

function ArticleCard({
  article,
  onClick,
}: {
  article: KnowledgeArticle;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group w-full text-left"
    >
      <GlassCard className="flex h-full flex-col gap-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg">
        <div className="flex items-start gap-3">
          <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl gradient-primary text-background shadow-md">
            <BookOpen className="h-4.5 w-4.5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              <span>{article.category}</span>
              <span>·</span>
              <span>{article.readTime} min</span>
            </div>
            <p className="mt-0.5 text-base font-semibold leading-snug group-hover:text-primary transition-colors">
              {article.title}
            </p>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{article.excerpt}</p>
          </div>
          <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/50 transition-transform group-hover:translate-x-0.5 group-hover:text-primary" />
        </div>

        {(article.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1 pt-1 border-t border-border/30">
            {(article.tags ?? []).map((tag) => (
              <span
                key={tag}
                className="inline-flex items-center gap-1 rounded-full bg-primary/8 px-2 py-0.5 text-[10px] font-medium text-primary"
              >
                <Tag className="h-2.5 w-2.5" />
                {tag}
              </span>
            ))}
          </div>
        )}
      </GlassCard>
    </button>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

function PublicKnowledgePage() {
  const [q, setQ] = useState("");
  const [opened, setOpened] = useState<KnowledgeArticle | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge", "public"],
    queryFn: () => fetchArticles({ published: true, limit: 200 }),
    staleTime: 5 * 60_000,
  });
  const list: KnowledgeArticle[] = (data?.items ?? []).filter((a) => a.published);

  // 4 articles les plus récents (triés par date de publication desc)
  const recentArticles = useMemo(
    () =>
      [...list]
        .sort(
          (a, b) =>
            new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime(),
        )
        .slice(0, 4),
    [list],
  );

  // Résultats de recherche intelligente (titre + extrait + corps + catégorie + tags)
  const searchResults = useMemo(() => {
    const trimmed = q.trim().toLowerCase();
    if (!trimmed) return [];
    return list.filter((a) =>
      `${a.title} ${a.excerpt} ${a.body} ${a.category} ${(a.tags ?? []).join(" ")}`
        .toLowerCase()
        .includes(trimmed),
    );
  }, [list, q]);

  const isSearching = q.trim().length > 0;

  if (opened) {
    return <ArticleDetail article={opened} onBack={() => setOpened(null)} />;
  }

  return (
    <PublicLayout>
      <section className="mx-auto max-w-5xl px-4 py-10 sm:px-6 sm:py-16">

        {/* En-tête */}
        <header className="mb-8">
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <BookOpen className="h-3 w-3" /> Ressources
          </div>
          <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
            Base de connaissance
          </h1>
          <p className="mt-2 text-muted-foreground">
            Articles, procédures et guides EDG Support.
          </p>
        </header>

        {/* Champ de recherche */}
        <div className="relative mb-8">
          <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Rechercher un article, une procédure, un guide…"
            className="h-12 rounded-full pl-11 pr-4 text-sm"
          />
          {q && (
            <button
              onClick={() => setQ("")}
              className="absolute right-4 top-1/2 -translate-y-1/2 text-xs text-muted-foreground hover:text-foreground"
            >
              ✕
            </button>
          )}
        </div>

        {/* Mode recherche */}
        {isSearching ? (
          <div>
            <p className="mb-4 text-sm text-muted-foreground">
              {searchResults.length > 0
                ? `${searchResults.length} résultat${searchResults.length > 1 ? "s" : ""} pour « ${q.trim()} »`
                : `Aucun résultat pour « ${q.trim()} »`}
            </p>
            {searchResults.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {searchResults.map((a) => (
                  <ArticleCard key={a.id} article={a} onClick={() => setOpened(a)} />
                ))}
              </div>
            ) : (
              <GlassCard className="py-12 text-center text-sm text-muted-foreground">
                Aucun article ne correspond à votre recherche.<br />
                <span className="mt-1 block text-xs">Essayez avec d'autres mots-clés.</span>
              </GlassCard>
            )}
          </div>
        ) : (
          /* Mode articles récents */
          <div>
            <div className="mb-4 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold">Articles récents</span>
            </div>

            {isLoading ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {[1, 2, 3, 4].map((i) => (
                  <GlassCard key={i} className="h-28 animate-pulse bg-muted/30" />
                ))}
              </div>
            ) : recentArticles.length > 0 ? (
              <div className="grid gap-4 sm:grid-cols-2">
                {recentArticles.map((a) => (
                  <ArticleCard key={a.id} article={a} onClick={() => setOpened(a)} />
                ))}
              </div>
            ) : (
              <GlassCard className="py-12 text-center text-sm text-muted-foreground">
                Aucun article publié pour le moment.
              </GlassCard>
            )}

            <p className="mt-5 text-center text-xs text-muted-foreground">
              Utilisez la recherche ci-dessus pour accéder à tous les articles.
            </p>
          </div>
        )}

        <div className="mt-10 flex justify-center">
          <Button asChild variant="outline" className="rounded-full">
            <Link to="/login">Se connecter pour accéder à l'espace complet</Link>
          </Button>
        </div>
      </section>
    </PublicLayout>
  );
}
