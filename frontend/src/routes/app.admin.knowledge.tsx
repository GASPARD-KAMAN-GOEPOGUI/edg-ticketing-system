import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchArticles,
  createArticle,
  updateArticle,
  publishArticle,
  deleteArticle,
} from "@/lib/api/knowledge";
import type { KnowledgeArticle } from "@/lib/mock-data";
import { toast } from "sonner";
import { Library, Plus, Pencil, Trash2, Search, Eye, EyeOff, Clock } from "lucide-react";
import { cn } from "@/lib/utils";

const KNOWLEDGE_CATEGORIES = [
  { id: "general", label: "Général" },
  { id: "pannes", label: "Pannes & Incidents" },
  { id: "facturation", label: "Facturation" },
  { id: "compteurs", label: "Compteurs & Relevés" },
  { id: "branchements", label: "Branchements" },
  { id: "procedures", label: "Procédures" },
  { id: "faq", label: "FAQ" },
  { id: "securite", label: "Sécurité" },
] as const;

export const Route = createFileRoute("/app/admin/knowledge")({
  head: () => ({ meta: [{ title: "Base de connaissances — Admin EDG" }] }),
  component: AdminKnowledge,
});

type ArticleForm = {
  title: string;
  excerpt: string;
  body: string;
  category: string;
  readTime: number;
  author: string;
  published: boolean;
  tags: string;
};

const emptyForm = (): ArticleForm => ({
  title: "",
  excerpt: "",
  body: "",
  category: KNOWLEDGE_CATEGORIES[0]?.id ?? "general",
  readTime: 5,
  author: "",
  published: false,
  tags: "",
});

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString("fr-FR", { day: "2-digit", month: "short", year: "numeric" });
}

function AdminKnowledge() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [catFilter, setCatFilter] = useState("all");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<KnowledgeArticle | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<KnowledgeArticle | null>(null);
  const [form, setForm] = useState<ArticleForm>(emptyForm());

  const { data, isLoading } = useQuery({
    queryKey: ["knowledge", "admin"],
    queryFn: () => fetchArticles({ limit: 100 }),
  });
  const articles: KnowledgeArticle[] = data?.items ?? [];

  const invalidate = () => qc.invalidateQueries({ queryKey: ["knowledge"] });

  const createMut = useMutation({
    mutationFn: (f: ArticleForm) =>
      createArticle({
        title: f.title,
        excerpt: f.excerpt,
        body: f.body,
        category: f.category,
        readTime: f.readTime,
        author: f.author,
        published: f.published,
        tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
      }),
    onSuccess: () => { invalidate(); setSheetOpen(false); toast.success("Article créé."); },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, f }: { id: string; f: ArticleForm }) =>
      updateArticle(id, {
        title: f.title,
        excerpt: f.excerpt,
        body: f.body,
        category: f.category,
        readTime: f.readTime,
        author: f.author,
        tags: f.tags.split(",").map((t) => t.trim()).filter(Boolean),
      }),
    onSuccess: () => { invalidate(); setSheetOpen(false); toast.success("Article mis à jour."); },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const publishMut = useMutation({
    mutationFn: ({ id, published }: { id: string; published: boolean }) =>
      publishArticle(id, published),
    onSuccess: (_, { published }) => {
      invalidate();
      toast.success(published ? "Article publié." : "Article dépublié.");
    },
    onError: () => toast.error("Erreur lors du changement de statut."),
  });

  const deleteMut = useMutation({
    mutationFn: deleteArticle,
    onSuccess: () => { invalidate(); setDeleteTarget(null); toast.success("Article supprimé."); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  const filtered = articles.filter((a) => {
    const matchQ = !q || `${a.title} ${a.author} ${a.excerpt}`.toLowerCase().includes(q.toLowerCase());
    const matchCat = catFilter === "all" || a.category === catFilter;
    return matchQ && matchCat;
  });

  function openCreate() { setForm(emptyForm()); setEditTarget(null); setSheetOpen(true); }
  function openEdit(a: KnowledgeArticle) {
    setForm({
      title: a.title,
      excerpt: a.excerpt,
      body: a.body,
      category: a.category,
      readTime: a.readTime,
      author: a.author,
      published: a.published,
      tags: a.tags?.join(", ") ?? "",
    });
    setEditTarget(a);
    setSheetOpen(true);
  }

  function validate() {
    if (!form.title.trim()) { toast.error("Le titre est requis."); return false; }
    if (!form.author.trim()) { toast.error("L'auteur est requis."); return false; }
    return true;
  }

  function submit() {
    if (!validate()) return;
    if (editTarget) {
      updateMut.mutate({ id: editTarget.id, f: form });
    } else {
      createMut.mutate(form);
    }
  }

  const catLabels = Object.fromEntries(KNOWLEDGE_CATEGORIES.map((c) => [c.id, c.label]));

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Library className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Base de connaissances</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Créez et gérez les articles disponibles pour les utilisateurs EDG Support.
          </p>
        </div>
        <Button className="gradient-primary rounded-full" onClick={openCreate}>
          <Plus className="mr-2 h-4 w-4" /> Nouvel article
        </Button>
      </header>

      {/* Stats */}
      <div className="grid gap-3 sm:grid-cols-3">
        <GlassCard className="py-4">
          <div className="text-sm text-muted-foreground">Total articles</div>
          <div className="mt-1 text-2xl font-bold">{articles.length}</div>
        </GlassCard>
        <GlassCard className="py-4">
          <div className="text-sm text-muted-foreground">Publiés</div>
          <div className="mt-1 text-2xl font-bold text-success">{articles.filter((a) => a.published).length}</div>
        </GlassCard>
        <GlassCard className="py-4">
          <div className="text-sm text-muted-foreground">Brouillons</div>
          <div className="mt-1 text-2xl font-bold text-muted-foreground">{articles.filter((a) => !a.published).length}</div>
        </GlassCard>
      </div>

      {/* Filters */}
      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="relative min-w-0 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Titre, auteur…" className="h-10 rounded-full pl-9" />
        </div>
        <Select value={catFilter} onValueChange={setCatFilter}>
          <SelectTrigger className="h-10 w-full rounded-full sm:w-48"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes catégories</SelectItem>
            {KNOWLEDGE_CATEGORIES.map((c) => (
              <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </GlassCard>

      {/* List */}
      {isLoading ? (
        <div className="py-16 text-center text-sm text-muted-foreground">Chargement…</div>
      ) : (
        <div className="space-y-3">
          {filtered.map((a) => (
            <GlassCard key={a.id} className="flex items-start gap-4 p-4">
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider",
                    a.published ? "bg-success/15 text-success" : "bg-muted text-muted-foreground",
                  )}>
                    {a.published ? "Publié" : "Brouillon"}
                  </span>
                  <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                    {catLabels[a.category] ?? a.category}
                  </span>
                </div>
                <h3 className="mt-1 font-semibold leading-snug">{a.title}</h3>
                <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{a.excerpt}</p>
                <div className="mt-2 flex items-center gap-3 text-xs text-muted-foreground">
                  <span>{a.author}</span>
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {a.readTime} min
                  </span>
                  <span>{fmtDate(a.updatedAt)}</span>
                </div>
              </div>
              <div className="flex shrink-0 gap-1">
                <Button
                  size="icon"
                  variant="ghost"
                  className={cn("h-8 w-8", a.published ? "text-warning-foreground" : "text-success")}
                  title={a.published ? "Dépublier" : "Publier"}
                  onClick={() => publishMut.mutate({ id: a.id, published: !a.published })}
                  disabled={publishMut.isPending}
                >
                  {a.published ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </Button>
                <Button size="icon" variant="ghost" className="h-8 w-8" onClick={() => openEdit(a)}>
                  <Pencil className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-destructive hover:text-destructive"
                  onClick={() => setDeleteTarget(a)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </GlassCard>
          ))}
          {filtered.length === 0 && (
            <div className="py-16 text-center text-sm text-muted-foreground">Aucun article trouvé.</div>
          )}
        </div>
      )}

      {/* Article editor sheet */}
      <Sheet open={sheetOpen} onOpenChange={(o) => !o && setSheetOpen(false)}>
        <SheetContent className="flex w-full flex-col gap-0 overflow-y-auto sm:max-w-2xl">
          <SheetHeader className="px-6 py-4 border-b">
            <SheetTitle>{editTarget ? "Modifier l'article" : "Nouvel article"}</SheetTitle>
          </SheetHeader>
          <div className="flex-1 space-y-4 overflow-y-auto p-6">
            <div className="space-y-1.5">
              <Label>Titre <span className="text-destructive">*</span></Label>
              <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Titre de l'article" />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Catégorie</Label>
                <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {KNOWLEDGE_CATEGORIES.map((c) => (
                      <SelectItem key={c.id} value={c.id}>{c.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Auteur <span className="text-destructive">*</span></Label>
                <Input value={form.author} onChange={(e) => setForm({ ...form, author: e.target.value })} placeholder="Nom de l'auteur" />
              </div>
              <div className="space-y-1.5">
                <Label>Temps de lecture (min)</Label>
                <Input
                  type="number"
                  min={1}
                  value={form.readTime}
                  onChange={(e) => setForm({ ...form, readTime: Number(e.target.value) })}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Tags (séparés par des virgules)</Label>
                <Input value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} placeholder="tag1, tag2" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Résumé</Label>
              <Textarea
                value={form.excerpt}
                onChange={(e) => setForm({ ...form, excerpt: e.target.value })}
                placeholder="Courte description de l'article…"
                rows={2}
              />
            </div>
            <div className="space-y-1.5">
              <Label>Contenu</Label>
              <Textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                placeholder="Corps de l'article (Markdown supporté)…"
                rows={10}
                className="font-mono text-sm"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 border-t p-4">
            <Button variant="outline" onClick={() => setSheetOpen(false)}>Annuler</Button>
            <Button
              variant="outline"
              onClick={() => { setForm({ ...form, published: false }); setTimeout(submit, 0); }}
              disabled={createMut.isPending || updateMut.isPending}
            >
              Enregistrer comme brouillon
            </Button>
            <Button
              className="gradient-primary"
              onClick={() => { setForm((prev) => ({ ...prev, published: true })); setTimeout(submit, 0); }}
              disabled={createMut.isPending || updateMut.isPending}
            >
              {createMut.isPending || updateMut.isPending ? "Enregistrement…" : "Publier"}
            </Button>
          </div>
        </SheetContent>
      </Sheet>

      {/* Delete confirm */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Supprimer cet article ?</AlertDialogTitle>
            <AlertDialogDescription>
              <strong>{deleteTarget?.title}</strong> sera définitivement supprimé.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
              onClick={() => deleteTarget && deleteMut.mutate(deleteTarget.id)}
              disabled={deleteMut.isPending}
            >
              {deleteMut.isPending ? "Suppression…" : "Supprimer"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
