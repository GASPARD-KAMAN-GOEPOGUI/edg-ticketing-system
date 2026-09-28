import { createFileRoute, Link } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { DEFAULT_CONFIG, isSectionExpired } from "@/lib/homepage-config";
import type { HomepageConfig, SectionConfig } from "@/lib/homepage-config";
import {
  fetchHomepageConfig,
  saveHomepageConfigApi,
  resetHomepageConfigApi,
  createSectionApi,
  updateSectionByIdApi,
  deleteSectionApi,
  fetchAdminSlides,
  createSlideApi,
  updateSlideApi,
  deleteSlideApi,
} from "@/lib/api/homepage";
import type { HomepageSlide } from "@/lib/api/homepage";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import {
  Globe,
  ChevronUp,
  ChevronDown,
  Eye,
  EyeOff,
  RotateCcw,
  ExternalLink,
  Info,
  AlignLeft,
  Zap,
  ListChecks,
  Users,
  ShieldCheck,
  GripVertical,
  SaveIcon,
  Lock,
  Pencil,
  Trash2,
  Plus,
  Clock,
  AlertTriangle,
  Sparkles,
  ImageIcon,
  Link2,
  SlidersHorizontal,
} from "lucide-react";

export const Route = createFileRoute("/app/admin/homepage")({
  head: () => ({ meta: [{ title: "Page d'accueil — Admin EDG" }] }),
  component: HomepageAdminPage,
});

// ── Icône par section ─────────────────────────────────────────────────────────
const SECTION_ICONS: Record<string, React.ComponentType<{ className?: string }>> = {
  mission:    AlignLeft,
  services:   Zap,
  how:        ListChecks,
  "for-who":  Users,
  trust:      ShieldCheck,
};

// ── Helpers date ──────────────────────────────────────────────────────────────

function toDatetimeLocal(iso?: string | null): string {
  if (!iso) return "";
  // Slice to "YYYY-MM-DDTHH:MM"
  return iso.replace("Z", "").slice(0, 16);
}

function fromDatetimeLocal(value: string): string | null {
  if (!value) return null;
  return new Date(value).toISOString();
}

// ── Dialog : Modifier une section ─────────────────────────────────────────────

interface EditDialogProps {
  section: SectionConfig | null;
  missionText: string;
  onClose: () => void;
  onSaved: (config: HomepageConfig) => void;
}

function EditSectionDialog({ section, missionText, onClose, onSaved }: EditDialogProps) {
  const [title, setTitle] = useState(section?.title ?? "");
  const [content, setContent] = useState(section?.content ?? "");
  const [missionLocal, setMissionLocal] = useState(missionText);
  const [expiresAt, setExpiresAt] = useState(toDatetimeLocal(section?.expiresAt));

  useEffect(() => {
    if (section) {
      setTitle(section.title ?? "");
      setContent(section.content ?? "");
      setExpiresAt(toDatetimeLocal(section.expiresAt));
    }
    setMissionLocal(missionText);
  }, [section, missionText]);

  const mutation = useMutation({
    mutationFn: () => {
      if (!section || !section.dbId) throw new Error("ID section manquant");
      const payload: {
        title?: string;
        content?: string;
        mission_text?: string;
        expires_at?: string | null;
      } = { expires_at: fromDatetimeLocal(expiresAt) };
      if (section.isCustom && title.trim()) payload.title = title.trim();
      if (content.trim()) payload.content = content.trim();
      if (section.id === "mission") payload.mission_text = missionLocal;
      return updateSectionByIdApi(section.dbId, payload);
    },
    onSuccess: (config) => {
      onSaved(config);
      toast.success("Section mise à jour");
      onClose();
    },
    onError: () => toast.error("Erreur lors de la mise à jour"),
  });

  if (!section) return null;

  const isMission = section.id === "mission";
  const showTitle = section.isCustom;

  return (
    <Dialog open={!!section} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Pencil className="h-4 w-4 text-primary" />
            Modifier — {section.label}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {showTitle && (
            <div className="grid gap-1.5">
              <Label htmlFor="edit-title">Titre de la section</Label>
              <Input
                id="edit-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Titre affiché sur la page…"
              />
            </div>
          )}

          {isMission ? (
            <div className="grid gap-1.5">
              <Label htmlFor="edit-mission">Texte de la bande de mission</Label>
              <Textarea
                id="edit-mission"
                rows={4}
                className="resize-none text-sm"
                value={missionLocal}
                onChange={(e) => setMissionLocal(e.target.value)}
                placeholder="Texte de présentation de la plateforme…"
              />
              <p className="text-xs text-muted-foreground">{missionLocal.length} caractères</p>
            </div>
          ) : (
            <div className="grid gap-1.5">
              <Label htmlFor="edit-content">Contenu / Description</Label>
              <Textarea
                id="edit-content"
                rows={4}
                className="resize-none text-sm"
                value={content}
                onChange={(e) => setContent(e.target.value)}
                placeholder="Texte affiché dans cette section…"
              />
            </div>
          )}

          <div className="grid gap-1.5">
            <Label htmlFor="edit-expires" className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              Délai d'expiration (optionnel)
            </Label>
            <input
              id="edit-expires"
              type="datetime-local"
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              La section sera automatiquement masquée après cette date.
            </p>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            className="gradient-primary text-background"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            <SaveIcon className="h-4 w-4 mr-1.5" />
            {mutation.isPending ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Dialog : Ajouter une section ──────────────────────────────────────────────

interface AddDialogProps {
  open: boolean;
  onClose: () => void;
  onAdded: (config: HomepageConfig) => void;
}

function AddSectionDialog({ open, onClose, onAdded }: AddDialogProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [expiresAt, setExpiresAt] = useState("");
  const [visible, setVisible] = useState(true);

  const reset = () => {
    setTitle("");
    setContent("");
    setExpiresAt("");
    setVisible(true);
  };

  const mutation = useMutation({
    mutationFn: () => {
      if (!title.trim()) throw new Error("Titre requis");
      // Generate section_id from title: lowercase, replace spaces with dashes, strip specials
      const section_id = title
        .toLowerCase()
        .trim()
        .replace(/[^a-z0-9\s-]/g, "")
        .replace(/\s+/g, "-")
        .slice(0, 50)
        + `-${Date.now().toString(36)}`;
      return createSectionApi({
        section_id,
        title: title.trim(),
        content: content.trim() || undefined,
        visible,
        expires_at: fromDatetimeLocal(expiresAt),
      });
    },
    onSuccess: (config) => {
      onAdded(config);
      toast.success("Section ajoutée");
      reset();
      onClose();
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : "Erreur lors de l'ajout";
      toast.error(msg);
    },
  });

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) { reset(); onClose(); } }}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Plus className="h-4 w-4 text-primary" />
            Ajouter une section personnalisée
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="add-title">
              Titre <span className="text-destructive">*</span>
            </Label>
            <Input
              id="add-title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Ex : Information importante, Maintenance prévue…"
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="add-content">Contenu</Label>
            <Textarea
              id="add-content"
              rows={4}
              className="resize-none text-sm"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Texte affiché dans cette section sur la page d'accueil…"
            />
          </div>

          <div className="grid gap-1.5">
            <Label htmlFor="add-expires" className="flex items-center gap-2">
              <Clock className="h-3.5 w-3.5 text-muted-foreground" />
              Délai d'expiration (optionnel)
            </Label>
            <input
              id="add-expires"
              type="datetime-local"
              className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              value={expiresAt}
              onChange={(e) => setExpiresAt(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              La section disparaît automatiquement de la page publique à cette date.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Switch
              id="add-visible"
              checked={visible}
              onCheckedChange={setVisible}
            />
            <Label htmlFor="add-visible" className="cursor-pointer">
              Visible immédiatement
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => { reset(); onClose(); }}>
            Annuler
          </Button>
          <Button
            className="gradient-primary text-background"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !title.trim()}
          >
            <Plus className="h-4 w-4 mr-1.5" />
            {mutation.isPending ? "Ajout…" : "Ajouter"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Dialog : Confirmer suppression ────────────────────────────────────────────

interface DeleteDialogProps {
  section: SectionConfig | null;
  onClose: () => void;
  onDeleted: (config: HomepageConfig) => void;
}

function DeleteSectionDialog({ section, onClose, onDeleted }: DeleteDialogProps) {
  const mutation = useMutation({
    mutationFn: () => {
      if (!section?.dbId) throw new Error("ID manquant");
      return deleteSectionApi(section.dbId);
    },
    onSuccess: (config) => {
      onDeleted(config);
      toast.success("Section supprimée");
      onClose();
    },
    onError: () => toast.error("Erreur lors de la suppression"),
  });

  return (
    <Dialog open={!!section} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            Supprimer la section
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground py-2">
          Êtes-vous sûr de vouloir supprimer <strong>"{section?.label}"</strong> ?
          Cette action est irréversible.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant="destructive"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            <Trash2 className="h-4 w-4 mr-1.5" />
            {mutation.isPending ? "Suppression…" : "Supprimer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Dialog : Créer / Modifier un slide ───────────────────────────────────────

interface SlideFormDialogProps {
  slide: HomepageSlide | null;
  open: boolean;
  onClose: () => void;
  onSaved: () => void;
}

function SlideFormDialog({ slide, open, onClose, onSaved }: SlideFormDialogProps) {
  const isEdit = !!slide;
  const [title,     setTitle]     = useState(slide?.title ?? "");
  const [message,   setMessage]   = useState(slide?.message ?? "");
  const [ctaLabel,  setCtaLabel]  = useState(slide?.cta_label ?? "");
  const [ctaUrl,    setCtaUrl]    = useState(slide?.cta_url ?? "");
  const [imageUrl,  setImageUrl]  = useState(slide?.image_url ?? "");
  const [sortOrder, setSortOrder] = useState(String(slide?.sort_order ?? 0));
  const [visible,   setVisible]   = useState(slide?.visible ?? true);
  const [startsAt,  setStartsAt]  = useState(toDatetimeLocal(slide?.starts_at));
  const [endsAt,    setEndsAt]    = useState(toDatetimeLocal(slide?.ends_at));

  useEffect(() => {
    if (open) {
      setTitle(slide?.title ?? "");
      setMessage(slide?.message ?? "");
      setCtaLabel(slide?.cta_label ?? "");
      setCtaUrl(slide?.cta_url ?? "");
      setImageUrl(slide?.image_url ?? "");
      setSortOrder(String(slide?.sort_order ?? 0));
      setVisible(slide?.visible ?? true);
      setStartsAt(toDatetimeLocal(slide?.starts_at));
      setEndsAt(toDatetimeLocal(slide?.ends_at));
    }
  }, [open, slide]);

  const mutation = useMutation({
    mutationFn: () => {
      const data = {
        title: title.trim() || null,
        message: message.trim() || null,
        cta_label: ctaLabel.trim() || null,
        cta_url: ctaUrl.trim() || null,
        image_url: imageUrl.trim() || null,
        sort_order: parseInt(sortOrder, 10) || 0,
        visible,
        starts_at: fromDatetimeLocal(startsAt),
        ends_at: fromDatetimeLocal(endsAt),
      };
      return isEdit && slide
        ? updateSlideApi(slide.id, data)
        : createSlideApi(data);
    },
    onSuccess: () => {
      onSaved();
      onClose();
      toast.success(isEdit ? "Slide mis à jour" : "Slide créé");
    },
    onError: () => toast.error("Erreur lors de l'enregistrement"),
  });

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg max-h-[90dvh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <SlidersHorizontal className="h-4 w-4 text-primary" />
            {isEdit ? "Modifier le slide" : "Nouveau slide"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="grid gap-1.5">
            <Label htmlFor="sl-title">Titre</Label>
            <Input id="sl-title" value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="Titre du slide…" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="sl-message">Message</Label>
            <Textarea id="sl-message" rows={3} className="resize-none text-sm"
              value={message} onChange={(e) => setMessage(e.target.value)}
              placeholder="Description courte affichée sous le titre…" />
          </div>
          <div className="grid gap-1.5">
            <Label htmlFor="sl-image" className="flex items-center gap-2">
              <ImageIcon className="h-3.5 w-3.5 text-muted-foreground" />
              URL de l'image (optionnelle)
            </Label>
            <Input id="sl-image" value={imageUrl} onChange={(e) => setImageUrl(e.target.value)}
              placeholder="https://…" type="url" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="sl-cta-label" className="flex items-center gap-2">
                <Link2 className="h-3.5 w-3.5 text-muted-foreground" />
                Texte du bouton CTA
              </Label>
              <Input id="sl-cta-label" value={ctaLabel} onChange={(e) => setCtaLabel(e.target.value)}
                placeholder="Ex : En savoir plus" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="sl-cta-url">URL du bouton CTA</Label>
              <Input id="sl-cta-url" value={ctaUrl} onChange={(e) => setCtaUrl(e.target.value)}
                placeholder="https://… ou /chemin" />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="sl-starts" className="flex items-center gap-2">
                <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                Début de diffusion
              </Label>
              <input id="sl-starts" type="datetime-local"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="sl-ends">Fin de diffusion</Label>
              <input id="sl-ends" type="datetime-local"
                className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                value={endsAt} onChange={(e) => setEndsAt(e.target.value)} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="sl-order">Ordre d'affichage</Label>
              <Input id="sl-order" type="number" min={0} value={sortOrder}
                onChange={(e) => setSortOrder(e.target.value)} />
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Switch id="sl-visible" checked={visible} onCheckedChange={setVisible} />
            <Label htmlFor="sl-visible" className="cursor-pointer">Visible sur la page d'accueil</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button className="gradient-primary text-background"
            onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <SaveIcon className="h-4 w-4 mr-1.5" />
            {mutation.isPending ? "Enregistrement…" : "Enregistrer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Dialog : Confirmer suppression d'un slide ─────────────────────────────────

function DeleteSlideDialog({
  slide,
  onClose,
  onDeleted,
}: {
  slide: HomepageSlide | null;
  onClose: () => void;
  onDeleted: () => void;
}) {
  const mutation = useMutation({
    mutationFn: () => {
      if (!slide) throw new Error("slide manquant");
      return deleteSlideApi(slide.id);
    },
    onSuccess: () => {
      onDeleted();
      onClose();
      toast.success("Slide supprimé");
    },
    onError: () => toast.error("Erreur lors de la suppression"),
  });
  return (
    <Dialog open={!!slide} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-sm">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-destructive">
            <AlertTriangle className="h-4 w-4" />
            Supprimer le slide
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground py-2">
          Êtes-vous sûr de vouloir supprimer <strong>"{slide?.title ?? "ce slide"}"</strong> ?
          Cette action est irréversible.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>Annuler</Button>
          <Button variant="destructive" onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            <Trash2 className="h-4 w-4 mr-1.5" />
            {mutation.isPending ? "Suppression…" : "Supprimer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ── Page principale ───────────────────────────────────────────────────────────

function HomepageAdminPage() {
  const queryClient = useQueryClient();

  const { data: serverConfig } = useQuery({
    queryKey: ["homepage-config"],
    queryFn: () => fetchHomepageConfig(),
    staleTime: 60_000,
  });

  const [config, setConfig] = useState<HomepageConfig>(DEFAULT_CONFIG);
  const [dirty, setDirty] = useState(false);
  const [editingSection, setEditingSection] = useState<SectionConfig | null>(null);
  const [addingSection, setAddingSection] = useState(false);
  const [deletingSection, setDeletingSection] = useState<SectionConfig | null>(null);

  // ── Slides ────────────────────────────────────────────────────────────────
  const slidesQuery = useQuery({
    queryKey: ["homepage-slides-admin"],
    queryFn: fetchAdminSlides,
    staleTime: 30_000,
  });
  const slides = slidesQuery.data ?? [];
  const [editingSlide, setEditingSlide] = useState<HomepageSlide | null>(null);
  const [addingSlide, setAddingSlide] = useState(false);
  const [deletingSlide, setDeletingSlide] = useState<HomepageSlide | null>(null);

  const refreshSlides = () => {
    queryClient.invalidateQueries({ queryKey: ["homepage-slides-admin"] });
    queryClient.invalidateQueries({ queryKey: ["homepage-slides"] });
  };

  useEffect(() => {
    if (serverConfig) {
      setConfig(serverConfig);
      setDirty(false);
    }
  }, [serverConfig]);

  const applyServerConfig = (newConfig: HomepageConfig) => {
    queryClient.setQueryData(["homepage-config"], newConfig);
    setConfig(newConfig);
    setDirty(false);
  };

  const saveMutation = useMutation({
    mutationFn: () => saveHomepageConfigApi(config),
    onSuccess: (data) => {
      applyServerConfig(data);
      toast.success("Configuration enregistrée", {
        description: "La page d'accueil a été mise à jour.",
      });
    },
    onError: () => toast.error("Erreur lors de l'enregistrement"),
  });

  const resetMutation = useMutation({
    mutationFn: resetHomepageConfigApi,
    onSuccess: (data) => {
      applyServerConfig(data);
      toast.success("Configuration réinitialisée");
    },
    onError: () => toast.error("Erreur lors de la réinitialisation"),
  });

  const updateSection = (id: string, patch: Partial<SectionConfig>) => {
    setConfig((c) => ({
      ...c,
      sections: c.sections.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    }));
    setDirty(true);
  };

  const move = (id: string, dir: -1 | 1) => {
    setConfig((c) => {
      const sorted = [...c.sections].sort((a, b) => a.order - b.order);
      const idx = sorted.findIndex((s) => s.id === id);
      const target = idx + dir;
      if (target < 0 || target >= sorted.length) return c;
      const newSections = sorted.map((s, i) => {
        if (i === idx) return { ...s, order: sorted[target].order };
        if (i === target) return { ...s, order: sorted[idx].order };
        return s;
      });
      return { ...c, sections: newSections };
    });
    setDirty(true);
  };

  const sorted = [...config.sections].sort((a, b) => a.order - b.order);
  const visibleCount = config.sections.filter((s) => s.visible).length;
  const expiredCount = config.sections.filter((s) => isSectionExpired(s.expiresAt)).length;
  const missionSection = config.sections.find((s) => s.id === "mission");

  return (
    <div className="mx-auto max-w-3xl space-y-6">

      {/* ── En-tête ── */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Globe className="h-3 w-3" /> Administration
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Page d'accueil publique
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Ajoutez, modifiez, supprimez ou planifiez des sections.
          </p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="outline" className="rounded-full gap-2">
            <Link to="/" target="_blank" rel="noopener">
              <ExternalLink className="h-4 w-4" />
              Prévisualiser
            </Link>
          </Button>
          <Button
            className="rounded-full gap-2 gradient-primary text-background"
            onClick={() => setAddingSection(true)}
          >
            <Plus className="h-4 w-4" />
            Ajouter
          </Button>
        </div>
      </header>

      {/* ── Résumé ── */}
      <div className="grid gap-3 sm:grid-cols-3">
        <GlassCard className="flex items-center gap-3 py-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-primary/10">
            <Eye className="h-4 w-4 text-primary" />
          </div>
          <div>
            <div className="text-xl font-bold">{visibleCount}</div>
            <div className="text-xs text-muted-foreground">Sections visibles</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-3 py-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-muted">
            <EyeOff className="h-4 w-4 text-muted-foreground" />
          </div>
          <div>
            <div className="text-xl font-bold">{config.sections.length - visibleCount}</div>
            <div className="text-xs text-muted-foreground">Masquées</div>
          </div>
        </GlassCard>
        <GlassCard className="flex items-center gap-3 py-3">
          <div className={cn(
            "grid h-9 w-9 shrink-0 place-items-center rounded-xl",
            expiredCount > 0 ? "bg-warning/10" : "bg-muted"
          )}>
            <Clock className={cn("h-4 w-4", expiredCount > 0 ? "text-warning-foreground dark:text-warning" : "text-muted-foreground")} />
          </div>
          <div>
            <div className="text-xl font-bold">{expiredCount}</div>
            <div className="text-xs text-muted-foreground">Expirées</div>
          </div>
        </GlassCard>
      </div>

      {/* ── Note Hero ── */}
      <div className="flex items-start gap-2 rounded-xl border border-info/20 bg-info/5 px-4 py-3 text-sm text-info">
        <Info className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Le <strong>Hero</strong> (titre, CTA principal, maquette animée) est toujours affiché —
          il constitue l'identité visuelle de la page. Seules les sections ci-dessous sont configurables.
        </span>
      </div>

      {/* ── Liste des sections ── */}
      <GlassCard className="overflow-hidden p-0">
        <div className="border-b border-border/40 px-5 py-3.5">
          <h2 className="text-sm font-semibold">Sections configurables</h2>
          <p className="text-xs text-muted-foreground">
            Activez, réordonnez, modifiez ou supprimez les sections.
          </p>
        </div>

        <ul className="divide-y divide-border/40">
          {sorted.map((section, idx) => {
            const Icon = SECTION_ICONS[section.id] ?? Sparkles;
            const isFirst = idx === 0;
            const isLast = idx === sorted.length - 1;
            const expired = isSectionExpired(section.expiresAt);

            return (
              <li
                key={section.id}
                className={cn(
                  "flex items-start gap-4 px-5 py-4 transition-colors",
                  !section.visible && "opacity-55",
                )}
              >
                {/* Handle décoratif */}
                <GripVertical className="mt-1 h-4 w-4 shrink-0 text-muted-foreground/40" aria-hidden />

                {/* Icône */}
                <div
                  className={cn(
                    "mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl transition",
                    expired ? "bg-warning/10" :
                    section.visible ? "bg-primary/10" : "bg-muted",
                  )}
                >
                  <Icon className={cn(
                    "h-4 w-4",
                    expired ? "text-warning-foreground dark:text-warning" :
                    section.visible ? "text-primary" : "text-muted-foreground",
                  )} />
                </div>

                {/* Infos */}
                <div className="min-w-0 flex-1 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium leading-tight">{section.label}</span>
                    {section.isCustom && (
                      <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold text-accent-foreground dark:text-accent">
                        Personnalisée
                      </span>
                    )}
                    {!section.isCustom && !section.editable && (
                      <span className="flex items-center gap-1 rounded-full bg-muted/80 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
                        <Lock className="h-2.5 w-2.5" /> Intégrée
                      </span>
                    )}
                    {expired && (
                      <span className="flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] font-semibold text-warning-foreground dark:text-warning">
                        <Clock className="h-2.5 w-2.5" /> Expirée
                      </span>
                    )}
                    {section.expiresAt && !expired && (
                      <span className="flex items-center gap-1 rounded-full bg-info/10 px-2 py-0.5 text-[10px] font-medium text-info">
                        <Clock className="h-2.5 w-2.5" />
                        Expire le {new Date(section.expiresAt).toLocaleDateString("fr-FR")}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">{section.desc}</p>

                  {/* Actions */}
                  <div className="flex flex-wrap gap-1 pt-1">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 rounded-lg px-2 text-xs"
                      disabled={isFirst}
                      onClick={() => move(section.id, -1)}
                      aria-label="Monter"
                    >
                      <ChevronUp className="h-3.5 w-3.5" />
                      Monter
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 rounded-lg px-2 text-xs"
                      disabled={isLast}
                      onClick={() => move(section.id, 1)}
                      aria-label="Descendre"
                    >
                      <ChevronDown className="h-3.5 w-3.5" />
                      Descendre
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 rounded-lg px-2 text-xs text-primary hover:text-primary"
                      onClick={() => setEditingSection(section)}
                      aria-label="Modifier"
                    >
                      <Pencil className="h-3.5 w-3.5" />
                      Modifier
                    </Button>
                    {section.isCustom && (
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 rounded-lg px-2 text-xs text-destructive hover:text-destructive"
                        onClick={() => setDeletingSection(section)}
                        aria-label="Supprimer"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        Supprimer
                      </Button>
                    )}
                  </div>
                </div>

                {/* Switch visibilité */}
                <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
                  <Switch
                    checked={section.visible}
                    onCheckedChange={(v) => updateSection(section.id, { visible: v })}
                    aria-label={`${section.visible ? "Masquer" : "Afficher"} ${section.label}`}
                  />
                  <span className={cn(
                    "text-[10px] font-medium",
                    section.visible ? "text-success" : "text-muted-foreground",
                  )}>
                    {section.visible ? "Visible" : "Masquée"}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      </GlassCard>

      {/* ── Actions ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-border/40 bg-background/40 px-4 py-3 backdrop-blur">
        <Button
          variant="outline"
          className="gap-2 rounded-xl border-destructive/40 text-destructive hover:bg-destructive/10"
          onClick={() => resetMutation.mutate()}
          disabled={resetMutation.isPending}
        >
          <RotateCcw className="h-4 w-4" />
          Réinitialiser
        </Button>

        <div className="flex items-center gap-3">
          {dirty && (
            <span className="text-xs text-warning-foreground dark:text-amber-400">
              Modifications d'ordre/visibilité non sauvegardées
            </span>
          )}
          <Button
            className="gap-2 rounded-xl gradient-primary text-background shadow-md shadow-primary/30"
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !dirty}
          >
            <SaveIcon className="h-4 w-4" />
            {saveMutation.isPending ? "Enregistrement…" : "Enregistrer l'ordre"}
          </Button>
        </div>
      </div>

      {/* ── Slides du carrousel ── */}
      <GlassCard className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-border/40 px-5 py-3.5">
          <div>
            <h2 className="text-sm font-semibold flex items-center gap-2">
              <SlidersHorizontal className="h-4 w-4 text-primary" />
              Slides du carrousel d'accueil
            </h2>
            <p className="text-xs text-muted-foreground">
              Affiché juste sous le hero — disparaît si aucun slide actif.
            </p>
          </div>
          <Button
            size="sm"
            className="gap-1.5 rounded-xl gradient-primary text-background"
            onClick={() => setAddingSlide(true)}
          >
            <Plus className="h-3.5 w-3.5" />
            Nouveau slide
          </Button>
        </div>

        {slidesQuery.isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">Chargement…</div>
        ) : slides.length === 0 ? (
          <div className="px-5 py-8 text-center text-sm text-muted-foreground">
            Aucun slide — cliquez sur <strong>Nouveau slide</strong> pour en créer un.
          </div>
        ) : (
          <ul className="divide-y divide-border/40">
            {[...slides].sort((a, b) => a.sort_order - b.sort_order).map((s) => {
              const now = new Date();
              const active =
                s.visible &&
                (!s.starts_at || new Date(s.starts_at) <= now) &&
                (!s.ends_at || new Date(s.ends_at) > now);
              return (
                <li key={s.id} className={cn("flex items-start gap-4 px-5 py-4", !s.visible && "opacity-55")}>
                  <div className={cn(
                    "mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl",
                    active ? "bg-primary/10" : "bg-muted",
                  )}>
                    {s.image_url
                      ? <ImageIcon className={cn("h-4 w-4", active ? "text-primary" : "text-muted-foreground")} />
                      : <SlidersHorizontal className={cn("h-4 w-4", active ? "text-primary" : "text-muted-foreground")} />
                    }
                  </div>
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium leading-tight">{s.title ?? "(Sans titre)"}</span>
                      <span className="rounded-full bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground">
                        Ordre {s.sort_order}
                      </span>
                      {active && (
                        <span className="rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">
                          Actif
                        </span>
                      )}
                      {s.ends_at && new Date(s.ends_at) <= now && (
                        <span className="flex items-center gap-1 rounded-full bg-warning/15 px-2 py-0.5 text-[10px] text-warning-foreground">
                          <Clock className="h-2.5 w-2.5" /> Expiré
                        </span>
                      )}
                    </div>
                    {s.message && (
                      <p className="text-xs text-muted-foreground line-clamp-2">{s.message}</p>
                    )}
                    {s.cta_label && (
                      <p className="text-xs text-primary flex items-center gap-1">
                        <Link2 className="h-3 w-3" /> {s.cta_label}
                      </p>
                    )}
                    <div className="flex gap-1 pt-1">
                      <Button size="sm" variant="ghost" className="h-7 rounded-lg px-2 text-xs text-primary hover:text-primary"
                        onClick={() => setEditingSlide(s)}>
                        <Pencil className="h-3.5 w-3.5" /> Modifier
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 rounded-lg px-2 text-xs text-destructive hover:text-destructive"
                        onClick={() => setDeletingSlide(s)}>
                        <Trash2 className="h-3.5 w-3.5" /> Supprimer
                      </Button>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1.5 pt-0.5">
                    <Switch
                      checked={s.visible}
                      onCheckedChange={(v) => {
                        updateSlideApi(s.id, { visible: v })
                          .then(refreshSlides)
                          .catch(() => toast.error("Erreur"));
                      }}
                      aria-label={`${s.visible ? "Masquer" : "Afficher"} le slide`}
                    />
                    <span className={cn("text-[10px] font-medium", s.visible ? "text-success" : "text-muted-foreground")}>
                      {s.visible ? "Visible" : "Masqué"}
                    </span>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </GlassCard>

      {/* ── Dialogs slides ── */}
      <SlideFormDialog
        slide={editingSlide}
        open={!!editingSlide}
        onClose={() => setEditingSlide(null)}
        onSaved={refreshSlides}
      />
      <SlideFormDialog
        slide={null}
        open={addingSlide}
        onClose={() => setAddingSlide(false)}
        onSaved={refreshSlides}
      />
      <DeleteSlideDialog
        slide={deletingSlide}
        onClose={() => setDeletingSlide(null)}
        onDeleted={refreshSlides}
      />

      {/* ── Dialogs ── */}
      <EditSectionDialog
        section={editingSection}
        missionText={config.missionText}
        onClose={() => setEditingSection(null)}
        onSaved={(cfg) => {
          applyServerConfig(cfg);
          setEditingSection(null);
        }}
      />

      <AddSectionDialog
        open={addingSection}
        onClose={() => setAddingSection(false)}
        onAdded={(cfg) => {
          applyServerConfig(cfg);
          setAddingSection(false);
        }}
      />

      <DeleteSectionDialog
        section={deletingSection}
        onClose={() => setDeletingSection(null)}
        onDeleted={(cfg) => {
          applyServerConfig(cfg);
          setDeletingSection(null);
        }}
      />
    </div>
  );
}
