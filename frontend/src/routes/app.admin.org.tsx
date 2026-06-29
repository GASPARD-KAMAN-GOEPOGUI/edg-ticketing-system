import { createFileRoute } from "@tanstack/react-router";
import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { Input } from "@/components/ui/input";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Unit } from "@/lib/api/directions-units";
import {
  Building2,
  CheckCircle2,
  GitBranch,
  Layers,
  Search,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/org")({
  head: () => ({ meta: [{ title: "Organigramme — Admin EDG" }] }),
  component: OrgChartPage,
});

function DirHeader({ dir, unitCount, activeUnitCount, hasSubDirs }: {
  dir: { name: string; code?: string; status: boolean };
  unitCount: number;
  activeUnitCount: number;
  hasSubDirs: boolean;
}) {
  return (
    <div className={cn(
      "flex items-start justify-between gap-2 border-b border-border/40 px-4 py-3",
      !dir.status && "opacity-60",
    )}>
      <div className="flex min-w-0 items-start gap-2">
        <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold">{dir.name}</p>
          <div className="mt-0.5 flex items-center gap-1.5">
            {dir.code && (
              <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary">
                {dir.code}
              </span>
            )}
            <span className="text-[10px] text-muted-foreground">
              {hasSubDirs
                ? `${activeUnitCount}/${unitCount} service${unitCount !== 1 ? "s" : ""} (toutes sous-directions)`
                : `${activeUnitCount}/${unitCount} service${unitCount !== 1 ? "s" : ""}`}
            </span>
          </div>
        </div>
      </div>
      {dir.status
        ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
        : <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />}
    </div>
  );
}

function UnitRow({ unit }: { unit: Unit }) {
  return (
    <div className={cn(
      "flex items-center gap-2 rounded-md border border-border/40 bg-muted/30 px-2.5 py-1.5",
      !unit.status && "opacity-50",
    )}>
      <Layers className="h-3 w-3 shrink-0 text-muted-foreground" />
      <span className="flex-1 truncate text-xs">{unit.name}</span>
      {unit.code && (
        <span className="font-mono text-[10px] text-muted-foreground">{unit.code}</span>
      )}
      <span className={cn("h-1.5 w-1.5 shrink-0 rounded-full", unit.status ? "bg-emerald-500" : "bg-muted-foreground/40")} />
    </div>
  );
}

type ActiveFilter = "all" | "active" | "inactive";

function OrgChartPage() {
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");

  const { data: directions = [], isLoading: dirsLoading } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const { data: units = [], isLoading: unitsLoading } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });

  const isLoading = dirsLoading || unitsLoading;

  // Group units by direction_id
  const unitsByDir = useMemo(() => {
    const map = new Map<string, Unit[]>();
    for (const unit of units) {
      const key = unit.direction_id ?? "__none__";
      const list = map.get(key) ?? [];
      list.push(unit);
      map.set(key, list);
    }
    return map;
  }, [units]);

  // Group sub-directions by parent_direction_id
  const subDirsByParent = useMemo(() => {
    const map = new Map<string, typeof directions>();
    for (const d of directions) {
      if (!d.parent_direction_id) continue;
      const list = map.get(d.parent_direction_id) ?? [];
      list.push(d);
      map.set(d.parent_direction_id, list);
    }
    return map;
  }, [directions]);

  const q = search.toLowerCase().trim();

  const matchesFilter = (d: (typeof directions)[0]) => {
    if (activeFilter === "active" && !d.status) return false;
    if (activeFilter === "inactive" && d.status) return false;
    return true;
  };

  const matchesSearch = (d: (typeof directions)[0]): boolean => {
    if (!q) return true;
    if (d.name.toLowerCase().includes(q)) return true;
    if (d.code?.toLowerCase().includes(q)) return true;
    if ((unitsByDir.get(d.id) ?? []).some((u) => u.name.toLowerCase().includes(q) || u.code?.toLowerCase().includes(q))) return true;
    return (subDirsByParent.get(d.id) ?? []).some((sub) => matchesSearch(sub));
  };

  // Root directions only (no parent_direction_id)
  const filtered = useMemo(() => {
    return directions.filter(
      (d) => !d.parent_direction_id && matchesFilter(d) && matchesSearch(d),
    );
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [directions, activeFilter, q, unitsByDir, subDirsByParent]);

  const activeDirCount = directions.filter((d) => d.status).length;
  const activeUnitCount = units.filter((u) => u.status).length;

  const orphans = (unitsByDir.get("__none__") ?? []).filter((u) =>
    activeFilter === "all" ? true : activeFilter === "active" ? u.status : !u.status,
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-4 md:p-6">
      {/* Header */}
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <GitBranch className="h-6 w-6 text-primary" />
          Organigramme EDG
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {activeDirCount} direction{activeDirCount !== 1 ? "s" : ""} active{activeDirCount !== 1 ? "s" : ""}
          {" · "}
          {activeUnitCount} service{activeUnitCount !== 1 ? "s" : ""} actif{activeUnitCount !== 1 ? "s" : ""}
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Rechercher une direction ou un service…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {(["active", "inactive", "all"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setActiveFilter(f)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                activeFilter === f
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {f === "active" ? "Actifs" : f === "inactive" ? "Inactifs" : "Tous"}
            </button>
          ))}
        </div>
      </div>

      {/* Org tree */}
      {isLoading ? (
        <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
          Chargement…
        </div>
      ) : filtered.length === 0 ? (
        <GlassCard className="py-12 text-center text-sm text-muted-foreground">
          Aucune direction ne correspond aux critères.
        </GlassCard>
      ) : (
        <div className="space-y-4">
          {filtered.map((dir) => {
            const subDirs = subDirsByParent.get(dir.id) ?? [];
            const dirUnits = unitsByDir.get(dir.id) ?? [];
            const hasSubDirs = subDirs.length > 0;

            return (
              <GlassCard key={dir.id} className="overflow-hidden p-0">
                {/* Root direction header */}
                <DirHeader dir={dir} unitCount={dirUnits.length + subDirs.reduce((acc, s) => acc + (unitsByDir.get(s.id) ?? []).length, 0)} activeUnitCount={dirUnits.filter(u => u.status).length + subDirs.reduce((acc, s) => acc + (unitsByDir.get(s.id) ?? []).filter(u => u.status).length, 0)} hasSubDirs={hasSubDirs} />

                <div className={cn("px-4 py-3", hasSubDirs ? "space-y-3" : "space-y-1.5")}>
                  {/* Sub-directions */}
                  {subDirs.map((sub) => {
                    const subUnits = unitsByDir.get(sub.id) ?? [];
                    const visibleSubUnits = q
                      ? subUnits.filter((u) => u.name.toLowerCase().includes(q) || u.code?.toLowerCase().includes(q))
                      : subUnits;
                    return (
                      <div key={sub.id} className={cn("rounded-xl border border-border/40 bg-background/20 overflow-hidden", !sub.status && "opacity-60")}>
                        {/* Sub-direction header */}
                        <div className="flex items-center justify-between gap-2 border-b border-border/30 bg-muted/20 px-3 py-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <Building2 className="h-3.5 w-3.5 shrink-0 text-primary/70" />
                            <span className="truncate text-xs font-semibold">{sub.name}</span>
                            {sub.code && (
                              <span className="rounded bg-primary/10 px-1.5 py-0.5 font-mono text-[10px] text-primary">
                                {sub.code}
                              </span>
                            )}
                          </div>
                          <div className="flex shrink-0 items-center gap-1.5">
                            <span className="text-[10px] text-muted-foreground">
                              {subUnits.filter(u => u.status).length}/{subUnits.length} service{subUnits.length !== 1 ? "s" : ""}
                            </span>
                            {sub.status
                              ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                              : <XCircle className="h-3.5 w-3.5 text-muted-foreground" />}
                          </div>
                        </div>
                        {/* Sub-direction units */}
                        <div className="space-y-1.5 px-3 py-2.5">
                          {visibleSubUnits.length === 0 ? (
                            <p className="py-1 text-xs text-muted-foreground">
                              {subUnits.length === 0 ? "Aucun service rattaché" : "Aucun service correspondant"}
                            </p>
                          ) : (
                            visibleSubUnits.map((unit) => <UnitRow key={unit.id} unit={unit} />)
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {/* Direct units under root direction */}
                  {(() => {
                    const visibleUnits = q
                      ? dirUnits.filter((u) => u.name.toLowerCase().includes(q) || u.code?.toLowerCase().includes(q))
                      : dirUnits;
                    if (visibleUnits.length === 0 && !hasSubDirs) {
                      return (
                        <p className="py-2 text-xs text-muted-foreground">
                          {dirUnits.length === 0 ? "Aucun service rattaché" : "Aucun service correspondant"}
                        </p>
                      );
                    }
                    return visibleUnits.map((unit) => <UnitRow key={unit.id} unit={unit} />);
                  })()}
                </div>
              </GlassCard>
            );
          })}
        </div>
      )}

      {/* Orphan units — no direction assigned */}
      {orphans.length > 0 && (
        <GlassCard>
          <h3 className="mb-3 text-sm font-medium text-muted-foreground">
            Services sans direction ({orphans.length})
          </h3>
          <div className="space-y-1.5">
            {orphans.map((unit) => (
              <div
                key={unit.id}
                className="flex items-center gap-2 rounded-md border border-dashed border-border px-2.5 py-1.5 text-xs"
              >
                <Layers className="h-3 w-3 text-muted-foreground" />
                <span className="flex-1 truncate">{unit.name}</span>
                {unit.code && (
                  <span className="font-mono text-[10px] text-muted-foreground">
                    {unit.code}
                  </span>
                )}
              </div>
            ))}
          </div>
        </GlassCard>
      )}
    </div>
  );
}
