import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { fetchRequest, reopenRequest } from "@/lib/api/requests";
import { toast } from "sonner";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import {
  XCircle,
  RotateCcw,
  Clock,
  Calendar,
  MessageSquare,
  FileText,
  Loader2,
  History,
  AlertTriangle,
  Tag,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface Props {
  id: string | null;
  open: boolean;
  onClose: () => void;
}

export function RejectedTicketModal({ id, open, onClose }: Props) {
  const qc = useQueryClient();
  const [reopenReason, setReopenReason] = useState("");
  const [showReopenForm, setShowReopenForm] = useState(false);

  const { data: r, isLoading } = useQuery({
    queryKey: ["request", id],
    queryFn: () => fetchRequest(id!),
    enabled: open && !!id,
    staleTime: 15_000,
  });

  const reopenMut = useMutation({
    mutationFn: (reason: string) => reopenRequest(id!, reason || undefined),
    onSuccess: () => {
      toast.success("Demande réouverte — un agent va la reprendre en charge.");
      qc.invalidateQueries({ queryKey: ["requests"] });
      qc.invalidateQueries({ queryKey: ["request", id] });
      setShowReopenForm(false);
      setReopenReason("");
      handleClose();
    },
    onError: () => toast.error("Impossible de réouvrir la demande. Veuillez réessayer."),
  });

  function handleClose() {
    setShowReopenForm(false);
    setReopenReason("");
    onClose();
  }

  const rejectionEvent = r?.timeline?.[r.timeline.length - 1];
  const publicComments = r?.comments.filter((c) => c.isPublic) ?? [];

  return (
    <Dialog open={open} onOpenChange={(o) => { if (!o) handleClose(); }}>
      <DialogContent className="max-w-2xl max-h-[88vh] overflow-hidden flex flex-col p-0 gap-0">
        {/* Header fixe */}
        <DialogHeader className="px-6 pt-6 pb-4 border-b border-border/40 shrink-0">
          {isLoading ? (
            <div className="flex items-center gap-2 text-muted-foreground text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Chargement des détails…
            </div>
          ) : r ? (
            <>
              <div className="flex items-start gap-3 pr-8">
                <div className="min-w-0 flex-1">
                  <p className="font-mono text-xs text-muted-foreground">{r.ref}</p>
                  <DialogTitle className="mt-1 text-base leading-snug">{r.title}</DialogTitle>
                  <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                    <StatusBadge status={r.status} />
                    <PriorityBadge priority={r.priority} />
                    <span className="inline-flex items-center gap-1 rounded-full border border-border/50 bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground">
                      <Tag className="h-2.5 w-2.5" />
                      {r.category}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="h-3 w-3" />
                  Créée le {format(new Date(r.createdAt), "d MMMM yyyy 'à' HH:mm", { locale: fr })}
                </span>
                {rejectionEvent && (
                  <span className="flex items-center gap-1 text-destructive font-medium">
                    <XCircle className="h-3 w-3" />
                    Rejetée le {format(new Date(rejectionEvent.at), "d MMMM yyyy 'à' HH:mm", { locale: fr })}
                  </span>
                )}
              </div>
            </>
          ) : null}
        </DialogHeader>

        {/* Corps scrollable */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5 min-h-0">
          {isLoading ? (
            <div className="space-y-3 py-2">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="h-14 animate-pulse rounded-xl bg-muted/40" />
              ))}
            </div>
          ) : r ? (
            <>
              {/* Motif du rejet */}
              <div className="rounded-2xl border border-destructive/30 bg-destructive/5 p-4 space-y-2">
                <div className="flex items-center gap-2 font-semibold text-sm text-destructive">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  Motif du rejet
                </div>
                {rejectionEvent ? (
                  <p className="text-sm leading-relaxed text-foreground/90">{rejectionEvent.label}</p>
                ) : (
                  <p className="text-sm text-muted-foreground italic">Aucun motif précisé.</p>
                )}
                {rejectionEvent?.by && (
                  <p className="text-xs text-muted-foreground">
                    Décision de :{" "}
                    <span className="font-medium text-foreground">{rejectionEvent.by}</span>
                  </p>
                )}
              </div>

              {/* Description */}
              <div className="space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                  <FileText className="h-3.5 w-3.5" />
                  Description de la demande
                </div>
                <p className="text-sm leading-relaxed rounded-xl border border-border/40 bg-background/50 px-4 py-3 text-foreground/90">
                  {r.description}
                </p>
              </div>

              {/* Historique */}
              {r.timeline.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <History className="h-3.5 w-3.5" />
                    Historique des traitements
                  </div>
                  <ol className="relative border-l border-border/50 ml-2 space-y-4 py-1 pl-1">
                    {r.timeline.map((t, i) => {
                      const isFirst = i === 0;
                      const isLast = i === r.timeline.length - 1;
                      return (
                        <li key={t.id} className="pl-5 relative">
                          <span
                            className={cn(
                              "absolute -left-[9px] top-[3px] h-[14px] w-[14px] rounded-full border-2 border-background",
                              isLast
                                ? "bg-destructive"
                                : isFirst
                                  ? "bg-primary"
                                  : "bg-muted-foreground/50",
                            )}
                          />
                          <p className="text-sm font-medium leading-snug">{t.label}</p>
                          <div className="flex flex-wrap gap-2 mt-0.5 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <Clock className="h-3 w-3" />
                              {format(new Date(t.at), "d MMM yyyy, HH:mm", { locale: fr })}
                            </span>
                            {t.by && <span>· {t.by}</span>}
                          </div>
                        </li>
                      );
                    })}
                  </ol>
                </div>
              )}

              {/* Commentaires agents */}
              {publicComments.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                    <MessageSquare className="h-3.5 w-3.5" />
                    Observations des agents
                  </div>
                  <ul className="space-y-2">
                    {publicComments.map((c) => (
                      <li
                        key={c.id}
                        className="rounded-xl border border-border/40 bg-background/50 px-4 py-3 text-sm"
                      >
                        <div className="flex items-center justify-between text-xs text-muted-foreground mb-1.5">
                          <strong className="text-foreground">{c.author}</strong>
                          <span>{format(new Date(c.createdAt), "d MMM yyyy, HH:mm", { locale: fr })}</span>
                        </div>
                        <p className="leading-relaxed text-foreground/90">{c.body}</p>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Formulaire de réouverture */}
              {showReopenForm && (
                <div className="space-y-3 rounded-2xl border border-border/40 bg-background/40 p-4">
                  <p className="text-sm font-semibold">Motif de la réouverture</p>
                  <p className="text-xs text-muted-foreground">
                    Expliquez ce qui a changé ou pourquoi vous contestez ce rejet (optionnel).
                  </p>
                  <textarea
                    value={reopenReason}
                    onChange={(e) => setReopenReason(e.target.value)}
                    placeholder="Ex : J'ai fourni les documents manquants, la panne persiste…"
                    rows={3}
                    className="w-full resize-none rounded-xl border border-border/50 bg-background/60 px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
                  />
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="rounded-full"
                      onClick={() => { setShowReopenForm(false); setReopenReason(""); }}
                    >
                      Annuler
                    </Button>
                    <Button
                      size="sm"
                      className="rounded-full"
                      disabled={reopenMut.isPending}
                      onClick={() => reopenMut.mutate(reopenReason.trim())}
                    >
                      {reopenMut.isPending ? (
                        <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <RotateCcw className="mr-1.5 h-3.5 w-3.5" />
                      )}
                      Confirmer la réouverture
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer fixe */}
        {!isLoading && r && (
          <div className="px-6 py-4 border-t border-border/40 flex items-center justify-between gap-3 bg-background/30 shrink-0">
            <Button variant="ghost" className="rounded-full" onClick={handleClose}>
              Fermer
            </Button>
            {!showReopenForm && (
              <Button
                className="rounded-full"
                onClick={() => setShowReopenForm(true)}
              >
                <RotateCcw className="mr-1.5 h-4 w-4" />
                Réouvrir la demande
              </Button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
