import { Send, CheckCircle2, Paperclip } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Intervention, TimelineEvent } from "@/lib/mock-data";
import { formatInterventionDateTime, formatFileSize } from "@/lib/intervention-utils";

// BR-TRACE-001 — corps de détail partagé entre la carte dépliée du journal
// (`InterventionCard`, dans intervention-journal.tsx) et la fiche de
// consultation (`InterventionDetailsModal`) — une seule source de rendu.
export function InterventionDetailBody({
  intervention,
  events,
  onOpenAttachment,
}: {
  intervention: Intervention;
  events: TimelineEvent[];
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
}) {
  const iv = intervention;
  const comments = events.filter((e) => e.type === "comment_added");
  const attachments = events.filter((e) => e.type === "attachment_added");

  return (
    <div className="space-y-3">
      {(iv.actorMatricule || iv.actorDirectionLabel) && (
        <p className="text-xs text-muted-foreground">
          {iv.actorMatricule && <span>Matricule : {iv.actorMatricule}</span>}
          {iv.actorMatricule && iv.actorDirectionLabel && <span> · </span>}
          {iv.actorDirectionLabel && <span>{iv.actorDirectionLabel}</span>}
          {iv.actorDepartmentLabel && iv.actorDepartmentLabel !== iv.actorDirectionLabel && (
            <span> / {iv.actorDepartmentLabel}</span>
          )}
        </p>
      )}

      {/* 1. Travail effectué */}
      {iv.workDone && (
        <DetailBlock label="Travail effectué">{iv.workDone}</DetailBlock>
      )}

      {/* 2. Résultat / solution */}
      {(iv.summary || iv.solution || iv.recommendations) && (
        <div className="space-y-2">
          {iv.summary && <DetailBlock label="Résumé">{iv.summary}</DetailBlock>}
          {iv.solution && <DetailBlock label="Solution">{iv.solution}</DetailBlock>}
          {iv.recommendations && <DetailBlock label="Recommandations">{iv.recommendations}</DetailBlock>}
        </div>
      )}

      {/* 4. Instructions */}
      {iv.instruction && (
        <DetailBlock label="Instruction">{iv.instruction}</DetailBlock>
      )}

      {/* 6. Décision */}
      {iv.decision === "transmission" && (
        <div className="rounded-xl border border-sky-500/30 bg-sky-500/5 px-3 py-2 text-sm">
          <p className="flex flex-wrap items-center gap-1.5 font-medium text-sky-700 dark:text-sky-400">
            <span>{iv.actorName ?? "Intervenant"}</span>
            <Send className="h-3.5 w-3.5" />
            <span>{iv.destinationName ?? "—"}</span>
          </p>
          {iv.transmissionReason && (
            <p className="mt-1"><span className="font-medium text-muted-foreground">Motif :</span> {iv.transmissionReason}</p>
          )}
          {iv.endedAt && (
            <p className="mt-1 text-xs text-muted-foreground">{formatInterventionDateTime(iv.endedAt)}</p>
          )}
        </div>
      )}
      {iv.decision === "resolution" && (
        <div className="flex items-center gap-2 rounded-xl border border-success/30 bg-success/5 px-3 py-2 text-sm font-medium text-success">
          <CheckCircle2 className="h-4 w-4 shrink-0" />
          Traitement terminé{iv.endedAt && ` — ${formatInterventionDateTime(iv.endedAt)}`}
        </div>
      )}

      {/* 3. Commentaires */}
      {comments.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Commentaires de l'intervention</p>
          {comments.map((c) => (
            <div key={c.id} className="rounded-xl border border-border/40 bg-background/45 px-3 py-2 text-sm">
              <p>{c.comment}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">{c.by} · {formatInterventionDateTime(c.at)}</p>
            </div>
          ))}
        </div>
      )}

      {/* 5. Pièces jointes */}
      {attachments.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Pièces jointes</p>
          <div className="space-y-1.5">
            {attachments.map((a) => {
              const filename = typeof a.infos?.filename === "string" ? a.infos.filename : "Fichier";
              const mimeType = typeof a.infos?.mime_type === "string" ? a.infos.mime_type : undefined;
              const sizeBytes = typeof a.infos?.size_bytes === "number" ? a.infos.size_bytes : undefined;
              const attachmentId = typeof a.infos?.attachment_id === "string" ? a.infos.attachment_id : undefined;
              return (
                <div
                  key={a.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-xs"
                >
                  <div className="flex min-w-0 items-center gap-2">
                    <Paperclip className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="truncate font-medium text-foreground">{filename}</p>
                      <p className="text-muted-foreground">
                        {mimeType && <span>{mimeType}</span>}
                        {sizeBytes != null && <span> · {formatFileSize(sizeBytes)}</span>}
                        {a.by && <span> · {a.by}</span>}
                        <span> · {formatInterventionDateTime(a.at)}</span>
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="shrink-0 rounded-full border border-border/50 px-2.5 py-1 font-medium transition hover:bg-foreground/5"
                    onClick={() => onOpenAttachment?.({ id: attachmentId, filename })}
                  >
                    Voir / Télécharger
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 7. SLA */}
      {iv.slaHours != null && (
        <div className={cn(
          "rounded-xl px-3 py-2 text-sm",
          iv.slaBreached ? "border border-destructive/30 bg-destructive/5" : "border border-success/30 bg-success/5",
        )}>
          <span className="font-medium text-muted-foreground">SLA (cycle {iv.cycleNumber}) :</span>{" "}
          {iv.slaBreached ? "dépassé" : "respecté"} — cible {iv.slaHours} h
        </div>
      )}
    </div>
  );
}

function DetailBlock({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-border/40 bg-background/45 px-3 py-2 text-sm">
      <span className="mr-1 font-medium text-muted-foreground">{label} :</span>
      {children}
    </div>
  );
}
