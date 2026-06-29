import { createFileRoute } from "@tanstack/react-router";
import { requireAuth } from "@/lib/auth-guard";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { KnowledgeArticle } from "@/lib/mock-data";
import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchArticles,
  createArticle,
  updateArticle,
  publishArticle,
  deleteArticle,
} from "@/lib/api/knowledge";
import { fetchRefTable } from "@/lib/api/admin-config";
import { useRole } from "@/lib/session";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import {
  BookOpen,
  Edit3,
  Plus,
  Search,
  Trash2,
  Eye,
  EyeOff,
  Clock,
  User,
  ArrowLeft,
  Tag,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { PaginationBar, usePagination } from "@/components/pagination-bar";


export const Route = createFileRoute("/app/knowledge")({
  beforeLoad: () => requireAuth(),
  head: () => ({ meta: [{ title: "Base de connaissance — EDG Support" }] }),
  component: KnowledgePage,
});

const FALLBACK_CATEGORIES = ["Pannes", "Documents", "Raccordement", "Facturation", "Sécurité", "Général"];

function emptyArticle(): KnowledgeArticle {
  return {
    id: "new",
    title: "",
    excerpt: "",
    body: "",
    category: "Général",
    readTime: 2,
    author: "Admin EDG",
    updatedAt: new Date().toISOString(),
    published: false,
    tags: [],
  };
}

function KnowledgePage() {
  const [role] = useRole();
  const isAdmin = role === "admin";
  const qc = useQueryClient();

  const { data: categoriesRef = [] } = useQuery({
    queryKey: ["ref", "knowledge_categories"],
    queryFn: () => fetchRefTable("knowledge_categories"),
    staleTime: 10 * 60_000,
  });
  const categories = categoriesRef.length > 0
    ? categoriesRef.map((c) => c.label)
    : FALLBACK_CATEGORIES;

  const { data } = useQuery({
    queryKey: ["knowledge"],
    queryFn: () => fetchArticles({ limit: 200 }),
  });
  const list: KnowledgeArticle[] = data?.items ?? [];

  const [q, setQ] = useState("");
  const [cat, setCat] = useState<string>("all");
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [opened, setOpened] = useState<KnowledgeArticle | null>(null);
  const [editing, setEditing] = useState<KnowledgeArticle | null>(null);
  const [confirmDel, setConfirmDel] = useState<KnowledgeArticle | null>(null);

  const visible = useMemo(
    () =>
      list
        .filter((a) => isAdmin || a.published)
        .filter((a) => cat === "all" || a.category === cat)
        .filter((a) =>
          !q ||
          `${a.title} ${a.excerpt} ${a.body} ${a.category} ${(a.tags ?? []).join(" ")}`
            .toLowerCase()
            .includes(q.toLowerCase()),
        ),
    [list, q, cat, isAdmin],
  );
  const { paged, page, setPage, totalPages, total, pageSize, setPageSize } = usePagination(visible, 6);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["knowledge"] });

  const saveMut = useMutation({
    mutationFn: (article: KnowledgeArticle) =>
      article.id === "new"
        ? createArticle({ title: article.title, excerpt: article.excerpt, body: article.body, category: article.category, readTime: article.readTime, author: article.author, published: article.published, tags: article.tags })
        : updateArticle(article.id, { title: article.title, excerpt: article.excerpt, body: article.body, category: article.category, readTime: article.readTime, published: article.published, tags: article.tags }),
    onSuccess: (saved, article) => {
      invalidate();
      toast.success(article.id === "new" ? "Article créé" : "Article mis à jour");
      setEditing(null);
      if (opened && opened.id === article.id) setOpened(saved);
    },
    onError: () => toast.error("Erreur lors de l'enregistrement"),
  });

  const publishMut = useMutation({
    mutationFn: ({ id, published }: { id: string; published: boolean }) =>
      publishArticle(id, published),
    onSuccess: (saved, { published }) => {
      invalidate();
      toast.success(published ? "Article publié" : "Article dépublié");
      if (opened?.id === saved.id) setOpened(saved);
    },
    onError: () => toast.error("Erreur lors de la publication"),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteArticle(id),
    onSuccess: (_, id) => {
      invalidate();
      toast.success("Article supprimé");
      setConfirmDel(null);
      if (opened?.id === id) setOpened(null);
    },
    onError: () => toast.error("Erreur lors de la suppression"),
  });

  const save = () => {
    if (!editing) return;
    if (!editing.title.trim() || !editing.excerpt.trim()) {
      toast.error("Titre et extrait sont requis");
      return;
    }
    saveMut.mutate(editing);
  };

  const remove = (id: string) => deleteMut.mutate(id);

  const togglePublish = (a: KnowledgeArticle) =>
    publishMut.mutate({ id: a.id, published: !a.published });

  /* Reading view */
  if (opened) {
    return (
      <div className="mx-auto max-w-3xl space-y-5">
        <Button variant="ghost" size="sm" className="rounded-full" onClick={() => setOpened(null)}>
          <ArrowLeft className="mr-1 h-4 w-4" /> Retour
        </Button>
        <GlassCard strong className="space-y-4 p-7 sm:p-10">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-primary/10 px-2.5 py-1 font-medium text-primary">{opened.category}</span>
            <span className="text-muted-foreground inline-flex items-center gap-1">
              <Clock className="h-3 w-3" /> {opened.readTime} min
            </span>
            <span className="text-muted-foreground inline-flex items-center gap-1">
              <User className="h-3 w-3" /> {opened.author}
            </span>
            {!opened.published && (
              <span className="rounded-full bg-warning/20 px-2.5 py-1 font-medium text-warning-foreground dark:text-warning">
                Brouillon
              </span>
            )}
          </div>
          <h1 className="text-3xl font-bold tracking-tight">{opened.title}</h1>
          <p className="text-muted-foreground">{opened.excerpt}</p>
          {(opened.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {(opened.tags ?? []).map((tag) => (
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
          <div className="prose prose-sm max-w-none whitespace-pre-wrap text-foreground/90">
            {opened.body}
          </div>
          {isAdmin && (
            <div className="flex flex-wrap gap-2 border-t border-border/40 pt-4">
              <Button variant="outline" className="rounded-full" onClick={() => setEditing({ ...opened })}>
                <Edit3 className="mr-1 h-4 w-4" /> Modifier
              </Button>
              <Button variant="outline" className="rounded-full" onClick={() => togglePublish(opened)}>
                {opened.published ? <EyeOff className="mr-1 h-4 w-4" /> : <Eye className="mr-1 h-4 w-4" />}
                {opened.published ? "Dépublier" : "Publier"}
              </Button>
              <Button variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => setConfirmDel(opened)}>
                <Trash2 className="mr-1 h-4 w-4" /> Supprimer
              </Button>
            </div>
          )}
        </GlassCard>
        {editorDialog()}
        {deleteDialog()}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <BookOpen className="h-3 w-3" /> Ressources
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Base de connaissance
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Articles, procédures et guides EDG Support.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
          {isAdmin && (
            <Button
              onClick={() => setEditing(emptyArticle())}
              className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30"
            >
              <Plus className="mr-1 h-4 w-4" /> Nouvel article
            </Button>
          )}
        </div>
      </header>

      <GlassCard className="flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un article…" className="h-11 rounded-full pl-9" />
        </div>
        <Select value={cat} onValueChange={setCat}>
          <SelectTrigger className="h-11 w-full rounded-full sm:w-44"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes catégories</SelectItem>
            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
          </SelectContent>
        </Select>
      </GlassCard>

      {/* ── VUE GRILLE (2 colonnes) ── */}
      {layout === "grid" ? (
        <div className="grid gap-4 md:grid-cols-2">
          {paged.map((a) => (
            <GlassCard key={a.id} className={cn("group flex flex-col gap-3 transition hover:-translate-y-0.5", !a.published && "opacity-70")}>
              <div className="flex items-start gap-3">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-primary text-white">
                  <BookOpen className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    <span>{a.category}</span>· <span>{a.readTime} min</span>
                    {!a.published && (
                      <span className="rounded-full bg-warning/20 px-1.5 py-0.5 text-warning-foreground dark:text-warning">
                        Brouillon
                      </span>
                    )}
                  </div>
                  <button onClick={() => setOpened(a)} className="text-left text-base font-semibold hover:text-primary">
                    {a.title}
                  </button>
                  <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.excerpt}</p>
                  {(a.tags ?? []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {(a.tags ?? []).map((tag) => (
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
                </div>
              </div>
              {isAdmin && (
                <div className="flex justify-end gap-1.5 border-t border-border/40 pt-2">
                  <Button size="sm" variant="ghost" className="rounded-full" onClick={() => togglePublish(a)}>
                    {a.published ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </Button>
                  <Button size="sm" variant="ghost" className="rounded-full" onClick={() => setEditing({ ...a })}>
                    <Edit3 className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => setConfirmDel(a)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </GlassCard>
          ))}
          {visible.length === 0 && (
            <GlassCard className="md:col-span-2 py-12 text-center text-sm text-muted-foreground">
              Aucun article ne correspond à votre recherche.
            </GlassCard>
          )}
        </div>
      ) : (
        /* ── VUE LISTE (1 colonne, rangées horizontales) ── */
        <div className="space-y-2.5">
          {paged.map((a) => (
            <GlassCard
              key={a.id}
              className={cn(
                "group flex items-center gap-4 py-3 transition hover:-translate-y-0.5 hover:shadow-lg",
                !a.published && "opacity-70",
              )}
            >
              {/* Icône */}
              <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-primary text-white">
                <BookOpen className="h-4.5 w-4.5" />
              </div>

              {/* Contenu principal */}
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <button
                    onClick={() => setOpened(a)}
                    className="text-left font-semibold hover:text-primary"
                  >
                    {a.title}
                  </button>
                  {!a.published && (
                    <span className="rounded-full bg-warning/20 px-2 py-0.5 text-[10px] font-medium text-warning-foreground dark:text-warning">
                      Brouillon
                    </span>
                  )}
                </div>
                <p className="mt-0.5 line-clamp-1 text-sm text-muted-foreground">{a.excerpt}</p>
                {(a.tags ?? []).length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {(a.tags ?? []).map((tag) => (
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
              </div>

              {/* Méta droite */}
              <div className="flex shrink-0 items-center gap-3 text-[11px] text-muted-foreground">
                <span className="hidden rounded-full bg-primary/8 px-2.5 py-1 font-medium text-primary sm:inline">
                  {a.category}
                </span>
                <span className="flex items-center gap-1 hidden sm:flex">
                  <Clock className="h-3 w-3" /> {a.readTime} min
                </span>
                <span className="flex items-center gap-1 hidden sm:flex">
                  <User className="h-3 w-3" /> {a.author}
                </span>
              </div>

              {/* Actions admin */}
              {isAdmin && (
                <div className="flex shrink-0 items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                  <Button size="sm" variant="ghost" className="rounded-full" onClick={() => togglePublish(a)}>
                    {a.published ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                  </Button>
                  <Button size="sm" variant="ghost" className="rounded-full" onClick={() => setEditing({ ...a })}>
                    <Edit3 className="h-3.5 w-3.5" />
                  </Button>
                  <Button size="sm" variant="ghost" className="rounded-full text-destructive hover:bg-destructive/10" onClick={() => setConfirmDel(a)}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </GlassCard>
          ))}
          {visible.length === 0 && (
            <GlassCard className="py-12 text-center text-sm text-muted-foreground">
              Aucun article ne correspond à votre recherche.
            </GlassCard>
          )}
        </div>
      )}

      <PaginationBar
        page={page}
        totalPages={totalPages}
        total={total}
        pageSize={pageSize}
        onChange={setPage}
          onPageSizeChange={setPageSize}
      />



      {editorDialog()}
      {deleteDialog()}
    </div>
  );

  function editorDialog() {
    return (
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{editing?.id === "new" ? "Nouvel article" : "Modifier l'article"}</DialogTitle>
          </DialogHeader>
          {editing && (
            <div className="space-y-4 py-2">
              <div className="grid gap-2">
                <Label>Titre</Label>
                <Input value={editing.title} onChange={(e) => setEditing({ ...editing, title: e.target.value })} placeholder="Ex. Réinitialiser son accès SAP" />
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="grid gap-2 col-span-2">
                  <Label>Catégorie</Label>
                  <Select value={editing.category} onValueChange={(v) => setEditing({ ...editing, category: v })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2">
                  <Label>Lecture (min)</Label>
                  <Input type="number" min={1} placeholder="Ex. 3" value={editing.readTime} onChange={(e) => setEditing({ ...editing, readTime: Number(e.target.value) })} />
                </div>
              </div>
              <div className="grid gap-2">
                <Label>Extrait</Label>
                <Textarea rows={2} value={editing.excerpt} onChange={(e) => setEditing({ ...editing, excerpt: e.target.value })} placeholder="Résumé court affiché dans la liste" />
              </div>
              <div className="grid gap-2">
                <Label>Contenu</Label>
                <Textarea rows={8} value={editing.body} onChange={(e) => setEditing({ ...editing, body: e.target.value })} placeholder="Corps de l'article (texte simple)" />
              </div>
              <div className="grid gap-2">
                <Label className="flex items-center gap-1.5">
                  <Tag className="h-3.5 w-3.5" />
                  Tags
                </Label>
                <Input
                  value={(editing.tags ?? []).join(", ")}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      tags: e.target.value
                        .split(",")
                        .map((t) => t.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="Ex. SAP, accès, réinitialisation"
                />
                <p className="text-xs text-muted-foreground">Séparés par des virgules</p>
              </div>
              <div className="flex items-center justify-between rounded-xl bg-card/60 p-3">
                <div>
                  <Label className="m-0">Publié</Label>
                  <p className="text-xs text-muted-foreground">Visible par tous les utilisateurs</p>
                </div>
                <Switch checked={editing.published} onCheckedChange={(v) => setEditing({ ...editing, published: v })} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditing(null)}>Annuler</Button>
            <Button className="gradient-primary text-background" onClick={save}>Enregistrer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }

  function deleteDialog() {
    return (
      <Dialog open={!!confirmDel} onOpenChange={(o) => !o && setConfirmDel(null)}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Supprimer cet article ?</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            « {confirmDel?.title} » sera définitivement supprimé.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmDel(null)}>Annuler</Button>
            <Button variant="destructive" onClick={() => confirmDel && remove(confirmDel.id)}>Supprimer</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }
}
