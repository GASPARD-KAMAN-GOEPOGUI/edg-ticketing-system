import { useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createRequest, uploadAttachment } from "@/lib/api/requests";
import { ApiError } from "@/lib/api/client";
import { useRole, useUser } from "@/lib/session";
import { toast } from "sonner";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Paperclip,
} from "lucide-react";

interface NewRequestFormProps {
  onClose: () => void;
}

const REQUESTER_DEFAULT_CATEGORY = "autre";
const REQUESTER_DEFAULT_PRIORITY = "medium";

type RequiredField = "title" | "description";
type ValidationErrors = Partial<Record<RequiredField, string>>;

export function NewRequestForm({ onClose }: NewRequestFormProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [role] = useRole();
  const sessionUser = useUser();

  // ── État du formulaire (AVANT le return conditionnel pour respecter les règles des hooks) ─
  const [form, setForm] = useState({
    title: "",
    description: "",
  });
  const [fileList, setFileList] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [duplicateRef, setDuplicateRef] = useState<string | null>(null);
  const [validationErrors, setValidationErrors] = useState<ValidationErrors>({});

  const clearFieldError = (field: keyof typeof form) => {
    if (!(field in validationErrors)) return;
    setValidationErrors((prev) => {
      const next = { ...prev };
      delete next[field as RequiredField];
      return next;
    });
  };

  const setInput = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
    clearFieldError(k);
  };

  const validateForm = (): ValidationErrors => {
    const errors: ValidationErrors = {};
    if (!form.title.trim()) {
      errors.title = "Le titre de la demande est obligatoire.";
    }
    if (!form.description.trim()) {
      errors.description = "La description détaillée est obligatoire.";
    } else if (form.description.trim().length < 10) {
      errors.description = "Description trop courte (minimum 10 caractères).";
    }
    return errors;
  };

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const errors = validateForm();
    setValidationErrors(errors);
    if (Object.keys(errors).length > 0 || !sessionUser || submitting) return;
    setSubmitting(true);

    let result: Awaited<ReturnType<typeof createRequest>>;
    try {
      result = await createRequest({
        title: form.title.trim(),
        description: form.description.trim(),
        category: REQUESTER_DEFAULT_CATEGORY,
        priority: REQUESTER_DEFAULT_PRIORITY,
        requester_name: sessionUser.name,
        requester_email: sessionUser.email,
        requester_id: sessionUser.id,
        infos: { auto_route: true },
        is_external: false,
      });
    } catch (err: unknown) {
      if (err instanceof ApiError && err.errorCode === "DUPLICATE_REQUEST") {
        const refMatch = err.message.match(/réf\.\s+([^\)]+)\)/);
        setDuplicateRef(refMatch?.[1]?.trim() ?? "—");
      } else if (err instanceof ApiError) {
        toast.error(err.message || "Impossible de créer la demande.");
      } else {
        toast.error("Impossible de créer la demande. Veuillez réessayer.");
      }
      setSubmitting(false);
      return;
    }

    toast.success("La demande a été créée avec succès.", {
      description: `Référence ${result.ref}.`,
      icon: <CheckCircle2 className="h-4 w-4 text-success" />,
    });

    qc.setQueryData(["request", String(result.id), "active"], result);
    await qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["req-stats"] });

    if (fileList.length > 0) {
      let uploadFailed = false;
      for (const file of fileList) {
        try {
          await uploadAttachment(result.id, file);
        } catch {
          uploadFailed = true;
        }
      }
      if (uploadFailed) {
        toast.warning("Demande créée, pièces jointes incomplètes.", {
          description: "Certaines pièces jointes n'ont pas pu être téléversées.",
        });
      }
    }

    try {
      await navigate({ to: "/app/requests/$id", params: { id: String(result.id) } });
    } catch {
      toast.warning("Demande créée, mais l'ouverture automatique a échoué.", {
        description: "Retrouvez-la dans Mes demandes.",
      });
      setSubmitting(false);
    }
  };

  // ── Accès réservé (role public) ──────────────────────────────────────────
  if (role === "public") {
    return (
      <div className="py-8 text-center space-y-3">
        <AlertCircle className="mx-auto h-10 w-10 text-warning" />
        <h2 className="text-lg font-bold">Accès réservé aux employés EDG</h2>
        <p className="text-sm text-muted-foreground">
          Cet espace est réservé aux collaborateurs internes EDG.
          Usagers ou clients, merci de passer par le portail public.
        </p>
        <div className="flex justify-center gap-2 pt-2">
          <Button variant="ghost" className="rounded-full" onClick={onClose}>Fermer</Button>
          <Button asChild className="rounded-full gradient-primary">
            <Link to="/create-request">
              <ExternalLink className="mr-1.5 h-4 w-4" /> Portail public
            </Link>
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Dialog open={duplicateRef !== null} onOpenChange={(o) => { if (!o) setDuplicateRef(null); }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Demande déjà soumise</DialogTitle>
            <DialogDescription>
              Une demande identique est déjà en cours de traitement.
            </DialogDescription>
          </DialogHeader>
          <div className="rounded-xl border border-amber-300/40 bg-amber-50/60 dark:bg-amber-950/20 p-4 text-sm">
            <p className="text-muted-foreground">Référence de votre demande existante :</p>
            <p className="mt-1 font-mono text-lg font-bold tracking-widest">{duplicateRef}</p>
          </div>
          <p className="text-sm text-muted-foreground">
            Consultez l'avancement de cette demande dans votre espace personnel avant d'en soumettre une nouvelle.
          </p>
          <DialogFooter className="gap-2 sm:flex-row">
            <Button variant="outline" className="rounded-full" onClick={() => setDuplicateRef(null)}>
              Fermer
            </Button>
            <Button
              className="rounded-full gradient-primary"
              onClick={() => { setDuplicateRef(null); navigate({ to: "/app/requests" }); }}
            >
              Voir mes demandes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <form onSubmit={submit} className="space-y-5" noValidate>
        {/* Titre */}
        <div>
          <Label>Titre de la demande</Label>
          <Input
            required
            className="mt-1.5 h-11"
            placeholder="Ex : Accès SAP bloqué depuis ce matin"
            value={form.title}
            onChange={setInput("title")}
            aria-invalid={!!validationErrors.title}
            aria-describedby={validationErrors.title ? "request-title-error" : undefined}
          />
          {validationErrors.title && (
            <p id="request-title-error" className="mt-1.5 text-xs text-destructive">
              {validationErrors.title}
            </p>
          )}
        </div>

        {/* Description */}
        <div>
          <Label>Description détaillée</Label>
          <Textarea
            required
            className="mt-1.5 min-h-28"
            placeholder="Décrivez le contexte, l'impact, les étapes pour reproduire l'incident… (minimum 10 caractères)"
            value={form.description}
            onChange={setInput("description")}
            aria-invalid={!!validationErrors.description}
            aria-describedby={validationErrors.description ? "request-description-error" : undefined}
          />
          {(validationErrors.description || (form.description.length > 0 && form.description.trim().length < 10)) && (
            <p id="request-description-error" className="mt-1.5 text-xs text-destructive">
              {validationErrors.description ?? "Description trop courte (minimum 10 caractères)."}
            </p>
          )}
        </div>

        {/* Pièces jointes */}
        <div>
          <Label>Pièces jointes (optionnel)</Label>
          <label className="mt-1.5 flex min-h-[2.75rem] cursor-pointer flex-wrap items-center gap-2 rounded-xl border border-dashed border-border/60 px-4 py-2.5 text-sm text-muted-foreground transition-colors hover:border-primary/50 hover:text-foreground">
            <Paperclip className="h-4 w-4 shrink-0" />
            <span>
              {fileList.length > 0
                ? fileList.map((f) => f.name).join(", ")
                : "Cliquer pour joindre des fichiers (jpg, png, pdf — max 10 Mo)"}
            </span>
            <input
              type="file"
              multiple
              accept=".jpg,.jpeg,.png,.webp,.heic,.pdf"
              className="sr-only"
              onChange={(e) => setFileList(Array.from(e.target.files ?? []))}
            />
          </label>
          {fileList.length > 0 && (
            <p className="mt-1.5 text-xs text-muted-foreground">
              {fileList.length} fichier{fileList.length > 1 ? "s" : ""} sélectionné{fileList.length > 1 ? "s" : ""} — seront téléversés après envoi.
            </p>
          )}
        </div>

        {/* Actions */}
        <div className="flex justify-end gap-2 border-t border-border/30 pt-4">
          <Button
            type="button"
            variant="ghost"
            className="rounded-full"
            onClick={onClose}
          >
            Annuler
          </Button>
          <Button
            type="submit"
            className="rounded-full gradient-primary px-6 shadow-lg shadow-primary/30"
            disabled={!sessionUser || submitting}
          >
            {submitting ? (
              <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Envoi en cours…</>
            ) : "Soumettre la demande"}
          </Button>
        </div>
      </form>
    </div>
  );
}
