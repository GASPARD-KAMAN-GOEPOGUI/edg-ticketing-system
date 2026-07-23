import { createFileRoute, Link } from "@tanstack/react-router";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { DirectionOrgChart } from "@/components/admin/direction-org-chart";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  fetchDepartments,
  fetchDirection,
  fetchUnits,
} from "@/lib/api/directions-units";
import type { Department, Unit } from "@/lib/api/directions-units";
import { buildAvatarUrl, fetchUsers } from "@/lib/api/accounts";
import type { AccountUser } from "@/lib/api/accounts";
import { roleLabels } from "@/lib/session";
import {
  ArrowLeft,
  BadgeCheck,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  ChevronRight,
  GitBranch,
  Home,
  Mail,
  MapPin,
  Maximize2,
  Minimize2,
  Phone,
  RotateCcw,
  Search,
  UserRound,
  Users2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/directions/$id")({
  head: () => ({ meta: [{ title: "Organigramme direction - Admin EDG" }] }),
  component: DirectionDetailPage,
});

type OrgContext = {
  direction: string;
  department?: string;
  departmentId?: string;
  unit?: string;
  unitId?: string;
};

function DirectionDetailPage() {
  const { id } = Route.useParams();
  const [selectedPerson, setSelectedPerson] = useState<AccountUser | null>(null);
  const [query, setQuery] = useState("");
  const [zoom, setZoom] = useState(100);
  const [focusMode, setFocusMode] = useState(false);

  const { data: direction, isLoading: directionLoading } = useQuery({
    queryKey: ["directions", id],
    queryFn: () => fetchDirection(id),
  });

  const { data: departments = [], isLoading: departmentsLoading } = useQuery({
    queryKey: ["departments", "direction", id],
    queryFn: () => fetchDepartments({ directionId: id, status: "active" }),
  });

  const { data: units = [], isLoading: unitsLoading } = useQuery({
    queryKey: ["units", "direction", id],
    queryFn: () => fetchUnits({ directionId: id, status: "active" }),
  });

  const { data: usersData, isLoading: usersLoading } = useQuery({
    queryKey: ["admin", "users", "org-tree"],
    queryFn: () => fetchUsers({ limit: 200 }),
  });

  const users = useMemo(() => usersData?.items ?? [], [usersData?.items]);
  const isLoading = directionLoading || departmentsLoading || unitsLoading || usersLoading;

  const usersByUnity = useMemo(() => {
    const allowedUnityIds = new Set<string>([
      id,
      ...departments.map((department) => department.id),
      ...units.map((unit) => unit.id),
    ]);
    const map = new Map<string, AccountUser[]>();
    for (const user of users) {
      if (!user.unit_id || !allowedUnityIds.has(user.unit_id)) continue;
      const list = map.get(user.unit_id) ?? [];
      list.push(user);
      map.set(user.unit_id, list);
    }
    return map;
  }, [departments, id, units, users]);

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center text-sm text-muted-foreground">
        Chargement de l'organigramme...
      </div>
    );
  }

  if (!direction) {
    return (
      <div className="mx-auto max-w-xl py-16 text-center">
        <h1 className="text-2xl font-bold">Direction introuvable</h1>
        <Button asChild className="mt-4 rounded-full" variant="outline">
          <Link to="/app/admin/directions">Retour aux directions</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className={cn("mx-auto space-y-6", focusMode ? "max-w-none" : "max-w-7xl")}>
      <header className="space-y-4">
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Link to="/app/admin/org" className="inline-flex items-center gap-1 transition hover:text-foreground">
            <Home className="h-3.5 w-3.5" />
            Administration
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <Link to="/app/admin/directions" className="transition hover:text-foreground">
            Directions
          </Link>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-foreground">{direction.name}</span>
        </div>

        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <Button asChild variant="ghost" className="mb-3 rounded-full px-0 text-muted-foreground hover:bg-transparent hover:text-foreground">
              <Link to="/app/admin/directions">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Retour
              </Link>
            </Button>
            <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
              <GitBranch className="h-3 w-3" />
              Organigramme
            </div>
            <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Organigramme</h1>
            <p className="mt-1 text-sm text-muted-foreground">{direction.name}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="h-10 w-64 rounded-full border border-border/60 bg-background/50 pl-9 pr-3 text-sm outline-none transition placeholder:text-muted-foreground focus:border-primary/60"
                placeholder="Rechercher..."
              />
            </div>
            <ControlButton label="Zoom arrière" onClick={() => setZoom((value) => Math.max(75, value - 10))}>
              <ZoomOut className="h-4 w-4" />
            </ControlButton>
            <span className="grid h-10 min-w-16 place-items-center rounded-full border border-border/60 bg-background/50 text-xs font-semibold">
              {zoom}%
            </span>
            <ControlButton label="Zoom avant" onClick={() => setZoom((value) => Math.min(130, value + 10))}>
              <ZoomIn className="h-4 w-4" />
            </ControlButton>
            <ControlButton label="Réinitialiser" onClick={() => setZoom(100)}>
              <RotateCcw className="h-4 w-4" />
            </ControlButton>
            <ControlButton label={focusMode ? "Réduire" : "Plein écran"} onClick={() => setFocusMode((value) => !value)}>
              {focusMode ? <Minimize2 className="h-4 w-4" /> : <Maximize2 className="h-4 w-4" />}
            </ControlButton>
          </div>
        </div>
      </header>

      <DirectionOrgChart
        direction={direction}
        departments={departments}
        units={units}
        usersByUnity={usersByUnity}
        search={query}
        zoom={zoom}
        onSelectPerson={setSelectedPerson}
      />

      <PersonSheet
        person={selectedPerson}
        open={!!selectedPerson}
        onOpenChange={(open) => !open && setSelectedPerson(null)}
        directionName={direction.name}
        departments={departments}
        units={units}
        usersByUnity={usersByUnity}
        onSelectPerson={setSelectedPerson}
      />
    </div>
  );
}

function PersonSheet({
  person,
  open,
  onOpenChange,
  directionName,
  departments,
  units,
  usersByUnity,
  onSelectPerson,
}: {
  person: AccountUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  directionName: string;
  departments: Department[];
  units: Unit[];
  usersByUnity: Map<string, AccountUser[]>;
  onSelectPerson: (person: AccountUser) => void;
}) {
  const org = person ? resolvePersonOrg(person, directionName, departments, units) : null;
  const superior = person && org ? resolveSuperior(person, org, usersByUnity, departments, units) : "";
  const subordinates = person && org ? resolveSubordinates(person, org, usersByUnity, departments, units) : [];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full overflow-y-auto border-l border-border/60 bg-background/95 sm:max-w-md">
        <SheetHeader>
          <SheetTitle>Détails de l'employé</SheetTitle>
        </SheetHeader>
        {person && (
          <div className="mt-6 space-y-6">
            <div className="flex flex-col items-center text-center">
              <PersonAvatar person={person} className="h-24 w-24 border-2 border-primary/45" />
              <span className="mt-3 rounded-full bg-primary/15 px-3 py-1 text-xs font-semibold text-primary">
                {roleLabels[person.role as keyof typeof roleLabels] || person.role}
              </span>
              <h2 className="mt-3 text-xl font-bold uppercase tracking-wide">{fullName(person)}</h2>
              <p className="text-sm text-muted-foreground">{person.job || "Fonction non renseignée"}</p>
            </div>

            <div className="space-y-1 rounded-2xl border border-border/50 bg-muted/15 p-3 text-sm">
              <InfoLine icon={<BadgeCheck className="h-4 w-4" />} label="Matricule" value={person.matricule} />
              <InfoLine icon={<Mail className="h-4 w-4" />} label="Email" value={person.email} />
              <InfoLine icon={<Phone className="h-4 w-4" />} label="Téléphone" value={person.phone} />
              <InfoLine icon={<BriefcaseBusiness className="h-4 w-4" />} label="Fonction" value={person.job} />
              <InfoLine icon={<Building2 className="h-4 w-4" />} label="Direction" value={org?.direction} />
              <InfoLine icon={<GitBranch className="h-4 w-4" />} label="Département" value={org?.department} />
              <InfoLine icon={<Users2 className="h-4 w-4" />} label="Service / Unité" value={org?.unit} />
              <InfoLine icon={<UserRound className="h-4 w-4" />} label="Supérieur hiérarchique" value={superior} />
              <InfoLine icon={<BadgeCheck className="h-4 w-4" />} label="Statut" value={accountStatusLabel(person.account_status)} />
              <InfoLine icon={<CalendarDays className="h-4 w-4" />} label="Date d'embauche" value={undefined} />
              <InfoLine icon={<MapPin className="h-4 w-4" />} label="Adresse" value={undefined} />
            </div>

            <div>
              <div className="mb-3 flex items-center justify-between gap-2">
                <span className="text-sm font-semibold">Subordonnés directs</span>
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary">{subordinates.length}</span>
              </div>
              {subordinates.length > 0 ? (
                <div className="grid grid-cols-2 gap-2">
                  {subordinates.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      aria-label={`Voir le profil de ${fullName(item)}`}
                      title={fullName(item)}
                      onClick={(event) => {
                        event.preventDefault();
                        event.stopPropagation();
                        onSelectPerson(item);
                      }}
                      className="flex min-w-0 cursor-pointer items-center gap-2 rounded-xl border border-border/40 bg-background/50 px-2 py-2 text-left transition hover:border-primary/45 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
                    >
                      <PersonAvatar person={item} className="h-9 w-9" />
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-semibold">{fullName(item)}</span>
                        <span className="block truncate text-[11px] text-muted-foreground">{item.job || item.role}</span>
                      </span>
                    </button>
                  ))}
                </div>
              ) : (
                <p className="rounded-xl border border-dashed border-border/50 px-3 py-4 text-sm text-muted-foreground">
                  Aucun subordonné direct identifié dans les données disponibles.
                </p>
              )}
            </div>
          </div>
        )}
      </SheetContent>
    </Sheet>
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

function ControlButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="icon"
      className="h-10 w-10 rounded-full"
      onClick={onClick}
      title={label}
      aria-label={label}
    >
      {children}
    </Button>
  );
}

function InfoLine({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value?: string;
}) {
  return (
    <div className="grid grid-cols-[1rem_1fr_1.3fr] gap-3 border-b border-border/30 py-2 last:border-0">
      <span className="mt-0.5 text-primary">{icon}</span>
      <span className="text-muted-foreground">{label}</span>
      <span className="min-w-0 text-right font-medium">{value || "-"}</span>
    </div>
  );
}

function resolvePersonOrg(person: AccountUser, directionName: string, departments: Department[], units: Unit[]): OrgContext {
  const unit = units.find((item) => item.id === person.unit_id);
  const department = departments.find((item) => item.id === person.unit_id || item.id === unit?.department_id);
  return {
    direction: directionName,
    department: department?.name,
    departmentId: department?.id,
    unit: unit?.name,
    unitId: unit?.id,
  };
}

function resolveSuperior(
  person: AccountUser,
  org: OrgContext,
  usersByUnity: Map<string, AccountUser[]>,
  departments: Department[],
  units: Unit[],
) {
  if (person.role === "director") return "Direction Générale ou hiérarchie supérieure";
  if (org.unitId) {
    const unitChief = (usersByUnity.get(org.unitId) ?? []).find((candidate) => candidate.role === "chief" && candidate.id !== person.id);
    if (unitChief) return fullName(unitChief);
  }
  if (org.departmentId) {
    const departmentChief = (usersByUnity.get(org.departmentId) ?? []).find((candidate) => candidate.role === "chief" && candidate.id !== person.id);
    if (departmentChief) return fullName(departmentChief);
  }
  const director = [...usersByUnity.values()]
    .flat()
    .find((candidate) => candidate.role === "director" && candidate.id !== person.id);
  if (director) return fullName(director);
  if (departments.length > 0 || units.length > 0) return "Non renseigné";
  return "";
}

function resolveSubordinates(
  person: AccountUser,
  org: OrgContext,
  usersByUnity: Map<string, AccountUser[]>,
  departments: Department[],
  units: Unit[],
) {
  if (person.role === "director") {
    const departmentChiefs = departments.flatMap((department) =>
      (usersByUnity.get(department.id) ?? []).filter((candidate) => candidate.role === "chief"),
    );
    const legacyChiefs = units
      .filter((unit) => !unit.department_id)
      .flatMap((unit) => (usersByUnity.get(unit.id) ?? []).filter((candidate) => candidate.role === "chief"));
    return [...departmentChiefs, ...legacyChiefs].filter((candidate) => candidate.id !== person.id);
  }
  if (org.departmentId && !org.unitId) {
    const serviceChiefs = units
      .filter((unit) => unit.department_id === org.departmentId)
      .flatMap((unit) => (usersByUnity.get(unit.id) ?? []).filter((candidate) => candidate.role === "chief"));
    return serviceChiefs.filter((candidate) => candidate.id !== person.id);
  }
  if (org.unitId && person.role === "chief") {
    return (usersByUnity.get(org.unitId) ?? []).filter((candidate) => candidate.id !== person.id && candidate.role !== "chief");
  }
  return [];
}

function fullName(person: AccountUser) {
  return person.firstname ? `${person.firstname} ${person.name}` : person.name;
}

function accountStatusLabel(status: string | undefined) {
  if (!status) return undefined;
  if (status === "active") return "Actif";
  if (status === "inactive") return "Inactif";
  return status;
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
