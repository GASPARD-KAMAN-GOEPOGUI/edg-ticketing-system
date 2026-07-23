import { useMemo, useState } from "react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { GlassCard } from "@/components/glass-card";
import type { Direction, Department, Unit } from "@/lib/api/directions-units";
import { buildAvatarUrl } from "@/lib/api/accounts";
import type { AccountUser } from "@/lib/api/accounts";
import { roleLabels } from "@/lib/session";
import { Building2, ChevronDown, ChevronRight, GitBranch, UserRound, Users2 } from "lucide-react";
import { cn } from "@/lib/utils";

type DirectionOrgChartProps = {
  direction: Direction;
  departments: Department[];
  units: Unit[];
  usersByUnity: Map<string, AccountUser[]>;
  search: string;
  zoom: number;
  onSelectPerson: (person: AccountUser) => void;
};

export function DirectionOrgChart({
  direction,
  departments,
  units,
  usersByUnity,
  search,
  zoom,
  onSelectPerson,
}: DirectionOrgChartProps) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const normalizedSearch = search.trim().toLowerCase();

  const unitsByDepartment = useMemo(() => {
    const map = new Map<string, Unit[]>();
    for (const unit of units) {
      if (!unit.department_id) continue;
      const list = map.get(unit.department_id) ?? [];
      list.push(unit);
      map.set(unit.department_id, list);
    }
    return map;
  }, [units]);

  const legacyUnits = useMemo(() => units.filter((unit) => !unit.department_id), [units]);

  const directors = useMemo(
    () => (usersByUnity.get(direction.id) ?? []).filter((user) => user.role === "director"),
    [direction.id, usersByUnity],
  );

  const visibleDepartments = useMemo(() => {
    if (!normalizedSearch) return departments;
    return departments.filter((department) => {
      const departmentPeople = usersByUnity.get(department.id) ?? [];
      const departmentUnits = unitsByDepartment.get(department.id) ?? [];
      const unitPeople = departmentUnits.flatMap((unit) => usersByUnity.get(unit.id) ?? []);
      return (
        includes(department.name, normalizedSearch) ||
        departmentPeople.some((person) => personMatches(person, normalizedSearch)) ||
        departmentUnits.some((unit) => includes(unit.name, normalizedSearch)) ||
        unitPeople.some((person) => personMatches(person, normalizedSearch))
      );
    });
  }, [departments, normalizedSearch, unitsByDepartment, usersByUnity]);

  const visibleLegacyUnits = useMemo(() => {
    if (!normalizedSearch) return legacyUnits;
    return legacyUnits.filter((unit) => {
      const people = usersByUnity.get(unit.id) ?? [];
      return includes(unit.name, normalizedSearch) || people.some((person) => personMatches(person, normalizedSearch));
    });
  }, [legacyUnits, normalizedSearch, usersByUnity]);

  const allPeopleCount = [...usersByUnity.values()].reduce((total, people) => total + people.length, 0);
  const hasBranches = visibleDepartments.length > 0 || visibleLegacyUnits.length > 0;

  function toggle(key: string) {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <GlassCard className="overflow-hidden p-0">
      <div className="border-b border-border/40 bg-background/35 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="grid h-12 w-12 place-items-center rounded-2xl bg-primary/15 text-lg font-bold text-primary">
              {initials(direction.name)}
            </span>
            <div>
              <p className="font-semibold">{direction.name}</p>
              <p className="text-xs text-muted-foreground">
                {departments.length} département{departments.length !== 1 ? "s" : ""} · {units.length} service
                {units.length !== 1 ? "s" : ""} · {allPeopleCount} collaborateur{allPeopleCount !== 1 ? "s" : ""}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2 text-xs">
            <Legend tone="director" label="Directeur" />
            <Legend tone="department" label="Chef de département" />
            <Legend tone="service" label="Chef de service" />
            <Legend tone="member" label="Collaborateur" />
          </div>
        </div>
      </div>

      <div className="overflow-auto bg-[radial-gradient(circle_at_top,rgba(0,174,66,0.14),transparent_34%),linear-gradient(180deg,rgba(0,0,0,0.04),transparent)] px-4 py-8">
        <div
          className="mx-auto min-w-[1120px] origin-top pb-8 transition-transform duration-200"
          style={{ transform: `scale(${zoom / 100})` }}
        >
          <div className="flex flex-col items-center">
            <div className="flex flex-wrap justify-center gap-8">
              {directors.length > 0 ? (
                directors.map((person) => (
                  <PersonNode
                    key={person.id}
                    person={person}
                    tone="director"
                    subtitle={person.job || "Directeur"}
                    onSelect={onSelectPerson}
                    size="large"
                  />
                ))
              ) : (
                <PlaceholderNode
                  title="Poste directeur"
                  subtitle="Aucun directeur affecté"
                  tone="director"
                  badge="Directeur"
                  icon={<Building2 className="h-7 w-7" />}
                  size="large"
                />
              )}
            </div>

            <ConnectorDown />

            {hasBranches ? (
              <div className="relative flex w-full items-start justify-center gap-8 px-8 pt-9">
                <div className="absolute left-[8%] right-[8%] top-0 h-px bg-primary/35" />

                {visibleDepartments.map((department) => (
                  <DepartmentBranch
                    key={department.id}
                    department={department}
                    units={unitsByDepartment.get(department.id) ?? []}
                    usersByUnity={usersByUnity}
                    collapsed={collapsed}
                    onToggle={toggle}
                    onSelectPerson={onSelectPerson}
                  />
                ))}

                {visibleLegacyUnits.length > 0 && (
                  <LegacyBranch
                    units={visibleLegacyUnits}
                    usersByUnity={usersByUnity}
                    onSelectPerson={onSelectPerson}
                  />
                )}
              </div>
            ) : (
              <EmptyPyramid searchActive={Boolean(normalizedSearch)} />
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function DepartmentBranch({
  department,
  units,
  usersByUnity,
  collapsed,
  onToggle,
  onSelectPerson,
}: {
  department: Department;
  units: Unit[];
  usersByUnity: Map<string, AccountUser[]>;
  collapsed: Set<string>;
  onToggle: (key: string) => void;
  onSelectPerson: (person: AccountUser) => void;
}) {
  const key = `department:${department.id}`;
  const isCollapsed = collapsed.has(key);
  const chiefs = (usersByUnity.get(department.id) ?? []).filter((person) => person.role === "chief");
  const departmentMembers = (usersByUnity.get(department.id) ?? []).filter((person) => person.role !== "chief");

  return (
    <section className="relative flex min-w-[290px] max-w-[350px] flex-1 flex-col items-center">
      <span className="absolute -top-9 left-1/2 h-9 w-px -translate-x-1/2 bg-primary/35" />

      <button
        type="button"
        onClick={() => onToggle(key)}
        className="mb-4 inline-flex max-w-full items-center gap-2 rounded-full border border-border/60 bg-background/75 px-3 py-1.5 text-xs font-medium text-muted-foreground transition hover:border-primary/50 hover:text-foreground"
      >
        {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
        <span className="truncate">{department.name}</span>
      </button>

      <div className="flex flex-wrap justify-center gap-4">
        {chiefs.length > 0 ? (
          chiefs.map((person) => (
            <PersonNode
              key={person.id}
              person={person}
              tone="department"
              subtitle={department.name}
              onSelect={onSelectPerson}
            />
          ))
        ) : (
          <PlaceholderNode
            title="Chef de département"
            subtitle={department.name}
            tone="department"
            icon={<GitBranch className="h-5 w-5" />}
          />
        )}
      </div>

      {!isCollapsed && (
        <>
          <ConnectorDown short />

          {units.length > 0 ? (
            <div className="relative grid w-full grid-cols-1 gap-6">
              {units.length > 1 && <div className="absolute left-[20%] right-[20%] top-0 h-px bg-primary/25" />}
              {units.map((unit) => (
                <UnitBranch
                  key={unit.id}
                  unit={unit}
                  people={usersByUnity.get(unit.id) ?? []}
                  onSelectPerson={onSelectPerson}
                />
              ))}
            </div>
          ) : (
            <EmptyServiceChain />
          )}

          {departmentMembers.length > 0 && (
            <div className="mt-5 w-full rounded-2xl border border-border/45 bg-background/45 p-3">
              <p className="mb-3 text-center text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
                Membres rattachés
              </p>
              <MemberGrid people={departmentMembers} onSelectPerson={onSelectPerson} />
            </div>
          )}
        </>
      )}
    </section>
  );
}

function UnitBranch({
  unit,
  people,
  onSelectPerson,
}: {
  unit: Unit;
  people: AccountUser[];
  onSelectPerson: (person: AccountUser) => void;
}) {
  const chiefs = people.filter((person) => person.role === "chief");
  const members = people.filter((person) => person.role !== "chief");

  return (
    <section className="relative flex flex-col items-center rounded-3xl border border-emerald-500/20 bg-background/40 p-4">
      <span className="absolute -top-9 left-1/2 h-9 w-px -translate-x-1/2 bg-primary/25" />
      <p className="mb-4 max-w-64 truncate text-center text-xs font-semibold uppercase tracking-wide text-emerald-400">
        {unit.name}
      </p>

      <div className="flex flex-wrap justify-center gap-4">
        {chiefs.length > 0 ? (
          chiefs.map((person) => (
            <PersonNode
              key={person.id}
              person={person}
              tone="service"
              subtitle={unit.name}
              onSelect={onSelectPerson}
            />
          ))
        ) : (
          <PlaceholderNode
            title="Chef de service"
            subtitle={unit.name}
            tone="service"
            icon={<Building2 className="h-5 w-5" />}
          />
        )}
      </div>

      <ConnectorDown short />

      {members.length > 0 ? (
        <MemberGrid people={members} onSelectPerson={onSelectPerson} />
      ) : (
        <EmptyMemberGroup compact subtitle="Aucun membre affecté" />
      )}
    </section>
  );
}

function LegacyBranch({
  units,
  usersByUnity,
  onSelectPerson,
}: {
  units: Unit[];
  usersByUnity: Map<string, AccountUser[]>;
  onSelectPerson: (person: AccountUser) => void;
}) {
  return (
    <section className="relative flex min-w-[290px] max-w-[350px] flex-1 flex-col items-center">
      <span className="absolute -top-9 left-1/2 h-9 w-px -translate-x-1/2 bg-primary/35" />
      <div className="mb-4 inline-flex rounded-full border border-dashed border-border/70 bg-background/75 px-3 py-1.5 text-xs font-medium text-muted-foreground">
        Services historiques
      </div>
      <div className="grid w-full grid-cols-1 gap-6">
        {units.map((unit) => (
          <UnitBranch
            key={unit.id}
            unit={unit}
            people={usersByUnity.get(unit.id) ?? []}
            onSelectPerson={onSelectPerson}
          />
        ))}
      </div>
    </section>
  );
}

function EmptyPyramid({ searchActive }: { searchActive: boolean }) {
  return (
    <div className="relative flex w-full flex-col items-center px-8 pt-2">
      <div className="mb-7 rounded-full border border-dashed border-primary/35 bg-background/65 px-4 py-2 text-xs font-medium text-muted-foreground">
        {searchActive ? "Aucune branche trouvée pour cette recherche" : "Structure à compléter"}
      </div>

      <div className="relative flex w-full max-w-5xl items-start justify-center gap-8 px-8 pt-9">
        <div className="absolute left-[12%] right-[12%] top-0 h-px bg-primary/30" />
        {[0, 1, 2].map((branch) => (
          <EmptyDepartmentBranch key={branch} searchActive={searchActive} />
        ))}
      </div>
    </div>
  );
}

function EmptyDepartmentBranch({ searchActive }: { searchActive?: boolean }) {
  return (
    <section className="relative flex min-w-[250px] max-w-[300px] flex-1 flex-col items-center">
      <span className="absolute -top-9 left-1/2 h-9 w-px -translate-x-1/2 bg-primary/30" />
      <PlaceholderNode
        title={searchActive ? "Aucun résultat" : "Chef de département"}
        subtitle={searchActive ? "Modifiez la recherche" : "Département non renseigné"}
        tone="department"
        badge="Département"
        icon={<GitBranch className="h-5 w-5" />}
      />

      <ConnectorDown short />
      <EmptyServiceChain searchActive={searchActive} />
    </section>
  );
}

function EmptyServiceChain({ searchActive }: { searchActive?: boolean }) {
  return (
    <>
      <PlaceholderNode
        title="Chef de service"
        subtitle={searchActive ? "Aucun service trouvé" : "Service / unité non renseigné"}
        tone="service"
        badge="Service / Unité"
        icon={<Building2 className="h-5 w-5" />}
      />

      <ConnectorDown short />

      <EmptyMemberGroup compact subtitle={searchActive ? "Aucun membre trouvé" : "Aucun membre affecté"} />
    </>
  );
}

function PersonNode({
  person,
  tone,
  subtitle,
  onSelect,
  size = "normal",
}: {
  person: AccountUser;
  tone: OrgTone;
  subtitle: string;
  onSelect: (person: AccountUser) => void;
  size?: "normal" | "large";
}) {
  return (
    <button
      type="button"
      aria-label={`Voir le profil de ${fullName(person)}`}
      title={fullName(person)}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onSelect(person);
      }}
      className="group flex w-52 cursor-pointer flex-col items-center rounded-2xl text-center transition hover:-translate-y-1 hover:bg-background/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
    >
      <PersonAvatar
        person={person}
        className={cn(
          "mb-3 border-2 bg-background shadow-xl shadow-black/15 transition group-hover:scale-105",
          size === "large" ? "h-24 w-24" : "h-20 w-20",
          avatarToneClass(tone),
        )}
      />
      <span className={cn("mb-2 rounded-full px-3 py-1 text-[11px] font-semibold shadow-sm", badgeToneClass(tone))}>
        {nodeRoleLabel(tone)}
      </span>
      <span className="max-w-full truncate text-sm font-bold uppercase tracking-wide">{fullName(person)}</span>
      <span className="mt-1 line-clamp-2 text-xs text-muted-foreground">{subtitle}</span>
    </button>
  );
}

function PlaceholderNode({
  title,
  subtitle,
  tone,
  icon,
  badge,
  size = "normal",
}: {
  title: string;
  subtitle: string;
  tone: OrgTone;
  icon: React.ReactNode;
  badge?: string;
  size?: "normal" | "large";
}) {
  return (
    <div className="flex w-52 flex-col items-center text-center">
      <span
        className={cn(
          "mb-3 grid place-items-center rounded-full border border-dashed bg-background/45 shadow-lg shadow-black/10",
          size === "large" ? "h-24 w-24" : "h-20 w-20",
          avatarToneClass(tone),
        )}
      >
        {icon}
      </span>
      <span className={cn("mb-2 rounded-full px-3 py-1 text-[11px] font-semibold", badgeToneClass(tone))}>
        {badge ?? nodeRoleLabel(tone)}
      </span>
      <span className="max-w-full truncate text-sm font-bold">{title}</span>
      <span className="mt-1 text-xs text-muted-foreground">{subtitle}</span>
    </div>
  );
}

function EmptyMemberGroup({
  subtitle,
  compact,
}: {
  subtitle: string;
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center text-center", compact ? "w-full" : "w-72")}>
      <div className="mb-3 flex items-center justify-center gap-2">
        {[0, 1, 2].map((item) => (
          <span
            key={item}
            className="grid h-11 w-11 place-items-center rounded-full border border-dashed border-border/70 bg-background/40 text-muted-foreground"
          >
            <UserRound className="h-4 w-4" />
          </span>
        ))}
      </div>
      <span className={cn("mb-2 rounded-full px-3 py-1 text-[11px] font-semibold", badgeToneClass("member"))}>
        Membres
      </span>
      <span className="text-sm font-bold">Collaborateurs</span>
      <span className="mt-1 text-xs text-muted-foreground">{subtitle}</span>
    </div>
  );
}

function MemberGrid({
  people,
  onSelectPerson,
}: {
  people: AccountUser[];
  onSelectPerson: (person: AccountUser) => void;
}) {
  return (
    <div className="grid w-full gap-2">
      {people.map((person) => (
        <button
          key={person.id}
          type="button"
          aria-label={`Voir le profil de ${fullName(person)}`}
          title={fullName(person)}
          onClick={(event) => {
            event.preventDefault();
            event.stopPropagation();
            onSelectPerson(person);
          }}
          className="flex min-w-0 cursor-pointer items-center gap-2 rounded-xl border border-border/50 bg-background/60 px-3 py-2 text-left transition hover:border-primary/45 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          <PersonAvatar person={person} className="h-10 w-10" />
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold">{fullName(person)}</span>
            <span className="block truncate text-xs text-muted-foreground">
              {person.job || roleLabels[person.role as keyof typeof roleLabels] || person.role}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}

function PersonAvatar({ person, className }: { person: AccountUser; className?: string }) {
  return (
    <Avatar className={cn("shrink-0 border border-border/60 bg-background", className)}>
      <AvatarImage src={buildAvatarUrl(person.avatar)} alt={fullName(person)} />
      <AvatarFallback className="bg-primary/10 text-primary">{initials(fullName(person))}</AvatarFallback>
    </Avatar>
  );
}

function ConnectorDown({ short }: { short?: boolean }) {
  return <span className={cn("block w-px bg-primary/35", short ? "my-5 h-8" : "my-0 h-12")} />;
}

function Legend({
  tone,
  label,
}: {
  tone: OrgTone;
  label: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full border px-3 py-1", badgeToneClass(tone))}>
      <span className="h-2 w-2 rounded-full bg-current" />
      {label}
    </span>
  );
}

type OrgTone = "director" | "department" | "service" | "member";

function avatarToneClass(tone: OrgTone) {
  return cn(
    tone === "director" && "border-primary/55 text-primary",
    tone === "department" && "border-sky-500/55 text-sky-400",
    tone === "service" && "border-emerald-500/55 text-emerald-400",
    tone === "member" && "border-border/70 text-muted-foreground",
  );
}

function badgeToneClass(tone: OrgTone) {
  return cn(
    tone === "director" && "border-primary/30 bg-primary/12 text-primary",
    tone === "department" && "border-sky-500/25 bg-sky-500/12 text-sky-300",
    tone === "service" && "border-emerald-500/25 bg-emerald-500/12 text-emerald-300",
    tone === "member" && "border-border bg-muted/35 text-muted-foreground",
  );
}

function nodeRoleLabel(tone: OrgTone) {
  if (tone === "director") return "Directeur";
  if (tone === "department") return "Chef de département";
  if (tone === "service") return "Chef de service";
  return "Collaborateur";
}

function personMatches(person: AccountUser, search: string) {
  return includes(fullName(person), search) || includes(person.job, search) || includes(person.email, search);
}

function includes(value: string | undefined, search: string) {
  return (value ?? "").toLowerCase().includes(search);
}

function fullName(person: AccountUser) {
  return person.firstname ? `${person.firstname} ${person.name}` : person.name;
}

function initials(value: string) {
  return value
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}
