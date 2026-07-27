import { createFileRoute, Link } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { Input } from "@/components/ui/input";
import { fetchDepartments, fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Department, Direction, Unit } from "@/lib/api/directions-units";
import {
  Building2,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Eye,
  GitBranch,
  Layers,
  Search,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/org")({
  head: () => ({ meta: [{ title: "Organigramme - Admin EDG" }] }),
  component: OrgChartPage,
});

type ActiveFilter = "all" | "active" | "inactive";

function OrgChartPage() {
  const [search, setSearch] = useState("");
  const [activeFilter, setActiveFilter] = useState<ActiveFilter>("active");
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const { data: directions = [], isLoading: dirsLoading } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections({ status: "all" }),
    staleTime: 5 * 60_000,
  });

  const { data: departments = [], isLoading: depsLoading } = useQuery({
    queryKey: ["departments"],
    queryFn: () => fetchDepartments({ status: "all" }),
    staleTime: 5 * 60_000,
  });

  const { data: units = [], isLoading: unitsLoading } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits({ status: "all" }),
    staleTime: 5 * 60_000,
  });

  const isLoading = dirsLoading || depsLoading || unitsLoading;

  const childrenDirsByParent = useMemo(() => groupBy(directions.filter((d) => d.parent_direction_id), "parent_direction_id"), [directions]);
  const departmentsByDirection = useMemo(() => groupBy(departments, "direction_id"), [departments]);
  const unitsByDepartment = useMemo(() => groupBy(units.filter((unit) => unit.department_id), "department_id"), [units]);
  const legacyUnitsByDirection = useMemo(() => groupBy(units.filter((unit) => !unit.department_id), "direction_id"), [units]);

  const q = search.toLowerCase().trim();

  const visibleDirections = useMemo(() => {
    const rootDirections = directions.filter((direction) => !direction.parent_direction_id);
    return rootDirections.filter((direction) =>
      matchesStatus(direction.status, activeFilter) &&
      matchesDirectionSearch(direction, q, departmentsByDirection, unitsByDepartment, legacyUnitsByDirection, childrenDirsByParent),
    );
  }, [activeFilter, childrenDirsByParent, departmentsByDirection, directions, legacyUnitsByDirection, q, unitsByDepartment]);

  const activeDirCount = directions.filter((direction) => direction.status).length;
  const activeDepartmentCount = departments.filter((department) => department.status).length;
  const activeUnitCount = units.filter((unit) => unit.status).length;

  function toggle(id: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="flex items-center gap-2 text-2xl font-bold">
          <GitBranch className="h-6 w-6 text-primary" />
          Organigramme EDG
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {activeDirCount} direction{activeDirCount !== 1 ? "s" : ""} active{activeDirCount !== 1 ? "s" : ""}
          {" · "}
          {activeDepartmentCount} département{activeDepartmentCount !== 1 ? "s" : ""} actif{activeDepartmentCount !== 1 ? "s" : ""}
          {" · "}
          {activeUnitCount} service{activeUnitCount !== 1 ? "s" : ""} actif{activeUnitCount !== 1 ? "s" : ""}
        </p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Rechercher une direction, un département ou un service..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="pl-9"
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {(["active", "inactive", "all"] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setActiveFilter(filter)}
              className={cn(
                "rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
                activeFilter === filter
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {filter === "active" ? "Actifs" : filter === "inactive" ? "Inactifs" : "Tous"}
            </button>
          ))}
        </div>
      </div>

      {isLoading ? (
        <div className="flex h-40 items-center justify-center text-sm text-muted-foreground">
          Chargement...
        </div>
      ) : visibleDirections.length === 0 ? (
        <GlassCard className="py-12 text-center text-sm text-muted-foreground">
          Aucune structure ne correspond aux critères.
        </GlassCard>
      ) : (
        <div className="space-y-4">
          {visibleDirections.map((direction) => (
            <DirectionNode
              key={direction.id}
              direction={direction}
              childrenDirsByParent={childrenDirsByParent}
              departmentsByDirection={departmentsByDirection}
              unitsByDepartment={unitsByDepartment}
              legacyUnitsByDirection={legacyUnitsByDirection}
              collapsed={collapsed}
              onToggle={toggle}
              activeFilter={activeFilter}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function DirectionNode({
  direction,
  childrenDirsByParent,
  departmentsByDirection,
  unitsByDepartment,
  legacyUnitsByDirection,
  collapsed,
  onToggle,
  activeFilter,
}: {
  direction: Direction;
  childrenDirsByParent: Map<string, Direction[]>;
  departmentsByDirection: Map<string, Department[]>;
  unitsByDepartment: Map<string, Unit[]>;
  legacyUnitsByDirection: Map<string, Unit[]>;
  collapsed: Set<string>;
  onToggle: (id: string) => void;
  activeFilter: ActiveFilter;
}) {
  const departments = (departmentsByDirection.get(direction.id) ?? []).filter((item) => matchesStatus(item.status, activeFilter));
  const legacyUnits = (legacyUnitsByDirection.get(direction.id) ?? []).filter((item) => matchesStatus(item.status, activeFilter));
  const childDirections = (childrenDirsByParent.get(direction.id) ?? []).filter((item) => matchesStatus(item.status, activeFilter));
  const isCollapsed = collapsed.has(`direction:${direction.id}`);

  return (
    <GlassCard className={cn("overflow-hidden p-0", !direction.status && "opacity-70")}>
      <div className="flex items-center justify-between gap-3 border-b border-border/40 px-4 py-3">
        <button
          type="button"
          onClick={() => onToggle(`direction:${direction.id}`)}
          className="flex min-w-0 flex-1 items-center gap-2 text-left"
        >
          {isCollapsed ? <ChevronRight className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
          <Building2 className="h-4 w-4 shrink-0 text-primary" />
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold">{direction.name}</p>
            <p className="text-[11px] text-muted-foreground">
              {departments.length} département{departments.length !== 1 ? "s" : ""} · {legacyUnits.length} service{legacyUnits.length !== 1 ? "s" : ""} direct{legacyUnits.length !== 1 ? "s" : ""}
            </p>
          </div>
        </button>
        <div className="flex shrink-0 items-center gap-2">
          <StatusIcon active={direction.status} />
          <Link
            to={`/app/admin/directions/${direction.id}` as never}
            className="inline-flex h-8 items-center gap-1.5 rounded-full border border-border px-3 text-xs font-medium hover:bg-muted"
          >
            <Eye className="h-3.5 w-3.5" />
            Voir
          </Link>
        </div>
      </div>

      {!isCollapsed && (
        <div className="space-y-3 px-4 py-3">
          {departments.map((department) => (
            <DepartmentNode
              key={department.id}
              department={department}
              units={unitsByDepartment.get(department.id) ?? []}
              collapsed={collapsed}
              onToggle={onToggle}
              activeFilter={activeFilter}
            />
          ))}

          {legacyUnits.length > 0 && (
            <div className="rounded-xl border border-dashed border-border/50 bg-background/20 p-3">
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Services directement rattachés
              </div>
              <div className="grid gap-2 sm:grid-cols-2">
                {legacyUnits.map((unit) => <UnitRow key={unit.id} unit={unit} />)}
              </div>
            </div>
          )}

          {childDirections.map((child) => (
            <DirectionNode
              key={child.id}
              direction={child}
              childrenDirsByParent={childrenDirsByParent}
              departmentsByDirection={departmentsByDirection}
              unitsByDepartment={unitsByDepartment}
              legacyUnitsByDirection={legacyUnitsByDirection}
              collapsed={collapsed}
              onToggle={onToggle}
              activeFilter={activeFilter}
            />
          ))}

          {departments.length === 0 && legacyUnits.length === 0 && childDirections.length === 0 && (
            <p className="py-2 text-xs text-muted-foreground">Aucun département ou service rattaché.</p>
          )}
        </div>
      )}
    </GlassCard>
  );
}

function DepartmentNode({
  department,
  units,
  collapsed,
  onToggle,
  activeFilter,
}: {
  department: Department;
  units: Unit[];
  collapsed: Set<string>;
  onToggle: (id: string) => void;
  activeFilter: ActiveFilter;
}) {
  const visibleUnits = units.filter((unit) => matchesStatus(unit.status, activeFilter));
  const isCollapsed = collapsed.has(`department:${department.id}`);

  return (
    <div className={cn("rounded-xl border border-border/40 bg-background/20", !department.status && "opacity-70")}>
      <button
        type="button"
        onClick={() => onToggle(`department:${department.id}`)}
        className="flex w-full items-center justify-between gap-3 border-b border-border/30 px-3 py-2 text-left"
      >
        <span className="flex min-w-0 items-center gap-2">
          {isCollapsed ? <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />}
          <GitBranch className="h-3.5 w-3.5 text-primary/80" />
          <span className="truncate text-xs font-semibold">{department.name}</span>
        </span>
        <span className="text-[10px] text-muted-foreground">{visibleUnits.length} service{visibleUnits.length !== 1 ? "s" : ""}</span>
      </button>
      {!isCollapsed && (
        <div className="space-y-2 px-3 py-2.5">
          {visibleUnits.length > 0
            ? visibleUnits.map((unit) => <UnitRow key={unit.id} unit={unit} />)
            : <p className="text-xs text-muted-foreground">Aucun service rattaché.</p>}
        </div>
      )}
    </div>
  );
}

function UnitRow({ unit }: { unit: Unit }) {
  return (
    <div className={cn(
      "flex items-center gap-2 rounded-md border border-border/40 bg-muted/25 px-2.5 py-1.5",
      !unit.status && "opacity-60",
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

function StatusIcon({ active }: { active: boolean }) {
  return active
    ? <CheckCircle2 className="h-4 w-4 text-emerald-500" />
    : <XCircle className="h-4 w-4 text-muted-foreground" />;
}

function groupBy<T extends Record<string, unknown>>(items: T[], key: keyof T): Map<string, T[]> {
  const map = new Map<string, T[]>();
  for (const item of items) {
    const value = item[key];
    if (value == null) continue;
    const id = String(value);
    const list = map.get(id) ?? [];
    list.push(item);
    map.set(id, list);
  }
  return map;
}

function matchesStatus(active: boolean, filter: ActiveFilter) {
  if (filter === "active") return active;
  if (filter === "inactive") return !active;
  return true;
}

function matchesDirectionSearch(
  direction: Direction,
  q: string,
  departmentsByDirection: Map<string, Department[]>,
  unitsByDepartment: Map<string, Unit[]>,
  legacyUnitsByDirection: Map<string, Unit[]>,
  childrenDirsByParent: Map<string, Direction[]>,
): boolean {
  if (!q) return true;
  if (`${direction.name} ${direction.code ?? ""}`.toLowerCase().includes(q)) return true;
  const departments = departmentsByDirection.get(direction.id) ?? [];
  if (departments.some((department) => `${department.name} ${department.code ?? ""}`.toLowerCase().includes(q))) return true;
  if (departments.some((department) => (unitsByDepartment.get(department.id) ?? []).some((unit) => `${unit.name} ${unit.code ?? ""}`.toLowerCase().includes(q)))) return true;
  if ((legacyUnitsByDirection.get(direction.id) ?? []).some((unit) => `${unit.name} ${unit.code ?? ""}`.toLowerCase().includes(q))) return true;
  return (childrenDirsByParent.get(direction.id) ?? []).some((child) =>
    matchesDirectionSearch(child, q, departmentsByDirection, unitsByDepartment, legacyUnitsByDirection, childrenDirsByParent),
  );
}
