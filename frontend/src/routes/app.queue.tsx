import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PriorityBadge } from "@/components/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { fetchTriage, fetchRequest, qualifyTriage } from "@/lib/api/requests";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchDirections, fetchDepartments, fetchUnits } from "@/lib/api/directions-units";
import { fetchRoutingRules, fetchRequestCategories } from "@/lib/api/admin-config";
import { priorityLabels } from "@/lib/mock-data";
import type { Priority, Role } from "@/lib/mock-data";
import { toast } from "sonner";
import {
  CheckCircle2, ChevronDown, ChevronUp, History,
  Loader2, MessageSquare, User, UserPlus, Zap,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { AsyncSwap } from "@/components/async-states";
import { StatusBadge } from "@/components/status-badge";
import { useUser } from "@/lib/session";
import { cn } from "@/lib/utils";

type TriageForm = {
  category: string;
  priority: Priority;
  directionId: string;
  departmentId: string;
  unitId: string;
  personId: string;
};

const QUALIFIABLE_STATUSES = new Set(["new", "qualifying", "qualified", "reopened"]);
const TERMINAL_STATUSES = new Set(["cancelled", "closed", "resolved", "rejected"]);
const STATUS_ALIASES: Record<string, string> = {
  cancalled: "cancelled",
  canceled: "cancelled",
  escaladed: "escalated",
};

function normalizeQueueStatus(status?: string) {
  const clean = (status || "new").trim().toLowerCase();
  return STATUS_ALIASES[clean] ?? clean;
}

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];
const OPERATIONAL_ROLES: Role[] = ["agent-support", "chief-service", "chief-departement", "director", "admin"];

export const Route = createFileRoute("/app/queue")({
  // Philosophie collaborative : tous les rôles opérationnels peuvent prendre un
  // ticket de la file d'attente ou devenir l'intervenant courant.
  beforeLoad: () => requireRole("agent-support", "chief-service", "chief-departement", "director", "admin"),
  head: () => ({ meta: [{ title: "File d'attente — EDG Support" }] }),
  component: QueuePage,
});

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

const priorityAvatarClass: Record<Priority, string> = {
  low: "bg-slate-100 text-slate-500 dark:bg-slate-800/50 dark:text-slate-400",
  medium: "bg-sky-100 text-sky-700 dark:bg-sky-950/50 dark:text-sky-300",
  high: "bg-orange-100 text-orange-700 dark:bg-orange-950/50 dark:text-orange-300",
  critical: "bg-red-100 text-red-700 dark:bg-red-950/50 dark:text-red-300",
};

// ── Composant racine ───────────────────────────────────────────────────────────

function QueuePage() {
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <QualifyTab />
    </div>
  );
}

// ── Onglet : À qualifier ──────────────────────────────────────────────────────

function QualifyTab() {
  const sessionUser = useUser();
  const queryClient = useQueryClient();
  const isOperationalRole = Boolean(sessionUser?.role && OPERATIONAL_ROLES.includes(sessionUser.role));
  const canUseAssignForm = isOperationalRole;
  const canTakeRole = isOperationalRole;
  const assignableRoles = sessionUser?.role === "admin"
    ? OPERATIONAL_ROLES
    : OPERATIONAL_ROLES.filter((role) => role !== "admin");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["qualify"],
    queryFn: () => fetchTriage({ limit: 50 }),
    staleTime: 20_000,
  });

  const queue = (data?.items ?? []).filter((req) => {
    const status = normalizeQueueStatus(req.status);
    return QUALIFIABLE_STATUSES.has(status) && !TERMINAL_STATUSES.has(status);
  });
  const [expanded, setExpanded] = useState<string | null>(null);
  const [forms, setForms] = useState<Record<string, TriageForm>>({});

  function getForm(id: string): TriageForm {
    const req = queue.find((r) => r.id === id);
    return forms[id] ?? {
      category: req?.category ?? "",
      priority: (req?.priority as Priority) ?? "medium",
      directionId: req?.directionId ?? "",
      departmentId: "",
      unitId: "",
      personId: "",
    };
  }

  function patchForm(id: string, patch: Partial<TriageForm>) {
    setForms((prev) => ({ ...prev, [id]: { ...getForm(id), ...patch } }));
  }

  const { data: categoryItems = [] } = useQuery({
    queryKey: ["admin-ref", "request_categories"],
    queryFn: fetchRequestCategories,
    staleTime: 300_000,
  });
  const categories = categoryItems.filter((c) => c.status).map((c) => c.label);

  const { data: routingRulesData = [] } = useQuery({
    queryKey: ["routing-rules"],
    queryFn: fetchRoutingRules,
    staleTime: 5 * 60_000,
  });

  const suggestDirection = (category: string) =>
    routingRulesData.find(
      (r) => r.conditionField === "category" && r.conditionValue === category && r.active,
    ) ?? null;

  const { data: realDirections = [] } = useQuery({
    queryKey: ["directions", "active"],
    queryFn: () => fetchDirections({ status: "active" }),
    staleTime: 5 * 60_000,
  });

  const expandedDirectionId = expanded
    ? (forms[expanded]?.directionId ?? queue.find((r) => r.id === expanded)?.directionId ?? "")
    : "";
  const expandedDepartmentId = expanded ? (forms[expanded]?.departmentId ?? "") : "";
  const expandedUnitId = expanded ? (forms[expanded]?.unitId ?? "") : "";

  const { data: expandedDepartments = [] } = useQuery({
    queryKey: ["departments", expandedDirectionId, "active"],
    queryFn: () => fetchDepartments({ directionId: expandedDirectionId, status: "active" }),
    enabled: !!expandedDirectionId,
    staleTime: 5 * 60_000,
  });

  const { data: expandedUnits = [] } = useQuery({
    queryKey: ["units", expandedDepartmentId, "active"],
    queryFn: () => fetchUnits({ departmentId: expandedDepartmentId, status: "active" }),
    enabled: !!expandedDepartmentId,
    staleTime: 5 * 60_000,
  });

  // Intervenants pouvant recevoir un ticket dans la direction sélectionnée :
  // tous les rôles opérationnels, actifs (filtre déjà appliqué côté backend).
  const { data: unitPeopleData } = useQuery({
    queryKey: ["people-by-direction", expandedDirectionId, expandedUnitId, sessionUser?.role],
    queryFn: async () => {
      const scope = expandedDirectionId ? { direction_id: expandedDirectionId } : { unit_id: expandedUnitId };
      const results = await Promise.all(
        assignableRoles.map((role) => fetchUsers({ role, ...scope, limit: 100 })),
      );
      const byId = new Map(
        results.flatMap((result) => result.items).map((person) => [person.id, person]),
      );
      return Array.from(byId.values());
    },
    enabled: (!!expandedDirectionId || !!expandedUnitId) && assignableRoles.length > 0,
    staleTime: 5 * 60_000,
  });
  const unitPeople = unitPeopleData ?? [];

  // BR-REOPEN-QUEUE-001 : détail de la réouverture (motif, ancien intervenant)
  // — chargé à la demande seulement pour la carte dépliée, le endpoint /triage
  // ne renvoyant pas l'historique complet (allégé pour les listes).
  const expandedStatus = expanded
    ? normalizeQueueStatus(queue.find((r) => r.id === expanded)?.status)
    : "";
  const { data: expandedDetail } = useQuery({
    queryKey: ["queue-reopen-detail", expanded],
    queryFn: () => fetchRequest(expanded as string),
    enabled: !!expanded && expandedStatus === "reopened",
    staleTime: 10_000,
  });
  const reopenEvent = expandedDetail?.timeline
    ?.filter((t) => t.type === "reopened")
    .slice(-1)[0];
  const priorHandlerEvent = expandedDetail?.timeline
    ?.filter((t) => t.type === "treatment_completed")
    .slice(-1)[0];

  const qualifyMut = useMutation({
    mutationFn: ({ id, form }: { id: string; form: TriageForm }) =>
      qualifyTriage(
        id,
        {
          category: form.category,
          priority: form.priority,
          direction_id: form.directionId,
          unit_id: form.unitId || undefined,
          assignee_id: form.personId || undefined,
        },
        sessionUser?.id,
      ),
    onSuccess: (_, { id }) => {
      const req = queue.find((r) => r.id === id);
      toast.success(`Ticket ${req?.ref ?? ""} orienté avec succès.`);
      setExpanded(null);
      queryClient.invalidateQueries({ queryKey: ["qualify"] });
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erreur lors de la qualification.");
    },
  });

  const takeMut = useMutation({
    mutationFn: ({ id, data }: {
      id: string;
      data: {
        category: string;
        priority: string;
        direction_id?: string;
        unit_id?: string;
        assignee_id: string;
      };
    }) => qualifyTriage(id, data, sessionUser?.id),
    onSuccess: (_, { id }) => {
      const req = queue.find((r) => r.id === id);
      toast.success(`Ticket ${req?.ref ?? ""} pris en charge.`);
      setExpanded(null);
      queryClient.invalidateQueries({ queryKey: ["qualify"] });
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
      queryClient.invalidateQueries({ queryKey: ["my-tickets-stats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard-stats"] });
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Erreur lors de la prise en charge.");
    },
  });

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || queue.length === 0
    ? "empty"
    : "ready";

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">File d'attente</h1>
          {!isLoading && (
            <p className="mt-1 text-sm text-muted-foreground">
              {queue.length} ticket{queue.length !== 1 ? "s" : ""} en attente de qualification.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-warning/30 bg-warning/10 px-4 py-2 text-sm font-medium text-warning-foreground dark:text-warning">
          <Zap className="h-4 w-4 shrink-0" />
          Aucun ticket ne doit rester non orienté plus de 2h.
        </div>
      </header>

      <AsyncSwap
        state={listState}
        empty={
          isError ? (
            <GlassCard className="py-16 text-center">
              <p className="text-sm text-muted-foreground">Impossible de charger les tickets.</p>
            </GlassCard>
          ) : (
            <GlassCard className="py-16 text-center">
              <CheckCircle2 className="mx-auto h-10 w-10 text-success" />
              <h3 className="mt-3 font-semibold">File de qualification vide</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Tous les tickets ont été qualifiés et orientés.
              </p>
            </GlassCard>
          )
        }
      >
        <div className="space-y-3">
          {queue.map((req) => {
            const isOpen = expanded === req.id;
            const form = getForm(req.id);
            const suggestion = form.category ? suggestDirection(form.category) : null;
            const departments = isOpen ? expandedDepartments : [];
            const services = isOpen ? expandedUnits : [];
            const people = isOpen ? unitPeople : [];
            const canAssign = Boolean(
              form.directionId && form.departmentId && form.unitId && form.personId,
            );
            const isPending = qualifyMut.isPending && qualifyMut.variables?.id === req.id;
            const takeDirectionId = form.directionId || req.directionId || sessionUser?.direction_id || undefined;
            const takeUnitId = form.unitId || sessionUser?.unit_id || req.serviceId || undefined;
            const takeCategory = form.category || req.category || "autre";
            const status = normalizeQueueStatus(req.status);
            const canTake = canTakeRole && QUALIFIABLE_STATUSES.has(status) && !TERMINAL_STATUSES.has(status);
            const takeData = canTake && sessionUser?.id
              ? {
                  category: takeCategory,
                  priority: form.priority || req.priority,
                  ...(takeDirectionId ? { direction_id: takeDirectionId } : {}),
                  ...(takeUnitId ? { unit_id: takeUnitId } : {}),
                  assignee_id: sessionUser.id,
                }
              : null;
            const isTaking = takeMut.isPending && takeMut.variables?.id === req.id;

            return (
              <GlassCard key={req.id} className="overflow-hidden p-0">
                <button
                  className="flex w-full items-start gap-4 p-5 text-left transition-colors hover:bg-foreground/3"
                  onClick={() => setExpanded(isOpen ? null : req.id)}
                >
                  <div className="flex shrink-0 flex-col items-center gap-1.5">
                    <div
                      className={cn(
                        "flex h-9 w-9 items-center justify-center rounded-full",
                        priorityAvatarClass[req.priority || "medium"],
                      )}
                    >
                      <User className="h-4 w-4" />
                    </div>
                    <PriorityBadge priority={req.priority || "medium"} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{req.ref}</span>
                      {status === "reopened" ? (
                        <StatusBadge status="reopened" />
                      ) : (
                        <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-foreground dark:text-accent">
                          Non orientée
                        </span>
                      )}
                    </div>
                    <div className="mt-0.5 font-semibold leading-snug">{req.title}</div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      {req.requesterName && (
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {req.requesterName}
                        </span>
                      )}
                      <span>{formatDistanceToNow(new Date(req.createdAt), { addSuffix: true, locale: fr })}</span>
                    </div>
                  </div>
                  <span className="shrink-0 text-muted-foreground">
                    {isOpen ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
                  </span>
                </button>

                {isOpen && (
                  <div className="space-y-5 border-t border-border/40 bg-background/30 px-5 pb-5 pt-4">
                    {status === "reopened" && (
                      <div className="flex items-start gap-2.5 rounded-xl border border-fuchsia-200 bg-fuchsia-50 px-4 py-3 text-sm dark:border-fuchsia-800/50 dark:bg-fuchsia-950/30">
                        <History className="mt-0.5 h-4 w-4 shrink-0 text-fuchsia-600 dark:text-fuchsia-400" />
                        <div className="space-y-1 text-fuchsia-800 dark:text-fuchsia-300">
                          <p className="font-medium">
                            Ticket réouvert — en attente d'une nouvelle prise en charge.
                          </p>
                          {reopenEvent ? (
                            <>
                              {reopenEvent.comment && (
                                <p><span className="font-medium">Motif :</span> {reopenEvent.comment}</p>
                              )}
                              {priorHandlerEvent?.by && (
                                <p><span className="font-medium">Ancien intervenant :</span> {priorHandlerEvent.by}</p>
                              )}
                              <p className="text-xs opacity-80">
                                Réouvert {formatDistanceToNow(new Date(reopenEvent.at), { addSuffix: true, locale: fr })}
                              </p>
                            </>
                          ) : (
                            <p className="text-xs opacity-80">Chargement du détail de la réouverture…</p>
                          )}
                        </div>
                      </div>
                    )}
                    <p className="text-sm text-muted-foreground">
                      <span className="font-medium text-foreground">Description :</span>{" "}
                      {req.description}
                    </p>

                    {/* Formulaire */}
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label>Catégorie</Label>
                        <Select
                          value={form.category}
                          onValueChange={(v) => {
                            const s = suggestDirection(v);
                            if (s) {
                              const dir = realDirections.find((d) => d.name === s.targetDirection);
                              patchForm(req.id, {
                                category: v,
                                directionId: dir ? String(dir.id) : "",
                                departmentId: "",
                                unitId: "",
                                personId: "",
                              });
                            } else {
                              patchForm(req.id, { category: v });
                            }
                          }}
                        >
                          <SelectTrigger className="mt-1.5 h-11">
                            <SelectValue placeholder="Choisir" />
                          </SelectTrigger>
                          <SelectContent>
                            {categories.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                      <div>
                        <Label>Priorité</Label>
                        <Select
                          value={form.priority}
                          onValueChange={(v) => patchForm(req.id, { priority: v as Priority })}
                        >
                          <SelectTrigger className="mt-1.5 h-11"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {PRIORITIES.map((p) => <SelectItem key={p} value={p}>{priorityLabels[p]}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Suggestion routage + hiérarchie d'assignation */}
                    {canUseAssignForm && (
                      <>
                        {form.category && suggestion && (
                          <div className="flex items-start gap-3 rounded-xl border border-info/25 bg-info/8 px-3 py-2.5 text-sm">
                            <Zap className="mt-0.5 h-4 w-4 shrink-0 text-info" />
                            <p>
                              <span className="font-semibold text-info">Routage suggéré :</span>
                              {" "}{suggestion.targetDirection} → {suggestion.targetService}{" "}
                              <button
                                className="ml-1 font-medium text-info underline underline-offset-2 hover:no-underline"
                                onClick={() => {
                                  const dir = realDirections.find((d) => d.name === suggestion.targetDirection);
                                  patchForm(req.id, {
                                    directionId: dir ? String(dir.id) : "",
                                    departmentId: "",
                                    unitId: "",
                                    personId: "",
                                  });
                                }}
                              >
                                Appliquer
                              </button>
                            </p>
                          </div>
                        )}
                        {form.category && !suggestion && routingRulesData.length > 0 && (
                          <div className="flex items-start gap-3 rounded-xl border border-warning/25 bg-warning/8 px-3 py-2.5 text-sm">
                            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-warning-foreground dark:text-warning" />
                            <p className="text-warning-foreground dark:text-warning">
                              <span className="font-semibold">Aucune règle de routage</span> ne correspond à cette catégorie — sélectionnez manuellement la direction cible.
                            </p>
                          </div>
                        )}

                        {/* Hiérarchie d'assignation — Direction → Département → Service → Personne */}
                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <Label>Direction cible <span className="text-destructive">*</span></Label>
                            <Select
                              value={form.directionId}
                              onValueChange={(v) => patchForm(req.id, {
                                directionId: v,
                                departmentId: "",
                                unitId: "",
                                personId: "",
                              })}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder="Sélectionner" />
                              </SelectTrigger>
                              <SelectContent>
                                {realDirections.map((d) => (
                                  <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {realDirections.length === 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">Aucune direction active disponible.</p>
                            )}
                          </div>
                          <div>
                            <Label>Département cible <span className="text-destructive">*</span></Label>
                            <Select
                              value={form.departmentId}
                              onValueChange={(v) => patchForm(req.id, {
                                departmentId: v,
                                unitId: "",
                                personId: "",
                              })}
                              disabled={!form.directionId}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder={
                                  !form.directionId ? "Choisir d'abord une direction" : "Sélectionner"
                                } />
                              </SelectTrigger>
                              <SelectContent>
                                {departments.map((dep) => (
                                  <SelectItem key={dep.id} value={String(dep.id)}>{dep.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {form.directionId && departments.length === 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                Aucun département actif disponible pour cette direction.
                              </p>
                            )}
                          </div>
                          <div>
                            <Label>Service cible <span className="text-destructive">*</span></Label>
                            <Select
                              value={form.unitId}
                              onValueChange={(v) => patchForm(req.id, { unitId: v, personId: "" })}
                              disabled={!form.departmentId}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder={
                                  !form.departmentId ? "Choisir d'abord un département" : "Sélectionner"
                                } />
                              </SelectTrigger>
                              <SelectContent>
                                {services.map((s) => (
                                  <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {form.departmentId && services.length === 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">Aucun service actif disponible.</p>
                            )}
                          </div>
                          <div>
                            <Label>Personne cible <span className="text-destructive">*</span></Label>
                            <Select
                              value={form.personId}
                              onValueChange={(v) => patchForm(req.id, { personId: v })}
                              disabled={!form.unitId}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder={
                                  !form.unitId ? "Choisir d'abord un service" : "Sélectionner"
                                } />
                              </SelectTrigger>
                              <SelectContent>
                                {people.map((p) => (
                                  <SelectItem key={p.id} value={String(p.id)}>
                                    {p.name}{p.role ? ` · ${p.role}` : ""}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {form.unitId && people.length === 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                Aucun employé autorisé à traiter dans ce service.
                              </p>
                            )}
                          </div>
                        </div>
                      </>
                    )}

                    {/* Actions */}
                    <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="rounded-full"
                        onClick={() => setExpanded(null)}
                      >
                        Fermer
                      </Button>
                      <div className="flex flex-wrap items-center gap-2">
                        {canTakeRole && (
                          <Button
                            size="sm"
                            variant="outline"
                            className="rounded-full border-success/40 text-success hover:bg-success/10"
                            disabled={!canTake || !takeData || isTaking}
                            onClick={() => takeData && takeMut.mutate({ id: req.id, data: takeData })}
                          >
                            {isTaking
                              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                              : <UserPlus className="mr-1.5 h-3.5 w-3.5" />}
                            Prendre le ticket
                          </Button>
                        )}

                        {/* Assigner — nécessite les 4 niveaux : direction, département, service, personne. */}
                        {canUseAssignForm && (
                          <Button
                            size="sm"
                            className={cn(
                              "rounded-full px-5",
                              canAssign
                                ? "gradient-primary text-background shadow-md shadow-primary/30"
                                : "bg-muted text-muted-foreground",
                            )}
                            disabled={!canAssign || isPending}
                            onClick={() => qualifyMut.mutate({ id: req.id, form })}
                          >
                            {isPending
                              ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Assignation…</>
                              : <><CheckCircle2 className="mr-1.5 h-4 w-4" /> Assigner</>
                            }
                          </Button>
                        )}
                      </div>
                    </div>
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
