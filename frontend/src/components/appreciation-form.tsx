import { useState } from "react";
import { Star, CheckCircle2, RotateCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import type { Appreciation } from "@/lib/mock-data";

type Props = {
  requestId: string;
  authorType: "internal" | "external";
  existing?: Appreciation;
  isClosed?: boolean;
  onSubmit: (appreciation: Appreciation) => void;
  onReopen?: () => void;
  onSave?: (data: {
    rating: 1 | 2 | 3 | 4 | 5;
    comment?: string;
    resolvedConfirmed: boolean;
    authorType: "internal" | "external";
  }) => Promise<void>;
};

const LABELS = ["Très insatisfait", "Insatisfait", "Neutre", "Satisfait", "Très satisfait"];

export function AppreciationForm({ existing, isClosed, authorType, onSubmit, onReopen, onSave }: Props) {
  const [rating, setRating] = useState<1 | 2 | 3 | 4 | 5>(existing?.rating ?? 0 as never);
  const [hovered, setHovered] = useState(0);
  const [comment, setComment] = useState(existing?.comment ?? "");
  const [resolved, setResolved] = useState<boolean | null>(existing?.resolvedConfirmed ?? null);
  const [submitted, setSubmitted] = useState(!!existing);
  const [editing, setEditing] = useState(false);

  const active = editing || !submitted;

  if (submitted && !editing) {
    return (
      <div className="rounded-xl border border-green-500/30 bg-green-500/10 p-4 flex flex-col gap-3">
        <div className="flex items-center gap-2 text-green-400 font-medium text-sm">
          <CheckCircle2 className="h-4 w-4" />
          Votre avis a été enregistré — merci !
        </div>
        <div className="flex gap-1">
          {([1, 2, 3, 4, 5] as const).map((s) => (
            <Star
              key={s}
              className={`h-5 w-5 ${s <= existing!.rating ? "fill-yellow-400 text-yellow-400" : "text-muted-foreground/30"}`}
            />
          ))}
          <span className="ml-2 text-sm text-muted-foreground">{LABELS[(existing?.rating ?? 1) - 1]}</span>
        </div>
        {existing?.comment && (
          <p className="text-sm text-muted-foreground italic">« {existing.comment} »</p>
        )}
        {!isClosed && (
          <Button size="sm" variant="ghost" className="self-start text-xs" onClick={() => setEditing(true)}>
            Modifier mon avis
          </Button>
        )}
      </div>
    );
  }

  const canSubmit = rating > 0 && resolved !== null;

  async function handleSubmit() {
    if (!canSubmit) return;
    const appr: Appreciation = {
      rating: rating as 1 | 2 | 3 | 4 | 5,
      comment: comment.trim() || undefined,
      resolvedConfirmed: resolved!,
      authorType,
      at: new Date().toISOString(),
    };
    if (onSave) {
      try {
        await onSave({
          rating: rating as 1 | 2 | 3 | 4 | 5,
          comment: comment.trim() || undefined,
          resolvedConfirmed: resolved!,
          authorType,
        });
      } catch {
        toast.error("Erreur lors de l'envoi de votre avis. Réessayez.");
        return;
      }
    }
    onSubmit(appr);
    setSubmitted(true);
    setEditing(false);
    toast.success("Merci pour votre retour !");
  }

  return (
    <div className="rounded-xl border border-border/50 bg-card/60 backdrop-blur-sm p-4 flex flex-col gap-4">
      <p className="font-medium text-sm">Évaluez la prise en charge de votre ticket</p>

      {/* Star rating */}
      <div className="flex flex-col gap-1">
        <div
          className="flex gap-1"
          role="radiogroup"
          aria-label="Note de 1 à 5 étoiles"
        >
          {([1, 2, 3, 4, 5] as const).map((s) => {
            const filled = s <= (hovered || rating);
            return (
              <button
                key={s}
                role="radio"
                aria-checked={rating === s}
                aria-label={`${s} étoile${s > 1 ? "s" : ""} — ${LABELS[s - 1]}`}
                onClick={() => setRating(s)}
                onMouseEnter={() => setHovered(s)}
                onMouseLeave={() => setHovered(0)}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" && s < 5) setRating((s + 1) as never);
                  if (e.key === "ArrowLeft" && s > 1) setRating((s - 1) as never);
                }}
                className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded"
              >
                <Star
                  className={`h-8 w-8 transition-colors ${
                    filled
                      ? "fill-yellow-400 text-yellow-400"
                      : "text-muted-foreground/40 hover:text-yellow-300"
                  }`}
                />
              </button>
            );
          })}
        </div>
        {(hovered || rating) > 0 && (
          <p className="text-xs text-muted-foreground">{LABELS[(hovered || rating) - 1]}</p>
        )}
      </div>

      {/* Resolved confirmation */}
      <div className="flex flex-col gap-2">
        <p className="text-sm">Votre problème a-t-il été résolu ?</p>
        <div className="flex gap-2">
          <button
            onClick={() => setResolved(true)}
            className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${
              resolved === true
                ? "bg-green-500/20 border-green-500/50 text-green-400"
                : "border-border/50 text-muted-foreground hover:bg-muted/40"
            }`}
          >
            Oui
          </button>
          <button
            onClick={() => setResolved(false)}
            className={`px-4 py-1.5 rounded-lg text-sm border transition-colors ${
              resolved === false
                ? "bg-red-500/20 border-red-500/50 text-red-400"
                : "border-border/50 text-muted-foreground hover:bg-muted/40"
            }`}
          >
            Non
          </button>
        </div>
        {resolved === false && onReopen && (
          <div className="flex items-center gap-2 rounded-lg bg-orange-500/10 border border-orange-500/30 p-3 text-sm text-orange-300">
            <RotateCcw className="h-4 w-4 shrink-0" />
            <span>Votre ticket n'est pas résolu ?</span>
            <button
              onClick={onReopen}
              className="ml-auto underline underline-offset-2 hover:text-orange-200 whitespace-nowrap"
            >
              Rouvrir le ticket
            </button>
          </div>
        )}
      </div>

      {/* Optional comment */}
      <div className="flex flex-col gap-1.5">
        <label className="text-sm text-muted-foreground">Commentaire (facultatif)</label>
        <Textarea
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          placeholder="Partagez votre expérience…"
          rows={3}
          maxLength={500}
          className="resize-none text-sm"
        />
        <p className="text-xs text-muted-foreground text-right">{comment.length}/500</p>
      </div>

      <div className="flex gap-2">
        <Button onClick={handleSubmit} disabled={!canSubmit} size="sm">
          Envoyer mon avis
        </Button>
        {editing && (
          <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setSubmitted(true); }}>
            Annuler
          </Button>
        )}
      </div>
    </div>
  );
}
