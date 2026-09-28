import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { prefetch } from "@/lib/prefetch";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { AsyncSwap } from "@/components/async-states";
import {
  fetchDistribution,
  fetchDistributionTechnicians,
  takeFromDistribution,
  assignFromDistribution,
} from "@/lib/api/requests";
import { toast } from "sonner";
import {
  Clock, Inbox, Share2, UserPlus, Wrench, Loader2, ChevronDown, ChevronUp,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { cn, formatElapsedHours } from "@/lib/utils";
import type { RequestItem } from "@/lib/mock-data";

// BR-DISTRIBUTION-001 — espace propre au chef de division support. L'admin y accède
// aussi (rôle bypass habituel), comme sur les autres espaces opérationnels.
const PAGE_ACCESS_ROLES = ["chef-division-support", "admin"] as const;

export const Route = createFileRoute("/app/distribution")({
  beforeLoad: () => requireRole(...PAGE_ACCESS_ROLES),
  head: () => ({ meta: [{ title: "Distribution — EDG Support" }] }),
  // Précharge au survol du lien — même queryKey que le useQuery du composant.
  loader: ({ context: { queryClient } }) =>
    prefetch(queryClient.ensureQueryData({
      queryKey: ["distribution"],
      queryFn: () => fetchDistribution({ limit: 100 }),
      staleTime: 20_000,
    })),
  component: DistributionPage,
});

function DistributionPage() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [technicianByTicket, setTechnicianByTicket] = useState<Record<string, string>>({});

  const { data, isLoading, isError } = useQuery({
    queryKey: ["distribution"],
    queryFn: () => fetchDistribution({ limit: 100 }),
    staleTime: 20_000,
  });
  const tickets: RequestItem[] = data?.items ?? [];

  // Liste métier dédiée : déjà restreinte aux techniciens actifs de ma division.
  const { data: technicians = [], isLoading: loadTechnicians } = useQuery({
    queryKey: ["distribution-technicians"],
    queryFn: fetchDistributionTechnicians,
    staleTime: 5 * 60_000,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["distribution"] });
    queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
    queryClient.invalidateQueries({ queryKey: ["my-tickets-stats"] });
    queryClient.invalidateQueries({ queryKey: ["requests"] });
    queryClient.invalidateQueries({ queryKey: ["queue"] });
    queryClient.invalidateQueries({ queryKey: ["stats"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };

  const takeMut = useMutation({
    mutationFn: (id: string) => takeFromDistribution(id),
    onSuccess: (_, id) => {
      const t = tickets.find((x) => x.id === id);
      toast.success(`Ticket ${t?.ref ?? ""} pris en charge — disponible dans votre boîte de traitement.`);
      setExpanded(null);
      invalidateAll();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Impossible de prendre ce ticket."),
  });

  const assignMut = useMutation({
    mutationFn: ({ id, technicianId }: { id: string; technicianId: string }) =>
      assignFromDistribution(id, technicianId),
    onSuccess: (_, { id, technicianId }) => {
      const t = tickets.find((x) => x.id === id);
      const tech = technicians.find((x) => x.id === technicianId);
      toast.success(`Ticket ${t?.ref ?? ""} assigné à ${tech?.name ?? "le technicien"}.`);
      setExpanded(null);
      invalidateAll();
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : "Impossible d'assigner ce ticket."),
  });

  const isBusy = takeMut.isPending || assignMut.isPending;
  const listState: "loading" | "empty" | "error" | "ready" = isLoading
    ? "loading"
    : isError
      ? "error"
      : tickets.length === 0
        ? "empty"
        : "ready";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center gap-2">
          <Share2 className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">Distribution</h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Tickets que le chef de service vous a orientés. Prenez-les en charge, ou
          assignez-les à un technicien de votre division.
        </p>
      </motion.header>

      <AsyncSwap
        state={listState}
        empty={
          <GlassCard className="py-16 text-center">
            <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted">
              <Inbox className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="font-semibold">Aucun ticket à répartir</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Les tickets orientés par le chef de service apparaîtront ici.
            </p>
          </GlassCard>
        }
      >
        <div className="space-y-3">
          <AnimatePresence mode="popLayout" initial={false}>
            {tickets.map((req) => {
              const isOpen = expanded === req.id;
              const selectedTechnician = technicianByTicket[req.id] ?? "";
              const isTaking = takeMut.isPending && takeMut.variables === req.id;
              const isAssigning = assignMut.isPending && assignMut.variables?.id === req.id;

              return (
                <motion.div
                  key={req.id}
                  layout
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -6 }}
                >
                  <GlassCard className="overflow-hidden p-0">
                    <button
                      type="button"
                      className="flex w-full items-start gap-4 p-5 text-left transition-colors hover:bg-foreground/3"
                      onClick={() => setExpanded(isOpen ? null : req.id)}
                    >
                      <div className="min-w-0 flex-1 space-y-1.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-[11px] text-primary">{req.ref}</span>
                          <PriorityBadge priority={req.priority} />
                          <StatusBadge status={req.status} />
                          {req.category && (
                            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
                              {req.category}
                            </span>
                          )}
                        </div>
                        <p className="line-clamp-2 font-semibold leading-snug">{req.title}</p>
                        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                          <span>{req.requesterName}</span>
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            {formatDistanceToNow(new Date(req.createdAt), { addSuffix: true, locale: fr })}
                          </span>
                          {req.slaElapsed != null && (
                            <span className={cn(
                              req.slaHours > 0 && req.slaElapsed > req.slaHours
                                && "font-semibold text-destructive",
                            )}>
                              SLA : {formatElapsedHours(req.slaElapsed)}
                            </span>
                          )}
                        </div>
                      </div>
                      {isOpen
                        ? <ChevronUp className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />
                        : <ChevronDown className="mt-1 h-4 w-4 shrink-0 text-muted-foreground" />}
                    </button>

                    {isOpen && (
                      <div className="space-y-4 border-t border-border/40 p-5 pt-4">
                        <p className="text-sm text-muted-foreground">{req.description}</p>

                        {/* Procédure EDG/PS-GSI/Pro-02 tâche 1.3 — descriptif de
                            solution proposée par le chef de service : c'est sur
                            cette base que la prise en charge ou l'affectation à
                            un technicien se décide. */}
                        {req.proposedSolution && (
                          <div className="rounded-xl border border-info/25 bg-info/8 px-3 py-2.5">
                            <p className="text-xs font-semibold uppercase tracking-wide text-info">
                              Solution proposée par le chef de service
                            </p>
                            <p className="mt-1 whitespace-pre-line text-sm">
                              {req.proposedSolution}
                            </p>
                          </div>
                        )}

                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <Label>Technicien de ma division</Label>
                            <Select
                              value={selectedTechnician}
                              onValueChange={(v) =>
                                setTechnicianByTicket((prev) => ({ ...prev, [req.id]: v }))
                              }
                              disabled={isBusy || loadTechnicians || technicians.length === 0}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder={
                                  loadTechnicians
                                    ? "Chargement…"
                                    : technicians.length === 0
                                      ? "Aucun technicien dans votre division"
                                      : "Sélectionner un technicien"
                                } />
                              </SelectTrigger>
                              <SelectContent>
                                {technicians.map((t) => (
                                  <SelectItem key={t.id} value={t.id}>{t.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        </div>

                        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                          <Link
                            to="/app/distribution/tickets/$id"
                            params={{ id: req.id }}
                            className="text-xs font-medium text-primary hover:underline"
                          >
                            Ouvrir la fiche complète
                          </Link>
                          <div className="flex flex-wrap items-center gap-2">
                            <Button
                              variant="outline"
                              className="rounded-full"
                              disabled={isBusy || !selectedTechnician}
                              onClick={() =>
                                assignMut.mutate({ id: req.id, technicianId: selectedTechnician })
                              }
                            >
                              {isAssigning
                                ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                                : <UserPlus className="mr-1.5 h-4 w-4" />}
                              Assigner à un technicien
                            </Button>
                            <Button
                              className="gradient-primary rounded-full"
                              disabled={isBusy}
                              onClick={() => takeMut.mutate(req.id)}
                            >
                              {isTaking
                                ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
                                : <Wrench className="mr-1.5 h-4 w-4" />}
                              Prendre en charge
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}
                  </GlassCard>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </AsyncSwap>
    </div>
  );
}
