import { useState, useMemo } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { useQuery, useQueryClient } from "@tanstack/react-query";
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchRoutingRules, fetchRequestCategories } from "@/lib/api/admin-config";
import type { RoutingRule } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { createRequest, uploadAttachment } from "@/lib/api/requests";
import { ApiError } from "@/lib/api/client";
import { useRole, useUser } from "@/lib/session";
import { toast } from "sonner";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Paperclip,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ── Suggestion de routage : code catégorie → code direction DB ───────────
const CATEGORY_DIR_CODE: Record<string, string> = {
  acces_applicatif: "DSI",
  logiciel:         "DSI",
  incident:         "DSI",
  maintenance_si:   "DSI",
  habilitation:     "DSI",
};

interface Suggestion { directionCode: string; ruleName: string }

function computeSuggestion(categoryCode: string, text: string, rules: RoutingRule[]): Suggestion | null {
  // Correspondance par mot-clé dans les règles de routage
  const lc = text.toLowerCase();
  for (const rule of rules.filter((r) => r.active && r.conditionField === "keyword")) {
    const kws = rule.conditionValue.split(",").map((k) => k.trim().toLowerCase());
    if (kws.some((kw) => kw && lc.includes(kw)) && rule.targetService) {
      return { directionCode: "DSI", ruleName: rule.name };
    }
  }
  // Fallback par code catégorie
  const dirCode = CATEGORY_DIR_CODE[categoryCode];
  if (dirCode) return { directionCode: dirCode, ruleName: `Routage automatique — ${categoryCode}` };
  return null;
}

interface NewRequestFormProps {
  onClose: () => void;
}

export function NewRequestForm({ onClose }: NewRequestFormProps) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [role] = useRole();
  const sessionUser = useUser();

  // ── Chargement des directions depuis l'API ────────────────────────────────
  const { data: apiDirections = [] } = useQuery({
    queryKey: ["directions-active"],
    queryFn: fetchDirections,
    staleTime: 5 * 60 * 1000,
  });

  const { data: routingRulesData = [] } = useQuery({
    queryKey: ["routing-rules"],
    queryFn: fetchRoutingRules,
    staleTime: 10 * 60_000,
  });

  const { data: categoriesRef = [] } = useQuery({
    queryKey: ["ref-request-categories"],
    queryFn: fetchRequestCategories,
    staleTime: 10 * 60_000,
  });
  const activeCategories = categoriesRef.filter((c) => c.status !== false);

  // ── État du formulaire (AVANT le return conditionnel pour respecter les règles des hooks) ─
  const [form, setForm] = useState({
    title: "",
    category: "",
    priority: "medium",
    directionId: "",
    serviceId: "",
    description: "",
    appName: "",
    accessReason: "",
    systemAffected: "",
    errorMsg: "",
    payPeriod: "",
    careerType: "",
    budgetLine: "",
    docType: "",
    extraField: "",
  });
  const [fileList, setFileList] = useState<File[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [duplicateRef, setDuplicateRef] = useState<string | null>(null);

  // ── Chargement des unités selon la direction sélectionnée ────────────────
  const { data: apiUnits = [] } = useQuery({
    queryKey: ["units", form.directionId],
    queryFn: () => fetchUnits(form.directionId),
    enabled: !!form.directionId,
    staleTime: 5 * 60 * 1000,
  });

  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const setInput = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleCategoryChange = (v: string) =>
    setForm((f) => ({ ...f, category: v, directionId: "", serviceId: "" }));

  const handleDirectionChange = (v: string) =>
    setForm((f) => ({ ...f, directionId: v, serviceId: "" }));

  // ── Suggestion de routage ─────────────────────────────────────────────────
  const suggestion = useMemo(
    () => form.category ? computeSuggestion(form.category, `${form.title} ${form.description}`, routingRulesData) : null,
    [form.category, form.title, form.description, routingRulesData],
  );

  // Trouve la direction API dont le code correspond à la suggestion
  const suggestionApiDir = useMemo(() => {
    if (!suggestion) return undefined;
    return apiDirections.find((d) => d.code === suggestion.directionCode);
  }, [suggestion, apiDirections]);

  const activeDirections = useMemo(() => apiDirections.filter((d) => d.status), [apiDirections]);
  const availableUnits = useMemo(() => apiUnits.filter((u) => u.status), [apiUnits]);

  const isUser = role === "user";

  // La suggestion est appliquée si la direction sélectionnée correspond à la suggestion
  const suggestionApplied = suggestion !== null && !!suggestionApiDir && String(form.directionId) === String(suggestionApiDir.id);

  const isValid =
    form.title.trim().length > 0 &&
    form.category !== "" &&
    form.directionId !== "" &&
    form.description.trim().length >= 10;

  const submit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!isValid || !sessionUser || submitting) return;
    setSubmitting(true);

    const selectedDirName = activeDirections.find((d) => String(d.id) === String(form.directionId))?.name;

    createRequest({
      title: form.title.trim(),
      description: form.description.trim(),
      category: form.category,
      priority: form.priority,
      ...(form.directionId && { direction_id: form.directionId }),
      ...(form.serviceId && !isUser && { unity_id: Number(form.serviceId) }),
      requester_name: sessionUser.name,
      requester_email: sessionUser.email,
      requester_id: sessionUser.id,
      is_external: false,
    })
      .then(async (result) => {
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
            toast.warning(`Demande ${result.ref} soumise`, {
              description: "Certaines pièces jointes n'ont pas pu être téléversées.",
            });
          } else {
            toast.success(`Demande ${result.ref} soumise`, {
              description: `${fileList.length} pièce${fileList.length > 1 ? "s jointes" : " jointe"} téléversée${fileList.length > 1 ? "s" : ""}.`,
            });
          }
        } else {
          toast.success(`Demande ${result.ref} soumise`, {
            description: `Routée vers ${selectedDirName ?? form.category}.`,
          });
        }
        qc.invalidateQueries({ queryKey: ["requests"] });
        navigate({ to: "/app/requests/$id", params: { id: String(result.id) } });
      })
      .catch((err: unknown) => {
        if (err instanceof ApiError && err.errorCode === "DUPLICATE_REQUEST") {
          const refMatch = err.message.match(/réf\.\s+([^\)]+)\)/);
          setDuplicateRef(refMatch?.[1]?.trim() ?? "—");
        } else if (err instanceof ApiError) {
          toast.error(err.message);
        } else {
          toast.error("Impossible de créer la demande. Veuillez réessayer.");
        }
        setSubmitting(false);
      });
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

      <form onSubmit={submit} className="space-y-5">
        {/* Titre */}
        <div>
          <Label>Titre de la demande</Label>
          <Input
            required
            className="mt-1.5 h-11"
            placeholder="Ex : Accès SAP bloqué depuis ce matin"
            value={form.title}
            onChange={setInput("title")}
          />
        </div>

        {/* Catégorie + Priorité */}
        <div className={cn("grid gap-4", !isUser && "sm:grid-cols-2")}>
          <div>
            <Label>Catégorie</Label>
            <Select value={form.category} onValueChange={handleCategoryChange}>
              <SelectTrigger className="mt-1.5 h-11">
                <SelectValue placeholder="Sélectionner une catégorie" />
              </SelectTrigger>
              <SelectContent>
                {activeCategories.map((c) => (
                  <SelectItem key={c.code} value={c.code}>{c.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {!isUser && (
            <div>
              <Label>Priorité</Label>
              <Select value={form.priority} onValueChange={set("priority")}>
                <SelectTrigger className="mt-1.5 h-11">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="critical">Critique</SelectItem>
                  <SelectItem value="high">Haute</SelectItem>
                  <SelectItem value="medium">Moyenne</SelectItem>
                  <SelectItem value="low">Basse</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}
        </div>

        {/* Champs dynamiques */}
        {(form.category === "acces_applicatif" || form.category === "habilitation") && (
          <div className="grid gap-4 sm:grid-cols-2 rounded-2xl border border-primary/20 bg-primary/5 p-4">
            <div>
              <Label>Nom de l'application</Label>
              <Input className="mt-1.5 h-11" placeholder="Ex : SAP, Sage, ArcGIS…" value={form.appName} onChange={setInput("appName")} />
            </div>
            <div>
              <Label>Motif de la demande</Label>
              <Input className="mt-1.5 h-11" placeholder="Ex : Nouveau poste, oubli mot de passe…" value={form.accessReason} onChange={setInput("accessReason")} />
            </div>
          </div>
        )}

        {(form.category === "incident" || form.category === "logiciel" || form.category === "maintenance_si") && (
          <div className="grid gap-4 sm:grid-cols-2 rounded-2xl border border-primary/20 bg-primary/5 p-4">
            <div>
              <Label>Système ou logiciel affecté</Label>
              <Input className="mt-1.5 h-11" placeholder="Ex : Poste Windows, imprimante RH…" value={form.systemAffected} onChange={setInput("systemAffected")} />
            </div>
            <div>
              <Label>Message d'erreur (si applicable)</Label>
              <Input className="mt-1.5 h-11" placeholder="Copiez ici le message exact" value={form.errorMsg} onChange={setInput("errorMsg")} />
            </div>
          </div>
        )}


        {/* Bannière suggestion de routage */}
        {!isUser && suggestion && suggestionApiDir && (
          <div
            className={cn(
              "flex flex-wrap items-center justify-between gap-3 rounded-2xl border px-4 py-3 text-sm",
              suggestionApplied
                ? "border-success/30 bg-success/10"
                : "border-primary/30 bg-primary/8",
            )}
          >
            <div className="flex min-w-0 items-start gap-2">
              {suggestionApplied
                ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" />
                : <Zap className="mt-0.5 h-4 w-4 shrink-0 text-primary" />}
              <div className="min-w-0">
                <p className="font-medium">
                  {suggestionApplied ? "Suggestion appliquée" : "Suggestion de routage automatique"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {suggestion.ruleName} — Direction recommandée :{" "}
                  <strong className="text-foreground">{suggestionApiDir.name}</strong>
                </p>
              </div>
            </div>
            {!suggestionApplied && (
              <Button
                type="button"
                size="sm"
                className="h-8 shrink-0 rounded-full gradient-primary px-4 text-xs text-primary-foreground"
                onClick={() =>
                  setForm((f) => ({ ...f, directionId: String(suggestionApiDir.id), serviceId: "" }))
                }
              >
                Appliquer
              </Button>
            )}
          </div>
        )}

        {/* Direction + Service */}
        <div className={isUser ? "" : "grid gap-4 sm:grid-cols-2"}>
          <div>
            <Label>
              <Building2 className="mr-1 inline h-3.5 w-3.5 text-muted-foreground" />
              Direction destinataire
            </Label>
            <Select value={form.directionId} onValueChange={handleDirectionChange}>
              <SelectTrigger className="mt-1.5 h-11">
                <SelectValue placeholder="Sélectionner une direction" />
              </SelectTrigger>
              <SelectContent>
                {activeDirections.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {isUser && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Un agent de cette direction sera automatiquement désigné pour traiter votre demande.
              </p>
            )}
          </div>
          {!isUser && (
            <div>
              <Label>Service (optionnel)</Label>
              <Select
                value={form.serviceId}
                onValueChange={set("serviceId")}
                disabled={availableUnits.length === 0}
              >
                <SelectTrigger className="mt-1.5 h-11">
                  <SelectValue
                    placeholder={
                      availableUnits.length === 0
                        ? "Choisissez d'abord une direction"
                        : "Sélectionner un service"
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {availableUnits.map((u) => (
                    <SelectItem key={u.id} value={String(u.id)}>{u.name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
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
          />
          {form.description.length > 0 && form.description.trim().length < 10 && (
            <p className="mt-1.5 text-xs text-destructive">Description trop courte (minimum 10 caractères).</p>
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
            disabled={!isValid || !sessionUser || submitting}
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
