import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { Intervention, TimelineEvent } from "@/lib/mock-data";
import { formatInterventionDateTime, formatInterventionDuration, interventionRoleLabel } from "@/lib/intervention-utils";
import { InterventionDetailBody } from "@/components/intervention-detail-body";

// BR-TRACE-001 — fiche de consultation complète d'une intervention, en lecture
// seule (aucune action de modification/suppression — une intervention figée ne
// se corrige jamais, voir BR-TRACE-001). Réutilise le même corps de détail que
// la carte dépliée dans le journal, pour une seule source de rendu.
export function InterventionDetailsModal({
  intervention,
  events,
  requestRef,
  onOpenChange,
  onOpenAttachment,
}: {
  intervention: Intervention | null;
  events: TimelineEvent[];
  requestRef?: string;
  onOpenChange: (open: boolean) => void;
  onOpenAttachment?: (attachment: { id?: string; filename?: string }) => void;
}) {
  return (
    <Dialog open={!!intervention} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-2xl">
        {intervention && (
          <>
            <DialogHeader>
              <DialogTitle>
                Intervention {intervention.interventionOrder ?? ""} — Cycle {intervention.cycleNumber}
              </DialogTitle>
              <DialogDescription>
                {intervention.actorName}
                {intervention.actorRole && ` · ${interventionRoleLabel(intervention.actorRole)}`}
                {requestRef && ` · ${requestRef}`}
              </DialogDescription>
            </DialogHeader>

            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 rounded-xl border border-border/40 bg-background/45 px-3 py-2.5 text-xs sm:grid-cols-3">
              <div>
                <dt className="text-muted-foreground">Identifiant</dt>
                <dd className="truncate font-mono" title={intervention.interventionId}>{intervention.interventionId}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Début</dt>
                <dd>{formatInterventionDateTime(intervention.startedAt)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Fin</dt>
                <dd>{intervention.endedAt ? formatInterventionDateTime(intervention.endedAt) : "en cours"}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Durée</dt>
                <dd>{formatInterventionDuration(intervention.durationSeconds)}</dd>
              </div>
              <div>
                <dt className="text-muted-foreground">Événements liés</dt>
                <dd>{intervention.eventIds.length}</dd>
              </div>
            </dl>

            <InterventionDetailBody
              intervention={intervention}
              events={events}
              onOpenAttachment={onOpenAttachment}
            />
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
