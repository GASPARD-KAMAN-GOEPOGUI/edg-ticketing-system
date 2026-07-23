import { createFileRoute, Link } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { useState, useCallback, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { fetchQueue, fetchTriage, assignRequest, qualifyTriage } from "@/lib/api/requests";
import { fetchUsers } from "@/lib/api/accounts";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { fetchRoutingRules, fetchRefTable, fetchRequestCategories } from "@/lib/api/admin-config";
import { priorityLabels } from "@/lib/mock-data";
import type { Priority } from "@/lib/mock-data";
import { toast } from "sonner";
import {
  ArrowUpRight, CheckCircle2, ChevronDown, ChevronUp, Clock, Filter, Inbox,
  Loader2, MessageSquare, RotateCcw, Search, SlidersHorizontal, User, UserPlus, Zap,
} from "lucide-react";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { format, formatDistanceToNow } from "date-fns";
import { fr } from "date-fns/locale";
import { PaginationBar } from "@/components/pagination-bar";
import { AsyncSwap } from "@/components/async-states";
import {
  EscalationProgressBar,
  buildRequesterStepsFromStatus,
  DEFAULT_LEVELS,
} from "@/components/escalation-progress-bar";
import { useUser, useRole } from "@/lib/session";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";

type Tab = "queue" | "qualify";

type TriageForm = {
  category: string;
  priority: Priority;
  directionId: string;
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

export const Route = createFileRoute("/app/queue")({
  beforeLoad: () => requireRole("agent", "chief", "admin"),
  validateSearch: (search: Record<string, unknown>): { tab?: Tab } => ({
    ...(search.tab === "qualify" && { tab: "qualify" as const }),
  }),
  head: () => ({ meta: [{ title: "File d'attente — EDG Support" }] }),
  component: QueuePage,
});

const priorityDotClass: Record<Priority, string> = {
  low: "text-muted-foreground",
  medium: "text-info",
  high: "text-warning-foreground dark:text-warning",
  critical: "text-destructive",
};

// ── Composant racine avec onglets ─────────────────────────────────────────────

function QueuePage() {
  const { tab = "queue" } = Route.useSearch();
  const navigate = Route.useNavigate();
  const setTab = (t: Tab) => navigate({ search: (prev) => ({ ...prev, tab: t }), replace: true });

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex w-fit items-center gap-1 rounded-full border border-border/50 bg-muted/30 p-0.5">
        <button
          onClick={() => setTab("queue")}
          className={
            "flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition " +
            (tab === "queue"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground")
          }
        >
          <Inbox className="h-4 w-4" />
          À prendre
        </button>
        <button
          onClick={() => setTab("qualify")}
          className={
            "flex items-center gap-1.5 rounded-full px-4 py-2 text-sm font-medium transition " +
            (tab === "qualify"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground")
          }
        >
          <SlidersHorizontal className="h-4 w-4" />
          À qualifier
        </button>
      </div>
      {tab === "queue" ? <QueueTab /> : <QualifyTab />}
    </div>
  );
}

// ── Onglet File d'attente ─────────────────────────────────────────────────────

function QueueTab() {
  const sessionUser = useUser();
  const [role] = useRole();
  const queryClient = useQueryClient();

  // ── Filtres ────────────────────────────────────────────────────────────────
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [filterPriority, setFilterPriority] = useState("all");
  const [filterDirection, setFilterDirection] = useState("all");
  const [layout, setLayout] = useState<LayoutMode>("grid");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(t);
  }, [search]);
  useEffect(() => { setPage(1); }, [filterPriority, filterDirection, debouncedSearch]);
  useEffect(() => {
    if (role === "chief" && sessionUser?.direction_id && filterDirection === "all") {
      setFilterDirection(sessionUser.direction_id);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [role, sessionUser?.direction_id]);

  const PRIORITY_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

  const filters = {
    page,
    limit: pageSize,
    unassigned_only: true,
    ...(filterDirection !== "all" && { direction_id: filterDirection }),
    ...(filterPriority !== "all" && { priority: filterPriority }),
    ...(debouncedSearch && { search: debouncedSearch }),
  };

  // ── Données ────────────────────────────────────────────────────────────────
  const { data, isLoading, isError } = useQuery({
    queryKey: ["queue", filters],
    queryFn: () => fetchQueue(filters),
    staleTime: 30_000,
  });

  // ── Dialog : Assigner — états déclarés avant les queries qui les utilisent ──
  const [assignOpen, setAssignOpen] = useState(false);
  const [assignTarget, setAssignTarget] = useState<string>("");
  const [assignDirectionId, setAssignDirectionId] = useState("");
  const [assignAgentId, setAssignAgentId] = useState("");

  const { data: directionsForAssign = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const directionMap = new Map(directionsForAssign.map((d) => [String(d.id), d.name]));

  const { data: directionAgentsData } = useQuery({
    queryKey: ["agents-by-direction", assignDirectionId],
    queryFn: () => fetchUsers({ role: "agent", direction_id: assignDirectionId, limit: 100 }),
    enabled: !!assignDirectionId,
    staleTime: 60_000,
  });

  const allItems = data?.items ?? [];
  const paged = [...allItems].sort(
    (a, b) => (PRIORITY_ORDER[a.priority] ?? 9) - (PRIORITY_ORDER[b.priority] ?? 9),
  );

  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  const listState: "loading" | "empty" | "ready" = isLoading
    ? "loading"
    : isError || paged.length === 0
    ? "empty"
    : "ready";

  // ── Sélection ──────────────────────────────────────────────────────────────
  const [selected, setSelected] = useState<string[]>([]);
  const toggleSelect = useCallback((id: string) =>
    setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]),
  []);
  const toggleAll = () =>
    setSelected(selected.length === paged.length ? [] : paged.map((r) => r.id));

  const assignMut = useMutation({
    mutationFn: async () => {
      const ids = assignTarget ? [assignTarget] : selected;
      await Promise.all(ids.map((id) => assignRequest(id, assignAgentId, sessionUser?.id)));
    },
    onSuccess: () => {
      toast.success(`${assignTarget ? 1 : selected.length} demande(s) assignée(s)`);
      setAssignOpen(false);
      setAssignTarget("");
      setAssignDirectionId("");
      setAssignAgentId("");
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["my-tickets"] });
      queryClient.invalidateQueries({ queryKey: ["my-tickets-stats"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: () => toast.error("Erreur lors de l'assignation"),
  });

  const openAssign = (singleId?: string) => {
    setAssignTarget(singleId ?? "");
    setAssignDirectionId("");
    setAssignAgentId("");
    setAssignOpen(true);
  };

  // ── Dialog : Escalader ─────────────────────────────────────────────────────
  const [escalateOpen, setEscalateOpen] = useState(false);
  const [escalateLevel, setEscalateLevel] = useState<string>(DEFAULT_LEVELS[3]);
  const [escalateReason, setEscalateReason] = useState("");

  const escalateMut = useMutation({
    mutationFn: async () => {
      await Promise.all(
        selected.map((id) =>
          apiFetch(`/requests/${id}/escalate${sessionUser?.id ? `?actor_id=${sessionUser.id}` : ""}`, {
            method: "POST",
            body: JSON.stringify({
              level: escalateLevel,
              reason: escalateReason || "Escalade manuelle",
              from_agent_name: sessionUser?.name ?? "",
            }),
          }),
        ),
      );
    },
    onSuccess: () => {
      toast.success(`${selected.length} demande(s) escaladée(s) vers ${escalateLevel}`);
      setEscalateOpen(false);
      setEscalateReason("");
      setSelected([]);
      queryClient.invalidateQueries({ queryKey: ["queue"] });
      queryClient.invalidateQueries({ queryKey: ["requests"] });
      queryClient.invalidateQueries({ queryKey: ["escalations"] });
      queryClient.invalidateQueries({ queryKey: ["stats"] });
    },
    onError: () => toast.error("Erreur lors de l'escalade"),
  });

  const escalationPreview = [
    { level: "Qualification", status: "done" as const },
    { level: "Chef de service", status: "active" as const },
    { level: escalateLevel, status: "pending" as const },
  ];

  return (
    <>
      {/* En-tête */}
      <motion.header
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="flex flex-wrap items-end justify-between gap-3"
      >
        <div>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">File d'attente</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {total} demande{total !== 1 ? "s" : ""} actives — triées par priorité.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
          {selected.length > 0 && (
            <>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => openAssign()}
              >
                <UserPlus className="mr-1.5 h-4 w-4" />
                Assigner ({selected.length})
              </Button>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => setEscalateOpen(true)}
              >
                <ArrowUpRight className="mr-1.5 h-4 w-4" />
                Escalader ({selected.length})
              </Button>
            </>
          )}
        </div>
      </motion.header>

      {/* Filtres */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, delay: 0.05 }}
      >
        <GlassCard className="p-4">
          <div className="grid gap-3 sm:grid-cols-[1fr_auto_auto_auto]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher par numéro, titre, demandeur…"
                className="h-11 pl-9"
              />
            </div>
            <Select value={filterPriority} onValueChange={setFilterPriority}>
              <SelectTrigger className="h-11 w-full sm:w-36">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes priorités</SelectItem>
                {(["critical", "high", "medium", "low"] as Priority[]).map((p) => (
                  <SelectItem key={p} value={p}>{priorityLabels[p]}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterDirection} onValueChange={setFilterDirection}>
              <SelectTrigger className="h-11 w-full sm:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes directions</SelectItem>
                {directionsForAssign.map((d) => (
                  <SelectItem key={d.id} value={String(d.id)}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </GlassCard>
      </motion.div>

      {/* Liste / Grille */}
      <AsyncSwap
        state={listState}
        empty={
          <GlassCard className="py-16 text-center">
            <motion.div
              className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted"
              initial={{ scale: 0.6, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: "spring", stiffness: 260, damping: 18 }}
            >
              <Inbox className="h-6 w-6 text-muted-foreground" />
            </motion.div>
            <h3 className="font-semibold">File vide</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              {isError
                ? "Impossible de charger la file d'attente."
                : "Aucune demande active ne correspond aux filtres."}
            </p>
          </GlassCard>
        }
      >
        <>
          {layout === "list" ? (
            /* ── Vue liste ─────────────────────────────────────────────── */
            <GlassCard className="overflow-hidden p-0">
              {/* Header sélection tout */}
              <div className="flex items-center gap-3 border-b border-border/40 px-5 py-3">
                <Checkbox
                  checked={selected.length === paged.length && paged.length > 0}
                  onCheckedChange={toggleAll}
                />
                <span className="text-xs text-muted-foreground">
                  {selected.length > 0
                    ? `${selected.length} sélectionné${selected.length > 1 ? "s" : ""}`
                    : "Tout sélectionner"}
                </span>
                <Filter className="ml-auto h-3.5 w-3.5 text-muted-foreground" />
              </div>

              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => {
                  const slaOver = r.slaElapsed > r.slaHours;
                  return (
                    <motion.div
                      key={r.id}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -6 }}
                      transition={{ duration: 0.3, delay: i * 0.03 }}
                      className={
                        "flex items-start gap-4 border-b px-5 py-4 last:border-0 transition-colors hover:bg-background/50 " +
                        (r.priority === "critical"
                          ? "border-destructive/30 bg-destructive/3"
                          : r.status === "reopened"
                          ? "border-amber-500/30 bg-amber-500/3"
                          : "border-border/30")
                      }
                    >
                      <Checkbox
                        checked={selected.includes(r.id)}
                        onCheckedChange={() => toggleSelect(r.id)}
                        className="mt-1 shrink-0"
                      />
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to="/app/queue/tickets/$id"
                            params={{ id: r.id }}
                            className="font-mono text-[11px] text-primary hover:underline"
                          >
                            {r.ref}
                          </Link>
                          <PriorityBadge priority={r.priority} />
                          <StatusBadge status={r.status} />
                          {r.status === "reopened" && (
                            <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                              <RotateCcw className="h-2.5 w-2.5" /> Réouvert
                            </span>
                          )}
                          {r.priority === "critical" && (
                            <span className="inline-flex items-center rounded-full bg-destructive/15 px-2 py-0.5 text-[10px] font-bold text-destructive">
                              CRITIQUE
                            </span>
                          )}
                        </div>
                        <Link
                          to="/app/queue/tickets/$id"
                          params={{ id: r.id }}
                          className="block font-semibold leading-snug hover:text-primary"
                        >
                          {r.title}
                        </Link>
                        <p className="line-clamp-1 text-xs text-muted-foreground">{r.description}</p>
                        <div className="text-xs text-muted-foreground">
                          {directionMap.get(String(r.directionId)) ?? "Non orientée"} · {r.requesterName}
                        </div>
                      </div>
                      <div className="flex shrink-0 flex-col items-end gap-2">
                        <div className={`flex items-center gap-1 text-xs font-medium ${slaOver ? "text-destructive" : "text-muted-foreground"}`}>
                          <Clock className="h-3.5 w-3.5" />
                          {slaOver
                            ? "SLA dépassé"
                            : `${Math.max(0, r.slaHours - r.slaElapsed)}h restantes`}
                        </div>
                        <div className="text-[11px] text-muted-foreground">
                          {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                        </div>
                        <div className="flex gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            className="h-7 rounded-full px-3 text-xs"
                            onClick={() => openAssign(r.id)}
                          >
                            <UserPlus className="mr-1 h-3 w-3" />
                            Assigner
                          </Button>
                          <Button
                            asChild
                            size="sm"
                            className="h-7 rounded-full px-3 text-xs gradient-primary"
                          >
                            <Link to="/app/queue/tickets/$id" params={{ id: r.id }}>
                              Traiter
                            </Link>
                          </Button>
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </GlassCard>
          ) : (
            /* ── Vue grille ────────────────────────────────────────────── */
            <motion.div layout className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <AnimatePresence mode="popLayout" initial={false}>
                {paged.map((r, i) => {
                  const slaOver = r.slaElapsed > r.slaHours;
                  const steps = buildRequesterStepsFromStatus(r.status);
                  return (
                    <motion.div
                      key={r.id}
                      layout
                      initial={{ opacity: 0, scale: 0.96 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.94 }}
                      transition={{ duration: 0.3, delay: i * 0.04 }}
                      whileHover={{ y: -3 }}
                    >
                      <GlassCard className={
                        "flex flex-col gap-3 p-4 transition-shadow hover:shadow-xl " +
                        (r.priority === "critical" ? "border-destructive/40 bg-destructive/3" :
                         r.status === "reopened"   ? "border-amber-500/40 bg-amber-500/3" : "")
                      }>
                        {/* Header */}
                        <div className="flex items-start justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <Checkbox
                              checked={selected.includes(r.id)}
                              onCheckedChange={() => toggleSelect(r.id)}
                            />
                            <StatusBadge status={r.status} />
                            {r.status === "reopened" && (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold text-amber-600 dark:text-amber-400">
                                <RotateCcw className="h-2.5 w-2.5" />
                              </span>
                            )}
                            {r.priority === "critical" && (
                              <span className="rounded-full bg-destructive/15 px-1.5 py-0.5 text-[10px] font-bold text-destructive">!</span>
                            )}
                          </div>
                          <div className={`flex items-center gap-1 text-xs font-medium ${slaOver ? "text-destructive" : "text-muted-foreground"}`}>
                            <Clock className="h-3 w-3" />
                            {slaOver ? "SLA !" : `${Math.max(0, r.slaHours - r.slaElapsed)}h`}
                          </div>
                        </div>

                        {/* Title + priority */}
                        <Link to="/app/queue/tickets/$id" params={{ id: r.id }} className="hover:text-primary">
                          <p className="line-clamp-2 font-semibold leading-snug">{r.title}</p>
                        </Link>
                        <div className={`flex items-center gap-1.5 text-xs font-medium ${priorityDotClass[r.priority]}`}>
                          <span className="h-2 w-2 shrink-0 rounded-full bg-current" />
                          {priorityLabels[r.priority]}
                        </div>
                        {r.description && (
                          <p className="line-clamp-2 text-xs text-muted-foreground">{r.description}</p>
                        )}

                        {/* Meta */}
                        <div className="flex-1" />
                        <div className="space-y-1">
                          <div className="text-xs text-muted-foreground">
                            {directionMap.get(String(r.directionId)) ?? "Non orientée"} · {r.requesterName}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {format(new Date(r.createdAt), "d MMM yyyy", { locale: fr })}
                          </div>
                          <p className="font-mono text-[11px] text-muted-foreground/60">Réf. {r.ref}</p>
                        </div>

                        {/* Progress */}
                        <div className="border-t border-border/30 pt-2">
                          <EscalationProgressBar
                            compact
                            steps={steps}
                            className="!border-0 !shadow-none !bg-transparent !backdrop-blur-none !rounded-none !px-0 !py-0"
                          />
                        </div>

                        {/* Actions */}
                        <div className="flex gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            className="flex-1 rounded-full text-xs"
                            onClick={() => openAssign(r.id)}
                          >
                            <UserPlus className="mr-1 h-3 w-3" />
                            Assigner
                          </Button>
                          <Button asChild size="sm" className="flex-1 rounded-full text-xs gradient-primary">
                            <Link to="/app/queue/tickets/$id" params={{ id: r.id }}>Traiter</Link>
                          </Button>
                        </div>
                      </GlassCard>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </motion.div>
          )}

          <PaginationBar
            page={page}
            totalPages={totalPages}
            total={total}
            pageSize={pageSize}
            onChange={setPage}
            onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
          />
        </>
      </AsyncSwap>

      {/* Dialog : Assigner */}
      <Dialog open={assignOpen} onOpenChange={(open) => {
        if (!open) { setAssignDirectionId(""); setAssignAgentId(""); }
        setAssignOpen(open);
      }}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Assigner {assignTarget ? "la demande" : `${selected.length} demande(s)`}</DialogTitle>
            <DialogDescription>
              Sélectionnez la direction puis l'agent responsable.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-1">
            {/* Champ 1 — Direction */}
            <div className="space-y-1.5">
              <Label>Direction <span className="text-destructive">*</span></Label>
              <Select
                value={assignDirectionId}
                onValueChange={(v) => { setAssignDirectionId(v); setAssignAgentId(""); }}
              >
                <SelectTrigger className="h-11">
                  <SelectValue placeholder="Sélectionner une direction" />
                </SelectTrigger>
                <SelectContent>
                  {directionsForAssign.filter((d) => d.status).map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>
                      {d.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Champ 2 — Agent (filtré par direction) */}
            <div className="space-y-1.5">
              <Label>Agent <span className="text-destructive">*</span></Label>
              <Select
                value={assignAgentId}
                onValueChange={setAssignAgentId}
                disabled={!assignDirectionId}
              >
                <SelectTrigger className="h-11">
                  <SelectValue placeholder={
                    !assignDirectionId
                      ? "Choisir d'abord une direction"
                      : (directionAgentsData?.items ?? []).length === 0
                        ? "Aucun agent dans cette direction"
                        : "Sélectionner un agent"
                  } />
                </SelectTrigger>
                <SelectContent>
                  {(directionAgentsData?.items ?? []).map((a) => (
                    <SelectItem key={a.id} value={a.id}>
                      <span className="font-medium">{a.name}</span>
                      {a.job && <span className="ml-1 text-muted-foreground">— {a.job}</span>}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={() => setAssignOpen(false)}>
              Annuler
            </Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={!assignDirectionId || !assignAgentId || assignMut.isPending}
              onClick={() => assignMut.mutate()}
            >
              {assignMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Confirmer l'assignation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Dialog : Escalader */}
      <Dialog open={escalateOpen} onOpenChange={setEscalateOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Escalader {selected.length} demande(s)</DialogTitle>
            <DialogDescription>
              Choisissez le niveau hiérarchique cible et la raison.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label>Niveau cible</Label>
              <Select value={escalateLevel} onValueChange={setEscalateLevel}>
                <SelectTrigger className="mt-1.5 h-11">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DEFAULT_LEVELS.slice(3, 6).map((l) => (
                    <SelectItem key={l} value={l}>{l}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Raison</Label>
              <Textarea
                className="mt-1.5 resize-none"
                rows={3}
                placeholder="Décrivez la raison de l'escalade…"
                value={escalateReason}
                onChange={(e) => setEscalateReason(e.target.value)}
              />
            </div>
            <EscalationProgressBar compact steps={escalationPreview} />
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={() => setEscalateOpen(false)}>
              Annuler
            </Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={escalateMut.isPending}
              onClick={() => escalateMut.mutate()}
            >
              {escalateMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Confirmer l'escalade
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ── Onglet : À qualifier ──────────────────────────────────────────────────────

function QualifyTab() {
  const sessionUser = useUser();
  const queryClient = useQueryClient();

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
      unitId: req?.serviceId ?? "",
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
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 5 * 60_000,
  });

  const expandedDirectionId = expanded
    ? (forms[expanded]?.directionId ?? queue.find((r) => r.id === expanded)?.directionId ?? "")
    : "";
  const { data: expandedUnits = [] } = useQuery({
    queryKey: ["units", expandedDirectionId],
    queryFn: () => fetchUnits(expandedDirectionId),
    enabled: !!expandedDirectionId,
    staleTime: 5 * 60_000,
  });

  // Personnes disponibles dans la direction sélectionnée (tous rôles sauf user)
  const { data: directionPeopleData } = useQuery({
    queryKey: ["people-by-direction", expandedDirectionId],
    queryFn: () => fetchUsers({ direction_id: expandedDirectionId, limit: 100 }),
    enabled: !!expandedDirectionId,
    staleTime: 5 * 60_000,
  });
  const directionPeople = (directionPeopleData?.items ?? []).filter(
    (u) => u.role !== "user",
  );

  const qualifyMut = useMutation({
    mutationFn: ({ id, form }: { id: string; form: TriageForm }) =>
      qualifyTriage(
        id,
        {
          category: form.category,
          priority: form.priority,
          direction_id: form.directionId,
          unit_id: form.unitId || undefined,
          assignee_id: form.personId && form.personId !== "none" ? form.personId : undefined,
        },
        sessionUser?.id,
      ),
    onSuccess: (_, { id }) => {
      const req = queue.find((r) => r.id === id);
      toast.success(`Demande ${req?.ref ?? ""} orientée avec succès.`);
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
      toast.success(`Demande ${req?.ref ?? ""} prise en charge.`);
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
          {!isLoading && (
            <p className="text-sm text-muted-foreground">
              {queue.length} demande{queue.length !== 1 ? "s" : ""} en attente de qualification.
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 rounded-2xl border border-warning/30 bg-warning/10 px-4 py-2 text-sm font-medium text-warning-foreground dark:text-warning">
          <Zap className="h-4 w-4 shrink-0" />
          Aucune demande ne doit rester non orientée plus de 2h.
        </div>
      </header>

      <AsyncSwap
        state={listState}
        empty={
          isError ? (
            <GlassCard className="py-16 text-center">
              <p className="text-sm text-muted-foreground">Impossible de charger les demandes.</p>
            </GlassCard>
          ) : (
            <GlassCard className="py-16 text-center">
              <CheckCircle2 className="mx-auto h-10 w-10 text-success" />
              <h3 className="mt-3 font-semibold">File de qualification vide</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Toutes les demandes ont été qualifiées et orientées.
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
            const services = isOpen ? expandedUnits : [];
            const isPending = qualifyMut.isPending && qualifyMut.variables?.id === req.id;
            const takeDirectionId = form.directionId || req.directionId || sessionUser?.direction_id || undefined;
            const takeUnitId = form.unitId || sessionUser?.unit_id || req.serviceId || undefined;
            const takeCategory = form.category || req.category || "";
            const status = normalizeQueueStatus(req.status);
            const canTake = QUALIFIABLE_STATUSES.has(status) && !TERMINAL_STATUSES.has(status);
            const takeData = canTake && sessionUser?.id && takeCategory && (takeDirectionId || takeUnitId)
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
                  <PriorityBadge priority={req.priority} />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{req.ref}</span>
                      <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent-foreground dark:text-accent">
                        Non orientée
                      </span>
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
                    {/* Fiche employé */}
                    <div className="flex items-center gap-3 rounded-2xl border border-border/40 bg-card/50 p-4">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
                        <User className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <div className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          Demandeur
                        </div>
                        <div className="font-medium">{req.requesterName || "—"}</div>
                        <div className="text-xs text-muted-foreground">Collaborateur EDG</div>
                      </div>
                    </div>

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
                              patchForm(req.id, { category: v, directionId: dir ? String(dir.id) : "", unitId: "" });
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

                    {/* Suggestion routage */}
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
                              patchForm(req.id, { directionId: dir ? String(dir.id) : "", unitId: "" });
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

                    {/* Direction & service cible */}
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div>
                        <Label>Direction cible <span className="text-destructive">*</span></Label>
                        <Select
                          value={form.directionId}
                          onValueChange={(v) => patchForm(req.id, { directionId: v, unitId: "", personId: "" })}
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
                      </div>
                      <div>
                        <Label>Service <span className="text-xs text-muted-foreground">(optionnel)</span></Label>
                        <Select
                          value={form.unitId}
                          onValueChange={(v) => patchForm(req.id, { unitId: v })}
                          disabled={!form.directionId}
                        >
                          <SelectTrigger className="mt-1.5 h-11">
                            <SelectValue placeholder="Sélectionner" />
                          </SelectTrigger>
                          <SelectContent>
                            {services.map((s) => (
                              <SelectItem key={s.id} value={String(s.id)}>{s.name}</SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {/* Personne cible (optionnel) */}
                    <div>
                      <Label>
                        Personne cible{" "}
                        <span className="text-xs text-muted-foreground">(optionnel — chef, directeur, agent…)</span>
                      </Label>
                      <Select
                        value={form.personId}
                        onValueChange={(v) => patchForm(req.id, { personId: v })}
                        disabled={!form.directionId}
                      >
                        <SelectTrigger className="mt-1.5 h-11">
                          <SelectValue placeholder={
                            !form.directionId
                              ? "Choisir d'abord une direction"
                              : directionPeople.length === 0
                              ? "Aucune personne trouvée"
                              : "Assigner directement à une personne"
                          } />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="none">— Aucune (laisser la direction gérer)</SelectItem>
                          {directionPeople.map((p) => (
                            <SelectItem key={p.id} value={String(p.id)}>
                              {p.name}{p.role ? ` · ${p.role}` : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

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
                      <div className="flex flex-wrap gap-2">
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
                          Prendre la demande
                        </Button>

                        {/* Valider l'orientation */}
                        <Button
                          size="sm"
                          className={cn(
                            "rounded-full px-5",
                            form.directionId
                              ? "gradient-primary text-background shadow-md shadow-primary/30"
                              : "bg-muted text-muted-foreground",
                          )}
                          disabled={!form.directionId || isPending}
                          onClick={() => qualifyMut.mutate({ id: req.id, form })}
                        >
                          {isPending
                            ? <><Loader2 className="mr-1.5 h-4 w-4 animate-spin" /> Validation…</>
                            : <><CheckCircle2 className="mr-1.5 h-4 w-4" /> Valider l'orientation</>
                          }
                        </Button>
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
