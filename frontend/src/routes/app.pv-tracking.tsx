import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { prefetch } from "@/lib/prefetch";
import { useQuery } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { AsyncSwap } from "@/components/async-states";
import { fetchPvTracking } from "@/lib/api/requests";
import { ClipboardList, Archive, Send, Clock, ClipboardCheck } from "lucide-react";
import { format } from "date-fns";
import { fr } from "date-fns/locale";
import { cn } from "@/lib/utils";
import type { RequestItem } from "@/lib/mock-data";

// TSI — Tableau de Suivi des Interventions, livrable de la tâche 3.4 de la
// procédure EDG/PS-GSI/Pro-02. Espace du chef de division support (l'admin y
// accède aussi, rôle bypass habituel comme sur les autres espaces métier).
const PAGE_ACCESS_ROLES = ["chef-division-support", "admin"] as const;

export const Route = createFileRoute("/app/pv-tracking")({
  beforeLoad: () => requireRole(...PAGE_ACCESS_ROLES),
  head: () => ({ meta: [{ title: "Suivi des interventions — EDG Support" }] }),
  loader: ({ context: { queryClient } }) =>
    prefetch(queryClient.ensureQueryData({
      queryKey: ["pv-tracking"],
      queryFn: () => fetchPvTracking({ limit: 100 }),
      staleTime: 20_000,
    })),
  component: PvTrackingPage,
});

/** Étape du PV dans son circuit : établi → soumis (3.3) → archivé (3.4). */
function pvStage(req: RequestItem): { label: string; tone: string; icon: typeof Send } {
  if (req.pvArchivedAt) {
    return { label: "Archivé", tone: "text-success border-success/40 bg-success/10", icon: Archive };
  }
  if (req.pvSubmittedAt) {
    return { label: "À archiver", tone: "text-primary border-primary/40 bg-primary/10", icon: Send };
  }
  // Tâche 3.2 — le demandeur a validé, l'intervenant doit maintenant soumettre.
  if (req.pvValidatedAt) {
    return { label: "À soumettre", tone: "text-info border-info/40 bg-info/10", icon: ClipboardCheck };
  }
  return {
    label: "En cours",
    tone: "text-muted-foreground border-border/50 bg-muted/40",
    icon: Clock,
  };
}

function dateLabel(value?: string): string {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? "—" : format(parsed, "d MMM yyyy", { locale: fr });
}

function PvTrackingPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["pv-tracking"],
    queryFn: () => fetchPvTracking({ limit: 100 }),
    staleTime: 20_000,
  });
  const rows: RequestItem[] = data?.items ?? [];

  const toArchive = rows.filter((r) => r.pvSubmittedAt && !r.pvArchivedAt).length;

  const listState: "loading" | "empty" | "error" | "ready" = isLoading
    ? "loading"
    : isError
      ? "error"
      : rows.length === 0
        ? "empty"
        : "ready";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header>
        <div className="flex items-center gap-2">
          <ClipboardList className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
            Suivi des interventions
          </h1>
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          Les interventions que vous avez réparties, suivies jusqu'à l'archivage de
          leur PV.
          {toArchive > 0 && (
            <>
              {" "}
              <span className="font-semibold text-primary">
                {toArchive} PV en attente d'archivage.
              </span>
            </>
          )}
        </p>
      </header>

      <AsyncSwap
        state={listState}
        empty={
          <GlassCard className="py-16 text-center">
            <div className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted">
              <ClipboardList className="h-6 w-6 text-muted-foreground" />
            </div>
            <h3 className="font-semibold">Aucune intervention à suivre</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Les tickets que vous répartirez apparaîtront ici.
            </p>
          </GlassCard>
        }
      >
        <GlassCard className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[56rem] text-sm">
              <thead className="border-b border-border/40 bg-muted/30 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 font-semibold">Réf.</th>
                  <th className="px-4 py-3 font-semibold">Objet</th>
                  <th className="px-4 py-3 font-semibold">Intervenant</th>
                  <th className="px-4 py-3 font-semibold">Statut ticket</th>
                  <th className="px-4 py-3 font-semibold">Validé</th>
                  <th className="px-4 py-3 font-semibold">PV soumis</th>
                  <th className="px-4 py-3 font-semibold">PV archivé</th>
                  <th className="px-4 py-3 font-semibold">Étape</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((req) => {
                  const stage = pvStage(req);
                  return (
                    <tr key={req.id} className="border-b border-border/25 last:border-0 hover:bg-foreground/3">
                      <td className="px-4 py-3">
                        <Link
                          to="/app/requests/$id"
                          params={{ id: req.id }}
                          className="font-mono text-[11px] text-primary hover:underline"
                        >
                          {req.ref}
                        </Link>
                      </td>
                      <td className="max-w-xs px-4 py-3">
                        <span className="line-clamp-1 font-medium">{req.title}</span>
                        <PriorityBadge priority={req.priority} />
                      </td>
                      <td className="px-4 py-3">
                        <span className="block">{req.intervenantName ?? "—"}</span>
                        {req.intervenantBadge && req.intervenantBadge !== req.intervenantName && (
                          <span className="font-mono text-[11px] text-muted-foreground">
                            {req.intervenantBadge}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3"><StatusBadge status={req.status} /></td>
                      <td className="px-4 py-3 text-muted-foreground">{dateLabel(req.pvValidatedAt)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{dateLabel(req.pvSubmittedAt)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{dateLabel(req.pvArchivedAt)}</td>
                      <td className="px-4 py-3">
                        <span className={cn(
                          "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium",
                          stage.tone,
                        )}>
                          <stage.icon className="h-3 w-3" />
                          {stage.label}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </GlassCard>
      </AsyncSwap>
    </div>
  );
}
