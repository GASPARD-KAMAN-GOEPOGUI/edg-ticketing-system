import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { toast } from "sonner";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { getRequestByRef } from "@/lib/api/requests";
import type { RequestItem, Intervention } from "@/lib/mock-data";
import {
  formatInterventionDateTime,
  formatInterventionDuration,
  interventionRoleLabel,
  interventionStatus,
  INTERVENTION_STATUS_LABEL,
} from "@/lib/intervention-utils";
import { cn, initialsFor } from "@/lib/utils";
import {
  Search,
  SearchX,
  Loader2,
  ExternalLink,
  UserCircle2,
  Flag,
  Lock,
} from "lucide-react";

export const Route = createFileRoute("/app/admin/ticket-trace")({
  head: () => ({ meta: [{ title: "Traçabilité d'un ticket — Admin EDG" }] }),
  component: TicketTracePage,
});

type Row = {
  key: string;
  actorName: string;
  actorRole?: string;
  actorService?: string;
  action: string;
  startedAt?: string;
  endedAt?: string;
  durationSeconds?: number;
  detail?: string;
  current: boolean;
};

function buildRows(r: RequestItem): Row[] {
  const rows: Row[] = [];

  rows.push({
    key: "creation",
    actorName: r.requesterName,
    actorRole: "Demandeur",
    action: "Création du ticket",
    startedAt: r.createdAt,
    current: false,
  });

  const interventions = [...(r.interventions ?? [])].sort((a, b) => {
    const ao = a.interventionOrder ?? 0;
    const bo = b.interventionOrder ?? 0;
    if (a.cycleNumber !== b.cycleNumber) return a.cycleNumber - b.cycleNumber;
    return ao - bo;
  });

  for (const iv of interventions) {
    const st = interventionStatus(iv);
    rows.push({
      key: iv.interventionId,
      actorName: iv.actorName ?? "Intervenant",
      actorRole: interventionRoleLabel(iv.actorRole),
      actorService: iv.actorServiceLabel,
      action: describeIntervention(iv),
      startedAt: iv.startedAt,
      endedAt: iv.endedAt,
      durationSeconds: iv.durationSeconds,
      detail: iv.decision === "transmission" ? (iv.destinationName ?? undefined) : (iv.workDone ?? undefined),
      current: st === "ongoing",
    });
  }

  if (r.status === "closed" && r.closedAt) {
    rows.push({
      key: "closure",
      actorName: r.requesterName,
      actorRole: "Demandeur",
      action: "Confirmation & clôture du ticket",
      startedAt: r.closedAt,
      current: false,
    });
  }

  return rows;
}

function describeIntervention(iv: Intervention): string {
  if (iv.decision === "transmission") return "Transmission du traitement";
  if (iv.decision === "resolution") return "Résolution du ticket";
  return INTERVENTION_STATUS_LABEL[interventionStatus(iv)];
}

function TicketTracePage() {
  const [ref, setRef] = useState("");
  const [ticket, setTicket] = useState<RequestItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const search = async () => {
    const trimmed = ref.trim();
    if (!trimmed) return;
    setLoading(true);
    setSearched(false);
    setTicket(null);
    setNotFound(false);
    try {
      const result = await getRequestByRef(trimmed);
      setTicket(result);
    } catch (err) {
      setNotFound(true);
      toast.error((err as { message?: string })?.message ?? "Aucun ticket trouvé pour cette référence.");
    } finally {
      setSearched(true);
      setLoading(false);
    }
  };

  const rows = ticket ? buildRows(ticket) : [];
  const currentHolder = ticket?.status === "closed"
    ? "Dossier clôturé"
    : ticket?.assigneeName ?? (ticket?.status === "new" ? "En attente de prise en charge" : "Non assigné");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <Search className="h-3 w-3" /> Audit & Traçabilité
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
          Traçabilité d'un ticket
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Recherchez un ticket par numéro de référence pour voir toutes les personnes qui sont intervenues, de la création jusqu'à la clôture, et savoir où il se trouve actuellement.
        </p>
      </header>

      <GlassCard className="p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={ref}
              onChange={(e) => setRef(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && search()}
              placeholder="Numéro de référence (ex. EDG-2026-000123)"
              className="h-10 rounded-full pl-9"
            />
          </div>
          <Button onClick={search} disabled={loading || !ref.trim()} className="rounded-full">
            {loading ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> : <Search className="mr-1.5 h-4 w-4" />}
            Rechercher
          </Button>
        </div>
      </GlassCard>

      {searched && notFound && (
        <GlassCard className="flex flex-col items-center gap-2 p-10 text-center text-muted-foreground">
          <SearchX className="h-8 w-8" />
          <p className="text-sm">Aucun ticket ne correspond à cette référence.</p>
        </GlassCard>
      )}

      {ticket && (
        <>
          <GlassCard className="space-y-4 p-4 sm:p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold">{ticket.ref}</span>
                  <StatusBadge status={ticket.status} />
                  <PriorityBadge priority={ticket.priority} />
                </div>
                <h2 className="mt-1.5 text-lg font-semibold">{ticket.title}</h2>
              </div>
              <Link
                to="/app/admin/tickets/$id"
                params={{ id: ticket.id }}
                className="inline-flex items-center gap-1.5 rounded-full border border-border/50 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:bg-foreground/5 hover:text-foreground"
              >
                Fiche complète <ExternalLink className="h-3.5 w-3.5" />
              </Link>
            </div>

            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-xl border border-primary/30 bg-primary/5 p-3">
                <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-primary">
                  <UserCircle2 className="h-3.5 w-3.5" /> Position actuelle
                </div>
                <div className="mt-1 text-sm font-semibold">{currentHolder}</div>
              </div>
              <div className="rounded-xl border border-border/40 bg-background/40 p-3">
                <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">Demandeur</div>
                <div className="mt-1 text-sm font-semibold">{ticket.requesterName}</div>
              </div>
              <div className="rounded-xl border border-border/40 bg-background/40 p-3">
                <div className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                  <Flag className="h-3.5 w-3.5" /> Créé le
                </div>
                <div className="mt-1 text-sm font-semibold">{formatInterventionDateTime(ticket.createdAt)}</div>
              </div>
            </div>
          </GlassCard>

          <GlassCard className="overflow-hidden p-0">
            <div className="flex items-center gap-1.5 border-b border-border/40 px-4 py-3 text-xs text-muted-foreground">
              <Lock className="h-3.5 w-3.5" /> Vue lecture seule — aucune action possible depuis ce tableau.
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-sm">
                <thead>
                  <tr className="border-b border-border/40 text-left text-xs uppercase tracking-wider text-muted-foreground">
                    <th className="px-4 py-3 font-medium">#</th>
                    <th className="px-4 py-3 font-medium">Intervenant</th>
                    <th className="px-4 py-3 font-medium">Rôle / Service</th>
                    <th className="px-4 py-3 font-medium">Action</th>
                    <th className="px-4 py-3 font-medium">Début</th>
                    <th className="px-4 py-3 font-medium">Fin</th>
                    <th className="px-4 py-3 font-medium">Durée</th>
                    <th className="px-4 py-3 font-medium">Détail</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/30">
                  {rows.map((row, i) => (
                    <tr
                      key={row.key}
                      className={cn(row.current && "bg-primary/5")}
                    >
                      <td className="px-4 py-3 align-top text-muted-foreground">{i + 1}</td>
                      <td className="px-4 py-3 align-top">
                        <div className="flex items-center gap-2">
                          <Avatar className="h-7 w-7 shrink-0">
                            <AvatarFallback className="bg-primary/10 text-[10px] font-semibold text-primary">
                              {initialsFor(row.actorName)}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0">
                            <div className="truncate font-medium">{row.actorName}</div>
                            {row.current && (
                              <span className="inline-flex items-center rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-primary-foreground">
                                Actuel
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 align-top text-muted-foreground">
                        {row.actorRole ?? "—"}
                        {row.actorService && <div className="text-xs">{row.actorService}</div>}
                      </td>
                      <td className="px-4 py-3 align-top">{row.action}</td>
                      <td className="px-4 py-3 align-top text-muted-foreground">{formatInterventionDateTime(row.startedAt)}</td>
                      <td className="px-4 py-3 align-top text-muted-foreground">
                        {row.endedAt ? formatInterventionDateTime(row.endedAt) : (row.current ? "en cours" : "—")}
                      </td>
                      <td className="px-4 py-3 align-top text-muted-foreground">
                        {row.durationSeconds != null ? formatInterventionDuration(row.durationSeconds) : "—"}
                      </td>
                      <td className="max-w-[220px] px-4 py-3 align-top text-muted-foreground">
                        <span className="line-clamp-2">{row.detail ?? "—"}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </GlassCard>
        </>
      )}
    </div>
  );
}
