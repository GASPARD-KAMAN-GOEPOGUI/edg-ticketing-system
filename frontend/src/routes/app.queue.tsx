import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { prefetch } from "@/lib/prefetch";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
import { fetchRequestCategories } from "@/lib/api/admin-config";
import { priorityLabels } from "@/lib/mock-data";
import type { Priority, Role } from "@/lib/mock-data";
import { toast } from "sonner";
import {
  CheckCircle2, ChevronDown, ChevronUp, History,
  Loader2, User, UserPlus, Zap,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { AsyncSwap } from "@/components/async-states";
import { StatusBadge } from "@/components/status-badge";
import { useUser } from "@/lib/session";
import { cn } from "@/lib/utils";

/** Seule la DSI traite les incidents : l'organisation traitante (direction,
 *  département, service) n'est plus saisie ici — le backend la déduit du
 *  rattachement du chef de service qui qualifie, déjà renseigné au back-office.
 *  Le CSSHF ne choisit donc que la catégorie, la priorité et le chef de
 *  division support de SON service à qui orienter le ticket. */
type TriageForm = {
  /** Vide à l'ouverture : la qualification est un point de contrôle, le chef de
   *  service doit choisir activement. Pré-remplir depuis le ticket permettait de
   *  valider sans avoir rien examiné. */
  category: string;
  /** Vide à l'ouverture, même raison que `category` — d'où `| ""` plutôt que
   *  `Priority` seul. */
  priority: Priority | "";
  personId: string;
  /** Procédure EDG/PS-GSI/Pro-02 tâche 1.3 — point de contrôle « descriptif de
   *  la solution proposée ». Obligatoire dans les deux cas : orientation vers un
   *  chef de division support comme prise en charge personnelle. */
  proposedSolution: string;
};

const QUALIFIABLE_STATUSES = new Set(["new", "qualifying", "qualified", "reopened"]);
const TERMINAL_STATUSES = new Set(["cancelled", "closed", "resolved", "rejected"]);
const STATUS_ALIASES: Record<string, string> = {
  cancalled: "cancelled",
  canceled: "cancelled",
  escaladed: "escalated",
};

/** Libellé d'un chef de division support dans la liste d'imputation :
 *  « nom complet.badge ». Un service peut compter plusieurs chefs de division,
 *  et le nom seul ne suffit pas toujours à les distinguer — d'où le badge.
 *
 *  « Badge » est le libellé métier de `account.matricule` (la colonne n'est pas
 *  renommée : la table `account` est partagée avec la plateforme centrale et le
 *  matricule sert d'identifiant de connexion). Sans badge renseigné, on affiche
 *  le nom complet seul, sans point orphelin — même repli que le PV d'intervention. */
export function queueTargetLabel(person: { name: string; firstname?: string; matricule?: string }) {
  const fullName = [person.firstname, person.name].filter(Boolean).join(" ").trim() || person.name;
  const badge = person.matricule?.trim();
  return badge ? `${fullName}.${badge}` : fullName;
}

function normalizeQueueStatus(status?: string) {
  const clean = (status || "new").trim().toLowerCase();
  return STATUS_ALIASES[clean] ?? clean;
}

const PRIORITIES: Priority[] = ["low", "medium", "high", "critical"];
// Cibles possibles pour le routage d'un ticket depuis la file d'attente ("Personne
// cible") — reste large (tous les roles traitants), distinct de qui peut ACCEDER a
// cette page (PAGE_ACCESS_ROLES, restreint au Module 2).
const OPERATIONAL_ROLES: Role[] = ["chief-service", "technicien", "chef-division-support", "admin"];
// File d'attente — reservee au chef de service (CSSHF) et a l'admin (Module 2).
const PAGE_ACCESS_ROLES: Role[] = ["chief-service", "admin"];

export const Route = createFileRoute("/app/queue")({
  beforeLoad: () => requireRole(...PAGE_ACCESS_ROLES),
  head: () => ({ meta: [{ title: "File d'attente — EDG Support" }] }),
  // Précharge les données (pas seulement le chunk JS) au survol du lien —
  // même queryKey que le useQuery du composant, donc pas de double fetch.
  loader: ({ context: { queryClient } }) =>
    prefetch(queryClient.ensureQueryData({
      queryKey: ["qualify"],
      queryFn: () => fetchTriage({ limit: 50 }),
      staleTime: 20_000,
    })),
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
  const isOperationalRole = Boolean(sessionUser?.role && PAGE_ACCESS_ROLES.includes(sessionUser.role));
  const canUseAssignForm = isOperationalRole;
  const canTakeRole = isOperationalRole;

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
    return forms[id] ?? {
      category: "",
      priority: "",
      personId: "",
      proposedSolution: "",
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

  // Les règles de routage, la liste des directions et les cascades
  // Direction → Département → Service ont été retirées de cet écran : la cible
  // n'est plus choisie, elle EST le service du chef de service qui qualifie
  // (déduit côté serveur dans ServiceRequest.qualify_triage).

  // Module 2 — depuis la File d'attente, le chef de service n'a que deux issues :
  // prendre le ticket pour lui-même, ou l'envoyer à un chef de division support
  // (CDS) de SON service. Ni technicien, ni chef-departement, ni director, ni un
  // autre chef de service ne sont proposés ici. La chaîne de transmission
  // dynamique (A → An) qui suit n'est pas concernée : elle reste libre.
  const actorUnitId = sessionUser?.unit_id ? String(sessionUser.unit_id) : "";
  const { data: unitPeopleData } = useQuery({
    queryKey: ["queue-targets", actorUnitId],
    queryFn: async () => {
      // fetchUsers({role}) élargit au groupe via l'alias RBAC backend — on
      // refiltre donc strictement sur chef-division-support côté client.
      const res = await fetchUsers({ role: "chef-division-support", unit_id: actorUnitId, limit: 100 });
      return res.items.filter(
        (person) => person.role === "chef-division-support" && String(person.unit_id ?? "") === actorUnitId,
      );
    },
    enabled: !!actorUnitId,
    staleTime: 5 * 60_000,
  });
  // BR-REQUESTER-NO-SELF-TREATMENT-001 — le demandeur du ticket en cours de
  // qualification ne doit jamais être sélectionnable comme "Personne cible".
  const expandedRequesterId = expanded
    ? String(queue.find((q) => q.id === expanded)?.requesterId ?? "")
    : "";
  const unitPeople = (unitPeopleData ?? []).filter(
    (person) => !expandedRequesterId || String(person.id) !== expandedRequesterId,
  );

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
          // Ni direction_id ni unit_id : l'organisation traitante est celle du
          // chef de service qui qualifie, déduite côté serveur.
          assignee_id: form.personId || undefined,
          proposed_solution: form.proposedSolution.trim() || undefined,
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
      // BR-QUEUE-AUTO-START-001 : "Assigner" démarre aussi le traitement
      // immédiatement (comme "Prendre le ticket" ci-dessous) — même invalidation.
      queryClient.invalidateQueries({ queryKey: ["my-tickets-stats"] });
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
        assignee_id: string;
        proposed_solution?: string;
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
      <header>
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">File d'attente</h1>
        {!isLoading && (
          <p className="mt-1 text-sm text-muted-foreground">
            {queue.length} ticket{queue.length !== 1 ? "s" : ""} en attente de qualification.
          </p>
        )}
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
            const people = isOpen ? unitPeople : [];
            // Procédure tâche 1.3 — la qualification est un point de contrôle
            // bloquant : rien ne part de la file d'attente sans catégorie,
            // priorité et solution proposée explicitement saisies. Aucun repli
            // sur une valeur par défaut, qui laisserait passer un ticket que
            // personne n'a réellement qualifié.
            const qualified = Boolean(
              form.category && form.priority && form.proposedSolution.trim(),
            );
            // Orienter exige en plus le chef de division support destinataire.
            const canAssign = qualified && Boolean(form.personId);
            const isPending = qualifyMut.isPending && qualifyMut.variables?.id === req.id;
            const status = normalizeQueueStatus(req.status);
            const canTake =
              canTakeRole
              && qualified
              && QUALIFIABLE_STATUSES.has(status)
              && !TERMINAL_STATUSES.has(status);
            const takeData = canTake && sessionUser?.id
              ? {
                  category: form.category,
                  priority: form.priority,
                  assignee_id: sessionUser.id,
                  proposed_solution: form.proposedSolution.trim(),
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
                        <Label>Catégorie <span className="text-destructive">*</span></Label>
                        <Select
                          value={form.category}
                          onValueChange={(v) => patchForm(req.id, { category: v })}
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
                        <Label>Priorité <span className="text-destructive">*</span></Label>
                        <Select
                          value={form.priority}
                          onValueChange={(v) => patchForm(req.id, { priority: v as Priority })}
                        >
                          <SelectTrigger className="mt-1.5 h-11">
                            <SelectValue placeholder="Choisir" />
                          </SelectTrigger>
                          <SelectContent>
                            {PRIORITIES.map((p) => <SelectItem key={p} value={p}>{priorityLabels[p]}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Orientation — le destinataire seul reste à choisir */}
                    {canUseAssignForm && (
                      <>
                        <div className="flex items-start gap-3 rounded-xl border border-info/25 bg-info/8 px-3 py-2.5 text-sm">
                          <Zap className="mt-0.5 h-4 w-4 shrink-0 text-info" />
                          <p>
                            <span className="font-semibold text-info">Traitement :</span>{" "}
                            le ticket est rattaché à votre direction, votre département et
                            votre service. Choisissez simplement le chef de division support
                            à qui l'orienter, ou prenez-le pour votre propre traitement.
                          </p>
                        </div>

                        {/* Procédure tâche 1.3 — point de contrôle de l'imputation */}
                        <div>
                          <Label htmlFor={`proposed-solution-${req.id}`}>
                            Solution proposée <span className="text-destructive">*</span>
                          </Label>
                          <Textarea
                            id={`proposed-solution-${req.id}`}
                            value={form.proposedSolution}
                            onChange={(e) => patchForm(req.id, { proposedSolution: e.target.value })}
                            placeholder="Décrivez la piste de résolution envisagée pour ce ticket…"
                            className="mt-1.5 min-h-24"
                          />
                          <p className="mt-1 text-xs text-muted-foreground">
                            Lue par le chef de division support puis par le technicien.
                            Jamais visible du demandeur. Obligatoire pour prendre comme
                            pour orienter le ticket.
                          </p>
                        </div>

                        <div className="grid gap-4 sm:grid-cols-2">
                          <div>
                            <Label>Chef de division support <span className="text-destructive">*</span></Label>
                            <Select
                              value={form.personId}
                              onValueChange={(v) => patchForm(req.id, { personId: v })}
                            >
                              <SelectTrigger className="mt-1.5 h-11">
                                <SelectValue placeholder="Sélectionner" />
                              </SelectTrigger>
                              <SelectContent>
                                {people.map((p) => (
                                  <SelectItem key={p.id} value={String(p.id)}>
                                    {queueTargetLabel(p)}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            {people.length === 0 && (
                              <p className="mt-1 text-xs text-muted-foreground">
                                Aucun chef de division support dans votre service — prenez le ticket
                                pour votre propre traitement.
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
