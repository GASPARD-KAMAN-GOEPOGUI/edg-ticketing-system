import { useMemo, useState } from "react";
import { Filter, Search, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { Intervention } from "@/lib/mock-data";
import { INTERVENTION_STATUS_LABEL, type InterventionStatus } from "@/lib/intervention-utils";

// BR-TRACE-001 — filtres compacts du Journal d'intervention (popover, desktop
// et mobile). Purement client-side sur les interventions déjà chargées.
export type InterventionFilterState = {
  cycle: number | "all";
  actorId: string | "all";
  service: string | "all";
  decision: InterventionStatus | "all";
  withAttachments: boolean;
  slaBreached: boolean;
  search: string;
};

export const DEFAULT_INTERVENTION_FILTERS: InterventionFilterState = {
  cycle: "all",
  actorId: "all",
  service: "all",
  decision: "all",
  withAttachments: false,
  slaBreached: false,
  search: "",
};

function countActiveFilters(f: InterventionFilterState): number {
  let n = 0;
  if (f.cycle !== "all") n++;
  if (f.actorId !== "all") n++;
  if (f.service !== "all") n++;
  if (f.decision !== "all") n++;
  if (f.withAttachments) n++;
  if (f.slaBreached) n++;
  if (f.search.trim()) n++;
  return n;
}

export function InterventionFilters({
  interventions,
  filters,
  onChange,
}: {
  interventions: Intervention[];
  filters: InterventionFilterState;
  onChange: (next: InterventionFilterState) => void;
}) {
  const [open, setOpen] = useState(false);
  const [searchDraft, setSearchDraft] = useState(filters.search);

  const cycles = useMemo(
    () => [...new Set(interventions.map((iv) => iv.cycleNumber))].sort((a, b) => a - b),
    [interventions],
  );
  const actors = useMemo(() => {
    const map = new Map<string, string>();
    for (const iv of interventions) {
      if (iv.actorId) map.set(iv.actorId, iv.actorName ?? iv.actorId);
    }
    return [...map.entries()];
  }, [interventions]);
  const services = useMemo(
    () => [...new Set(interventions.map((iv) => iv.actorServiceLabel).filter((s): s is string => !!s))],
    [interventions],
  );

  const activeCount = countActiveFilters(filters);

  function patch(partial: Partial<InterventionFilterState>) {
    onChange({ ...filters, ...partial });
  }

  function reset() {
    setSearchDraft("");
    onChange(DEFAULT_INTERVENTION_FILTERS);
  }

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={searchDraft}
          onChange={(e) => {
            setSearchDraft(e.target.value);
            patch({ search: e.target.value });
          }}
          placeholder="Rechercher (nom, matricule, travail, motif…)"
          aria-label="Rechercher dans le journal d'intervention"
          className="h-8 w-52 pl-8 text-xs sm:w-64"
        />
      </div>

      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs" aria-label="Filtrer le journal d'intervention">
            <Filter className="h-3.5 w-3.5" />
            Filtres
            {activeCount > 0 && (
              <span className="ml-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-[10px] font-semibold text-primary-foreground">
                {activeCount}
              </span>
            )}
          </Button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-72 space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold">Filtres</p>
            {activeCount > 0 && (
              <button type="button" className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground" onClick={reset}>
                <X className="h-3 w-3" /> Réinitialiser
              </button>
            )}
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Cycle</Label>
            <Select
              value={String(filters.cycle)}
              onValueChange={(v) => patch({ cycle: v === "all" ? "all" : Number(v) })}
            >
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les cycles</SelectItem>
                {cycles.map((c) => <SelectItem key={c} value={String(c)}>Cycle {c}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs">Intervenant</Label>
            <Select value={filters.actorId} onValueChange={(v) => patch({ actorId: v })}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous les intervenants</SelectItem>
                {actors.map(([id, name]) => <SelectItem key={id} value={id}>{name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>

          {services.length > 0 && (
            <div className="space-y-1.5">
              <Label className="text-xs">Service</Label>
              <Select value={filters.service} onValueChange={(v) => patch({ service: v })}>
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous les services</SelectItem>
                  {services.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          <div className="space-y-1.5">
            <Label className="text-xs">Décision</Label>
            <Select value={filters.decision} onValueChange={(v) => patch({ decision: v as InterventionStatus | "all" })}>
              <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes</SelectItem>
                {(Object.keys(INTERVENTION_STATUS_LABEL) as InterventionStatus[]).map((s) => (
                  <SelectItem key={s} value={s}>{INTERVENTION_STATUS_LABEL[s]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2 pt-1">
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                checked={filters.withAttachments}
                onCheckedChange={(v) => patch({ withAttachments: v === true })}
              />
              Avec pièces jointes
            </label>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                checked={filters.slaBreached}
                onCheckedChange={(v) => patch({ slaBreached: v === true })}
              />
              SLA dépassé
            </label>
          </div>
        </PopoverContent>
      </Popover>
    </div>
  );
}
