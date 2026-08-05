import { useQuery } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { AsyncSwap } from "@/components/async-states";
import { fetchDecisionReport } from "@/lib/api/reports";
import { cn } from "@/lib/utils";
import { Building2, AlertTriangle, ShieldCheck, ArrowUpRight, ChevronRight } from "lucide-react";

/**
 * Vue agrégée par service — réutilisée par :
 *   - Lot 3 : /app/department-inbox (mode "pilotage", chief-departement, drill-down)
 *   - Lot 4 : /app/strategic-dashboard (mode "strategic", director, lecture seule)
 *
 * Consomme GET /reports/decision?group_by=service, déjà scopé côté backend selon le
 * rôle de l'acteur (_apply_decision_scope) — aucun filtre de périmètre à passer ici.
 */

type ServiceRow = {
  group_key: string;
  service_unity?: string;
  direction?: string;
  total_tickets?: number;
  critical_tickets?: number;
  escalated_tickets?: number;
  sla_compliance_rate?: number;
};

type Props = {
  mode: "pilotage" | "strategic";
  onSelectService?: (unityId: string, label: string) => void;
};

export function AggregatedServiceDashboard({ mode, onSelectService }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["decision-report", "service", mode],
    queryFn: () => fetchDecisionReport({ group_by: "service" }),
    staleTime: 30_000,
  });

  const rows = (data?.tables?.analytical?.rows ?? []) as ServiceRow[];
  const kpis = data?.kpis;
  const listState: "loading" | "empty" | "error" | "ready" = isLoading
    ? "loading"
    : isError
    ? "error"
    : rows.length === 0
    ? "empty"
    : "ready";

  return (
    <div className="space-y-4">
      <header>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {mode === "pilotage" ? "Centre de pilotage" : "Tableau de bord stratégique"}
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {mode === "pilotage"
            ? "Vue agrégée par service de votre département — cliquez sur un service pour voir ses tickets."
            : "Vue consultative agrégée sur l'ensemble de la direction."}
        </p>
      </header>

      {/* Lot 4.1 — Résumé exécutif (mode "strategic" uniquement) : totaux de toute
          la direction, tirés de `kpis` — déjà présent dans la même réponse
          fetchDecisionReport(), aucun appel supplémentaire. */}
      {mode === "strategic" && kpis && (
        <GlassCard strong className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4">
          <SummaryTile label="Tickets (direction)" value={Number(kpis.total_tickets ?? 0)} />
          <SummaryTile
            label="Critiques"
            value={Number(kpis.critical_tickets ?? 0)}
            tone={Number(kpis.critical_tickets ?? 0) > 0 ? "destructive" : "default"}
            icon={AlertTriangle}
          />
          <SummaryTile
            label="Conformité SLA"
            value={`${Math.round(Number(kpis.sla_compliance_rate ?? 0))}%`}
            tone={
              Number(kpis.sla_compliance_rate ?? 0) >= 90 ? "success"
                : Number(kpis.sla_compliance_rate ?? 0) >= 70 ? "warning" : "destructive"
            }
            icon={ShieldCheck}
          />
          <SummaryTile
            label="Escaladés"
            value={Number(kpis.escalated_tickets ?? 0)}
            tone={Number(kpis.escalated_tickets ?? 0) > 0 ? "warning" : "default"}
            icon={ArrowUpRight}
          />
        </GlassCard>
      )}

      <AsyncSwap
        state={listState}
        empty={
          <GlassCard className="py-16 text-center">
            <p className="text-sm text-muted-foreground">Aucune donnée disponible pour cette période.</p>
          </GlassCard>
        }
        error={
          <GlassCard className="py-16 text-center">
            <p className="text-sm text-muted-foreground">Impossible de charger le rapport décisionnel.</p>
          </GlassCard>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {rows.map((row) => {
            const [, unityId] = row.group_key.split("|");
            const clickable = mode === "pilotage" && !!onSelectService && !!unityId && unityId !== "none";
            const slaRate = row.sla_compliance_rate ?? 0;

            return (
              <GlassCard
                key={row.group_key}
                className={cn(
                  "space-y-3 p-4 transition-shadow",
                  clickable && "cursor-pointer hover:shadow-xl",
                  (row.critical_tickets ?? 0) > 0 && "border-destructive/40 bg-destructive/3",
                )}
                onClick={clickable ? () => onSelectService!(unityId, row.service_unity || "Service") : undefined}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <Building2 className="h-3 w-3 shrink-0" />
                      <span className="truncate">{row.direction || "Direction"}</span>
                    </div>
                    <h3 className="truncate font-semibold leading-snug">{row.service_unity || "Service"}</h3>
                  </div>
                  {clickable && <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
                </div>

                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded-xl bg-muted/40 py-2">
                    <div className="text-lg font-bold leading-none">{row.total_tickets ?? 0}</div>
                    <div className="mt-1 text-[10px] text-muted-foreground">Tickets</div>
                  </div>
                  <div className={cn(
                    "rounded-xl py-2",
                    (row.critical_tickets ?? 0) > 0 ? "bg-destructive/10" : "bg-muted/40",
                  )}>
                    <div className={cn(
                      "flex items-center justify-center gap-1 text-lg font-bold leading-none",
                      (row.critical_tickets ?? 0) > 0 && "text-destructive",
                    )}>
                      {(row.critical_tickets ?? 0) > 0 && <AlertTriangle className="h-3.5 w-3.5" />}
                      {row.critical_tickets ?? 0}
                    </div>
                    <div className="mt-1 text-[10px] text-muted-foreground">Critiques</div>
                  </div>
                  <div className="rounded-xl bg-muted/40 py-2">
                    <div className={cn(
                      "flex items-center justify-center gap-1 text-lg font-bold leading-none",
                      slaRate >= 90 ? "text-success" : slaRate >= 70 ? "text-warning-foreground dark:text-warning" : "text-destructive",
                    )}>
                      <ShieldCheck className="h-3.5 w-3.5" />
                      {Math.round(slaRate)}%
                    </div>
                    <div className="mt-1 text-[10px] text-muted-foreground">SLA</div>
                  </div>
                </div>

                {(row.escalated_tickets ?? 0) > 0 && (
                  <div className="flex items-center gap-1.5 rounded-lg bg-orange-600/10 px-2 py-1 text-xs font-medium text-orange-600">
                    <ArrowUpRight className="h-3 w-3" />
                    {row.escalated_tickets} escaladé{(row.escalated_tickets ?? 0) > 1 ? "s" : ""}
                  </div>
                )}
              </GlassCard>
            );
          })}
        </div>
      </AsyncSwap>
    </div>
  );
}

function SummaryTile({
  label,
  value,
  icon: Icon,
  tone = "default",
}: {
  label: string;
  value: string | number;
  icon?: typeof AlertTriangle;
  tone?: "default" | "success" | "warning" | "destructive";
}) {
  return (
    <div className="rounded-2xl bg-background/40 p-3 text-center">
      <div className={cn(
        "flex items-center justify-center gap-1.5 text-2xl font-bold leading-none",
        tone === "success" && "text-success",
        tone === "warning" && "text-warning-foreground dark:text-warning",
        tone === "destructive" && "text-destructive",
      )}>
        {Icon && <Icon className="h-4 w-4" />}
        {value}
      </div>
      <div className="mt-1.5 text-xs text-muted-foreground">{label}</div>
    </div>
  );
}
