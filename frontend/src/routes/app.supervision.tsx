import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectSeparator,
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
import { Skeleton } from "@/components/ui/skeleton";
import { priorityLabels, statusLabels } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import type { Direction, Unit } from "@/lib/api/directions-units";
import type { EscalationItem, RequestItem } from "@/lib/mock-data";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import { useMemo, useState, useEffect, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { usePagination, PaginationBar } from "@/components/pagination-bar";
import { useUser, useRole } from "@/lib/session";
import {
  fetchEscalations,
  reviewEscalation,
  resolveEscalation,
  escalateRequest as escalateToDirector,
} from "@/lib/api/escalations";
import { downloadReport } from "@/lib/api/reports";
import {
  fetchRequests,
  assignRequest,
  updateRequest,
} from "@/lib/api/requests";
import { fetchUsers } from "@/lib/api/accounts";
import type { AccountUser } from "@/lib/api/accounts";
import {
  AlertTriangle,
  ArrowUpRight,
  Clock,
  Search,
  ShieldAlert,
  Users2,
  Activity,
  Filter,
  ChevronRight,
  Loader2,
  RotateCcw,
  UserPlus,
  ArrowRight,
  Download,
  Megaphone,
  Send,
  Building2,
  CheckCircle2,
  CircleDot,
  ClipboardList,
  Eye,
  Flag,
  Gauge,
  GitBranch,
  Layers,
  ListFilter,
  RefreshCw,
  Timer,
  UserCheck,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { toast } from "sonner";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { cn } from "@/lib/utils";
import { LayoutToggle } from "@/components/layout-toggle";
import type { LayoutMode } from "@/components/layout-toggle";

export const Route = createFileRoute("/app/supervision")({
  beforeLoad: () => requireRole("chief-service", "chief-departement", "director", "admin"),
  head: () => ({ meta: [{ title: "Supervision — EDG Support" }] }),
  component: SupervisionPage,
});

// ── Types ─────────────────────────────────────────────────────────────────────

type AgentStats = {
  id: string;
  name: string;
  directionId?: string;
  unitId?: string;
  availability?: string;
  open: number;
  inProgress: number;
  pending: number;
  slaBreached: number;
  critical: number;
};

// ── Constantes ────────────────────────────────────────────────────────────────

const ACTIVE_STATUSES = new Set([
  "new", "qualifying", "qualified", "assigned",
  "in_progress", "pending", "escalated", "reopened",
]);

const levelTone: Record<EscalationItem["level"], string> = {
  L1: "bg-info/15 text-info",
  L2: "bg-warning/20 text-warning-foreground dark:text-warning",
  L3: "bg-destructive/15 text-destructive",
};

const levelLabel: Record<EscalationItem["level"], string> = {
  L1: "Agent N1",
  L2: "Chef de service",
  L3: "Directeur",
};

type EscalationFilter = "active" | "all" | EscalationItem["status"];

// ── Composant principal ────────────────────────────────────────────────────────

function SupervisionPage() {
  const [role] = useRole();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const sessionUser = useUser();
  const isChiefRole = role === "chief-service" || role === "chief-departement";
  const isChiefService = role === "chief-service";
  const isChiefDepartment = role === "chief-departement";
  const unitId = isChiefRole ? sessionUser?.unit_id : undefined;
  const directionId = role === "director"
    ? (sessionUser?.direction_id ?? sessionUser?.unit_id)
    : sessionUser?.direction_id;
  const hasOperationalScope = isChiefRole ? !!unitId : !!directionId;
  const scopeLabel = isChiefDepartment ? "département" : "service";
  const scopeTitle = isChiefDepartment ? "Supervision du département" : "Supervision du service";

  // Deep-link "Mon équipe" (menu "Pilotage", chief-service) — ?section=equipe
  // fait défiler vers la section "Charge par agent" déjà existante.
  useEffect(() => {
    const section = new URLSearchParams(window.location.search).get("section");
    if (!section) return;
    document.getElementById(section)?.scrollIntoView({ behavior: "smooth", block: "start" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [teamMsg, setTeamMsg] = useState("");
  const teamMsgMut = useMutation({
    mutationFn: () => apiFetch("/announcements/team-message", {
      method: "POST",
      body: JSON.stringify({
        title: "Message d'équipe",
        description: teamMsg.trim(),
        announcement_category: "general",
        announcement_priority: "medium",
        announcement_status: "published",
        audience: "unit",
        author_id: sessionUser?.id ?? "",
        channel_names: ["in_app"],
        role_names: ["agent-support"],
        direction_ids: [],
      }),
    }),
    onSuccess: () => { toast.success("Message envoyé à votre équipe."); setTeamMsg(""); },
    onError: () => toast.error("Erreur lors de l'envoi du message."),
  });

  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<EscalationFilter>("active");
  const [agentLayout, setAgentLayout] = useState<LayoutMode>("grid");
  const [escLayout, setEscLayout] = useState<LayoutMode>("grid");

  // ── Dialogs ────────────────────────────────────────────────────────────────
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignEsc, setReassignEsc] = useState<EscalationItem | null>(null);
  const [reassignAgentId, setReassignAgentId] = useState("");
  const [reassignNote, setReassignNote] = useState("");

  const [transferOpen, setTransferOpen] = useState(false);
  const [transferEsc, setTransferEsc] = useState<EscalationItem | null>(null);
  const [transferReason, setTransferReason] = useState("");

  const canReassignEscalation = isChiefRole || role === "admin";
  const canTakeOverEscalation = role === "admin";
  const canTransferToDirector = isChiefRole || role === "admin";
  const openSupervisionTicket = useCallback((id: string) => {
    navigate({ to: "/app/supervision/tickets/$id", params: { id } });
  }, [navigate]);
  const openSupervisionTicketFromKeyboard = useCallback((event: React.KeyboardEvent, id?: string) => {
    if (!id) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openSupervisionTicket(id);
    }
  }, [openSupervisionTicket]);

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: dirsData = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 60_000,
  });

  const { data: escData, isLoading: loadEsc, isError: escError } = useQuery({
    queryKey: ["escalations"],
    queryFn: () => fetchEscalations({ limit: 100 }),
    staleTime: 30_000,
    // Pas de refetchInterval : escalation.* (SSE) invalide déjà ["escalations"].
  });
  const esc: EscalationItem[] = escData?.items ?? [];

  const { data: agentsData, isLoading: loadAgents, isError: agentsError } = useQuery({
    queryKey: ["agents-supervision", role, unitId, directionId],
    queryFn: () => {
      if (isChiefService) {
        return fetchUsers({ role: "agent-support", unit_id: unitId, limit: 100 });
      }
      if (isChiefDepartment) {
        return fetchUsers({ role: "agent-support", direction_id: unitId, limit: 100 });
      }
      return fetchUsers({ role: "agent-support", direction_id: directionId, limit: 100 });
    },
    enabled: hasOperationalScope,
    staleTime: 60_000,
    // Pas de refetchInterval : user.* (SSE) invalide désormais ["agents-supervision"].
  });
  const agents: AccountUser[] = agentsData?.items ?? [];

  const { data: chiefsData, isLoading: loadChiefs, isError: chiefsError } = useQuery({
    queryKey: ["chiefs-supervision", directionId],
    queryFn: () => fetchUsers({ role: "chief-service", direction_id: directionId, limit: 100 }),
    enabled: role === "director" && !!directionId,
    staleTime: 60_000,
    // Pas de refetchInterval : user.* (SSE) invalide désormais ["chiefs-supervision"].
  });
  const chiefs: AccountUser[] = chiefsData?.items ?? [];

  const { data: unitsData = [], isLoading: loadUnits, isError: unitsError } = useQuery({
    queryKey: ["units-supervision"],
    // Pas de filtre direction : les agents affichés (chef-service/département/director)
    // peuvent appartenir à des unités hors du seul périmètre `directionId` du rôle
    // director — nécessaire pour résoudre le nom de l'unité de chaque agent ci-dessous.
    queryFn: () => fetchUnits(),
    staleTime: 5 * 60_000,
  });

  const { data: ticketsData, isLoading: loadTickets, isError: ticketsError } = useQuery({
    queryKey: ["tickets-supervision", role, unitId, directionId],
    queryFn: () => {
      if (isChiefService) {
        return fetchRequests({ unit_id: unitId, limit: 500 });
      }
      if (isChiefDepartment) {
        return fetchRequests({ direction_id: unitId, limit: 500 });
      }
      return fetchRequests({ direction_id: directionId, limit: 500 });
    },
    enabled: hasOperationalScope,
    staleTime: 30_000,
    // Pas de refetchInterval : request.* (SSE) invalide désormais ["tickets-supervision"].
  });
  const allTickets = ticketsData?.items ?? [];

  const loadingStats = loadAgents || loadTickets;

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["escalations"] });
    qc.invalidateQueries({ queryKey: ["tickets-supervision"] });
    qc.invalidateQueries({ queryKey: ["requests"] });
    qc.invalidateQueries({ queryKey: ["queue"] });
    qc.invalidateQueries({ queryKey: ["my-tickets"] });
    qc.invalidateQueries({ queryKey: ["my-tickets-stats"] });
    qc.invalidateQueries({ queryKey: ["stats"] });
    qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
  };

  // ── Stats par agent ────────────────────────────────────────────────────────
  const agentStats: AgentStats[] = useMemo(() => {
    return agents.map((agent) => {
      const myTickets = allTickets.filter((t) => t.assigneeId === agent.id);
      const openTickets = myTickets.filter((t) => ACTIVE_STATUSES.has(t.status));
      return {
        id: agent.id,
        // Nom complet (prénom + nom) — agent.name seul ne porte que le nom de
        // famille, insuffisant pour distinguer des agents partageant un patronyme.
        name: [agent.firstname, agent.name].filter(Boolean).join(" "),
        directionId: agent.direction_id,
        unitId: agent.unit_id,
        availability: agent.availability,
        open: openTickets.length,
        inProgress: openTickets.filter((t) => t.status === "in_progress").length,
        pending: openTickets.filter((t) => t.status === "pending").length,
        slaBreached: openTickets.filter((t) => t.slaElapsed > t.slaHours).length,
        critical: openTickets.filter((t) => t.priority === "critical").length,
      };
    });
  }, [agents, allTickets]);

  const filteredAgents = useMemo(
    () => agentStats.filter((a) =>
      `${a.name} ${a.directionId ?? ""} ${a.unitId ?? ""}`.toLowerCase().includes(q.toLowerCase()),
    ),
    [agentStats, q],
  );

  const { page: agPage, setPage: setAgPage, totalPages: agTotalPages, paged: pagedAgents, total: agTotal, pageSize: agPageSize, setPageSize: setAgPageSize } = usePagination(filteredAgents, 10);
  useEffect(() => { setAgPage(1); }, [q]);

  // ── KPIs (données réelles) ─────────────────────────────────────────────────
  const kpis = useMemo(() => {
    const escalationsOpen = esc.filter((e) => e.status !== "resolved").length;
    const totalOpen = agentStats.reduce((s, a) => s + a.open, 0);
    const slaBreachedTotal = agentStats.reduce((s, a) => s + a.slaBreached, 0);
    const overloadCount = agentStats.filter((a) => a.open >= 8).length;
    return { escalationsOpen, totalOpen, slaBreachedTotal, overloadCount };
  }, [esc, agentStats]);

  // ── Escalades triées par urgence SLA (C12) ─────────────────────────────────
  const visibleEsc = useMemo(() => {
    const filtered = esc.filter((e) => {
      if (filter === "active") return e.status !== "resolved";
      if (filter === "all") return true;
      return e.status === filter;
    });
    return [...filtered].sort((a, b) => b.slaOverHours - a.slaOverHours);
  }, [esc, filter]);

  // ── Chart (données réelles) ────────────────────────────────────────────────
  const chartData = agentStats.map((a) => ({
    name: a.name.split(" ")[0],
    ouverts: a.open,
    retards: a.slaBreached,
  }));

  // ── Mutations escalades (C6) ───────────────────────────────────────────────
  const reviewMut = useMutation({
    mutationFn: (id: string) => reviewEscalation(id),
    onSuccess: () => { toast.success("Escalade prise en revue"); invalidate(); },
    onError: () => toast.error("Impossible de prendre en revue"),
  });

  const resolveMut = useMutation({
    mutationFn: (id: string) => resolveEscalation(id),
    onSuccess: () => { toast.success("Escalade clôturée"); invalidate(); },
    onError: () => toast.error("Impossible de clôturer l'escalade"),
  });

  const reassignMut = useMutation({
    mutationFn: async () => {
      if (!reassignEsc?.requestId) throw new Error("requestId manquant");
      await assignRequest(reassignEsc.requestId, reassignAgentId);
      await resolveEscalation(reassignEsc.id);
    },
    onSuccess: () => {
      toast.success("Ticket réaffecté — escalade clôturée");
      setReassignOpen(false);
      setReassignEsc(null);
      setReassignAgentId("");
      setReassignNote("");
      invalidate();
    },
    onError: () => toast.error("Erreur lors de la réaffectation"),
  });

  const returnToAgentMut = useMutation({
    mutationFn: async (e: EscalationItem) => {
      if (!e.requestId) throw new Error("requestId manquant");
      await updateRequest(e.requestId, { request_status: "in_progress" });
      await resolveEscalation(e.id);
    },
    onSuccess: () => { toast.success("Retourné à l'agent — ticket en traitement"); invalidate(); },
    onError: () => toast.error("Erreur lors du retour"),
  });

  const takeOverMut = useMutation({
    mutationFn: async (e: EscalationItem) => {
      if (!e.requestId) throw new Error("requestId manquant");
      if (sessionUser?.id) await assignRequest(e.requestId, sessionUser.id);
      await updateRequest(e.requestId, { request_status: "in_progress" });
      await resolveEscalation(e.id);
    },
    onSuccess: () => { toast.success("Ticket pris en charge directement — en cours"); invalidate(); },
    onError: () => toast.error("Erreur lors de la prise en charge"),
  });

  const transferMut = useMutation({
    mutationFn: async () => {
      if (!transferEsc?.requestId) throw new Error("requestId manquant");
      await escalateToDirector(transferEsc.requestId, {
        level: "L3",
        reason: transferReason.trim() || "Escalade vers le Directeur",
        from_agent_name: sessionUser?.name ?? "Chef de service",
        to_agent_name: "Directeur",
      });
      await resolveEscalation(transferEsc.id);
    },
    onSuccess: () => {
      toast.success("Escalade transmise au Directeur");
      setTransferOpen(false);
      setTransferEsc(null);
      setTransferReason("");
      invalidate();
    },
    onError: () => toast.error("Erreur lors du transfert"),
  });

  if (role === "director") {
    if (!directionId) {
      return (
        <div className="mx-auto max-w-2xl py-16 text-center">
          <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-warning/15">
            <AlertTriangle className="h-7 w-7 text-warning" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight">Aucune direction assignée</h1>
          <p className="mx-auto mt-3 max-w-sm text-sm text-muted-foreground">
            Votre compte directeur doit être rattaché à une direction avant d'accéder au centre de supervision.
          </p>
        </div>
      );
    }

    return (
      <DirectorSupervisionCenter
        directionId={directionId}
        tickets={allTickets}
        agents={agents}
        chiefs={chiefs}
        units={unitsData}
        directions={dirsData}
        escalations={esc}
        loading={loadTickets || loadAgents || loadChiefs || loadUnits || loadEsc}
        error={ticketsError || agentsError || chiefsError || unitsError || escError}
        onRefresh={invalidate}
      />
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* ── En-tête ── */}
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <ShieldAlert className="h-3 w-3" /> Pilotage opérationnel
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            {scopeTitle}
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Charge, délai agent par agent et escalades en cours — mis à jour en continu.
          </p>
        </div>
        <Button
          variant="outline"
          className="rounded-full"
          onClick={async () => {
            try {
              await downloadReport("by-agent", "excel");
              toast.success("Export agents téléchargé.");
            } catch {
              toast.error("Erreur lors de l'export — vérifiez que le backend est démarré.");
            }
          }}
        >
          <Download className="mr-1 h-4 w-4" /> Exporter agents
        </Button>
      </header>

      {/* ── Message d'équipe (chef uniquement) ── */}
      {isChiefService && (
        <GlassCard className="p-4">
          <div className="mb-2 flex items-center gap-2">
            <Megaphone className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Message d'équipe</span>
            <span className="text-xs text-muted-foreground">— visible uniquement par les agents de votre service</span>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Textarea
              value={teamMsg}
              onChange={(e) => setTeamMsg(e.target.value)}
              placeholder="Ex. : Réunion de service lundi à 9h, tickets urgents uniquement ce matin…"
              rows={2}
              className="flex-1 resize-none text-sm"
            />
            <Button
              className="gradient-primary shrink-0 self-end rounded-full sm:self-end"
              disabled={!teamMsg.trim() || teamMsgMut.isPending}
              onClick={() => teamMsgMut.mutate()}
            >
              {teamMsgMut.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              <span className="ml-1.5 sm:hidden">Envoyer</span>
            </Button>
          </div>
        </GlassCard>
      )}

      {/* ── KPI (données réelles) ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Kpi label="Escalades ouvertes"  value={kpis.escalationsOpen}  tone="destructive" icon={AlertTriangle} hint={`${esc.length} au total`}               loading={loadEsc} />
        <Kpi label="Tickets en charge"  value={kpis.totalOpen}        tone="primary"     icon={Activity}     hint={`${agentStats.length} agents actifs`}     loading={loadingStats} />
        <Kpi label="Agents surchargés"   value={kpis.overloadCount}    tone="warning"     icon={Users2}       hint="≥ 8 tickets ouverts"                       loading={loadingStats} />
      </div>

      {/* ── Sections operationnelles masquees a la demande metier ── */}
      <div className="hidden">
        <GlassCard className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Charge & retards par agent</h3>
              <p className="text-xs text-muted-foreground">Tickets ouverts vs délais dépassés</p>
            </div>
          </div>
          {loadingStats ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              Aucun agent dans le {scopeLabel}
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="name" tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <YAxis tick={{ fontSize: 11 }} stroke="var(--muted-foreground)" />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="ouverts" name="Ouverts"       fill="var(--chart-1)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <GlassCard>
          <h3 className="font-semibold">Distribution des escalades</h3>
          <p className="mb-4 text-xs text-muted-foreground">Niveaux actuellement actifs</p>
          <div className="space-y-3">
            {(["L1", "L2", "L3"] as const).map((lvl) => {
              const list = esc.filter((e) => e.level === lvl);
              const pct = (list.length / Math.max(esc.length, 1)) * 100;
              return (
                <div key={lvl}>
                  <div className="flex items-center justify-between text-xs">
                    <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", levelTone[lvl])}>{levelLabel[lvl]}</span>
                    <span className="text-muted-foreground">{list.length} escalades</span>
                  </div>
                  <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full gradient-primary" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </GlassCard>
      </div>

      {/* ── Escalades en cours (C1 : lien ticket, C6 : actions, C12 : tri SLA) ── */}
      <GlassCard className="hidden">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Escalades en cours</h3>
            <p className="text-xs text-muted-foreground">
              {visibleEsc.length} résultat(s) — triées par urgence délai décroissante
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Select value={filter} onValueChange={(v) => setFilter(v as EscalationFilter)}>
              <SelectTrigger className="h-9 w-full rounded-full sm:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="active">En cours</SelectItem>
                <SelectItem value="all">Tous statuts</SelectItem>
                <SelectItem value="open">Ouvertes</SelectItem>
                <SelectItem value="in_review">En revue</SelectItem>
                <SelectItem value="resolved">Clôturées</SelectItem>
              </SelectContent>
            </Select>
            <LayoutToggle layout={escLayout} onChange={setEscLayout} />
          </div>
        </div>

        {loadEsc ? (
          <div className="flex h-24 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground/40" />
          </div>
        ) : visibleEsc.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">Aucune escalade.</p>
        ) : escLayout === "list" ? (
          <ul className="space-y-2">
            {visibleEsc.map((e) => (
              <li
                key={e.id}
                className="flex flex-wrap items-start gap-3 rounded-2xl border border-border/40 bg-card/40 p-3 transition hover:border-primary/40"
              >
                <span className={cn("mt-0.5 rounded-full px-2.5 py-1 text-[10px] font-bold tracking-wider", levelTone[e.level])}>
                  {levelLabel[e.level] ?? e.level}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {/* C1 — lien vers le ticket */}
                    {e.requestId ? (
                      <Link
                        to="/app/supervision/tickets/$id"
                        params={{ id: e.requestId }}
                        className="font-mono text-[11px] text-primary hover:underline"
                      >
                        {e.requestRef}
                      </Link>
                    ) : (
                      <span className="font-mono text-[11px] text-muted-foreground">{e.requestRef}</span>
                    )}
                    <Badge variant="outline" className="text-[10px]">
                      {priorityLabels[e.priority]}
                    </Badge>
                    {e.status === "resolved" && (
                      <Badge className="bg-success/15 text-success">Clôturée</Badge>
                    )}
                    {e.status === "in_review" && (
                      <Badge className="bg-warning/20 text-warning-foreground dark:text-warning">En revue</Badge>
                    )}
                  </div>
                  <div className="mt-0.5 text-sm font-medium">{e.title}</div>
                  <div className="mt-0.5 text-xs text-muted-foreground">
                    {e.fromAgent} → <span className="font-medium text-foreground/80">{e.toAgent}</span>
                    {" · "}{e.reason}
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <div className="text-right">
                    <div className="text-xs text-muted-foreground">Délai dépassé</div>
                    <div className="text-sm font-semibold text-destructive">+{e.slaOverHours}h</div>
                  </div>
                  {e.status !== "resolved" && (
                    <div className="flex flex-wrap gap-1.5">
                      {e.status === "open" && (
                        <Button
                          size="sm" variant="outline"
                          className="h-7 rounded-full px-2.5 text-xs"
                          disabled={reviewMut.isPending}
                          onClick={() => reviewMut.mutate(e.id)}
                        >
                          En revue
                        </Button>
                      )}
                      {/* C6 — Réaffecter */}
                      {canReassignEscalation && e.requestId && (
                        <Button
                          size="sm" variant="outline"
                          className="h-7 rounded-full px-2.5 text-xs"
                          onClick={() => { setReassignEsc(e); setReassignAgentId(""); setReassignNote(""); setReassignOpen(true); }}
                        >
                          <UserPlus className="mr-1 h-3 w-3" /> Réaffecter
                        </Button>
                      )}
                      {/* C6 — Retourner à l'agent */}
                      {e.requestId && (
                        <Button
                          size="sm" variant="outline"
                          className="h-7 rounded-full px-2.5 text-xs"
                          disabled={returnToAgentMut.isPending}
                          onClick={() => returnToAgentMut.mutate(e)}
                        >
                          <RotateCcw className="mr-1 h-3 w-3" /> Retourner
                        </Button>
                      )}
                      {/* C6 — Traiter directement */}
                      {canTakeOverEscalation && e.requestId && (
                        <Button
                          size="sm" variant="outline"
                          className="h-7 rounded-full px-2.5 text-xs"
                          disabled={takeOverMut.isPending}
                          onClick={() => takeOverMut.mutate(e)}
                        >
                          <ArrowRight className="mr-1 h-3 w-3" /> Traiter
                        </Button>
                      )}
                      {/* C6 — Transférer au Directeur */}
                      {canTransferToDirector && e.requestId && (
                        <Button
                          size="sm"
                          className="h-7 rounded-full px-2.5 text-xs gradient-primary text-background"
                          onClick={() => { setTransferEsc(e); setTransferReason(""); setTransferOpen(true); }}
                        >
                          <ArrowUpRight className="mr-1 h-3 w-3" /> Directeur
                        </Button>
                      )}
                      <Button
                        size="sm"
                        className="h-7 rounded-full px-2.5 text-xs gradient-primary text-background"
                        disabled={resolveMut.isPending}
                        onClick={() => resolveMut.mutate(e.id)}
                      >
                        Clôturer
                      </Button>
                    </div>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {visibleEsc.map((e) => (
              <GlassCard
                key={e.id}
                className={cn(
                  "flex flex-col gap-2 p-4 transition hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40",
                  e.requestId && "cursor-pointer",
                )}
                role={e.requestId ? "link" : undefined}
                tabIndex={e.requestId ? 0 : undefined}
                onClick={() => { if (e.requestId) openSupervisionTicket(e.requestId); }}
                onKeyDown={(event) => openSupervisionTicketFromKeyboard(event, e.requestId)}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wider", levelTone[e.level])}>
                    {levelLabel[e.level] ?? e.level}
                  </span>
                  {e.requestId ? (
                    <Link
                      to="/app/supervision/tickets/$id"
                      params={{ id: e.requestId }}
                      className="font-mono text-[11px] text-primary hover:underline"
                    >
                      {e.requestRef}
                    </Link>
                  ) : (
                    <span className="font-mono text-[11px] text-muted-foreground">{e.requestRef}</span>
                  )}
                  <Badge variant="outline" className="text-[10px]">{priorityLabels[e.priority]}</Badge>
                </div>
                <div className="font-semibold text-sm mt-1 leading-snug">{e.title}</div>
                <div className="text-xs text-muted-foreground">{e.fromAgent} → {e.toAgent}</div>
                <div className="text-xs text-muted-foreground line-clamp-2">{e.reason}</div>
                <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-2">
                  <span className="text-xs font-semibold text-destructive">+{e.slaOverHours}h</span>
                  {e.status !== "resolved" && (
                    <div className="flex flex-wrap gap-1">
                      {e.status === "open" && (
                        <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                          disabled={reviewMut.isPending} onClick={(event) => { event.stopPropagation(); reviewMut.mutate(e.id); }}>
                          En revue
                        </Button>
                      )}
                      {e.requestId && (
                        <>
                          {canReassignEscalation && (
                            <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                              onClick={(event) => { event.stopPropagation(); setReassignEsc(e); setReassignAgentId(""); setReassignOpen(true); }}>
                              <UserPlus className="h-2.5 w-2.5" />
                            </Button>
                          )}
                          <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                            disabled={returnToAgentMut.isPending} onClick={(event) => { event.stopPropagation(); returnToAgentMut.mutate(e); }}>
                            <RotateCcw className="h-2.5 w-2.5" />
                          </Button>
                          {canTakeOverEscalation && (
                            <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                              disabled={takeOverMut.isPending} onClick={(event) => { event.stopPropagation(); takeOverMut.mutate(e); }}>
                              <ArrowRight className="h-2.5 w-2.5" />
                            </Button>
                          )}
                          {canTransferToDirector && (
                            <Button size="sm"
                              className="h-6 rounded-full px-2 text-[10px] gradient-primary text-background"
                              onClick={(event) => { event.stopPropagation(); setTransferEsc(e); setTransferReason(""); setTransferOpen(true); }}>
                              <ArrowUpRight className="h-2.5 w-2.5" />
                            </Button>
                          )}
                        </>
                      )}
                      <Button size="sm"
                        className="h-6 rounded-full px-2 text-[10px] gradient-primary text-background"
                        disabled={resolveMut.isPending} onClick={(event) => { event.stopPropagation(); resolveMut.mutate(e.id); }}>
                        Clôturer
                      </Button>
                    </div>
                  )}
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </GlassCard>

      {/* ── Charge par agent (C3 : suppression mock, données réelles) ── */}
      <GlassCard id="equipe" className="overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/40 p-5">
          <div>
            <h3 className="font-semibold">Charge par agent</h3>
            <p className="text-xs text-muted-foreground">
              {loadingStats
                ? "Chargement…"
                : `${agTotal} agent${agTotal !== 1 ? "s" : ""}`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative w-full max-w-xs">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Rechercher un agent…"
                className="h-10 rounded-full pl-9"
              />
            </div>
            <LayoutToggle layout={agentLayout} onChange={setAgentLayout} />
          </div>
        </div>

        {loadingStats ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
          </div>
        ) : agTotal === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {agents.length === 0
              ? `Aucun agent trouvé pour ce ${scopeLabel}.`
              : "Aucun résultat."}
          </p>
        ) : agentLayout === "list" ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-5 py-3 text-left font-semibold">Agent</th>
                  <th className="px-5 py-3 text-right font-semibold">Ouverts</th>
                  <th className="px-5 py-3 text-right font-semibold">En cours</th>
                  <th className="px-5 py-3 text-right font-semibold">En attente</th>
                  <th className="px-5 py-3 text-right font-semibold">Critiques</th>
                  <th className="px-5 py-3 text-right font-semibold">Disponibilité</th>
                </tr>
              </thead>
              <tbody>
                {pagedAgents.map((a) => (
                  <tr
                    key={a.id}
                    className="border-t border-border/40 transition hover:bg-card/40"
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="grid h-9 w-9 place-items-center rounded-full gradient-primary text-[11px] font-bold text-background">
                          {a.name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
                        </span>
                        <div>
                          <div className="font-medium">{a.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {dirsData.find((d) => String(d.id) === String(a.directionId))?.name
                              ?? unitsData.find((u) => String(u.id) === String(a.unitId))?.name
                              ?? "—"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right font-semibold">{a.open}</td>
                    <td className="px-5 py-3.5 text-right text-muted-foreground">{a.inProgress}</td>
                    <td className="px-5 py-3.5 text-right text-muted-foreground">{a.pending}</td>
                    <td className="px-5 py-3.5 text-right">
                      {a.critical > 0
                        ? <span className="font-semibold text-destructive">{a.critical}</span>
                        : <span className="text-muted-foreground">0</span>}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <AvailabilityBadge value={a.availability} open={a.open} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="grid gap-4 p-5 sm:grid-cols-2 lg:grid-cols-3">
            {pagedAgents.map((a) => (
              <GlassCard
                key={a.id}
                className={cn("flex flex-col gap-3 p-4", a.slaBreached > 0 && "border-destructive/30")}
              >
                <div className="flex items-center gap-3">
                  <span className="grid h-10 w-10 shrink-0 place-items-center rounded-full gradient-primary text-[11px] font-bold text-background">
                    {a.name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="font-semibold truncate">{a.name}</div>
                    <div className="text-xs text-muted-foreground truncate">
                      {dirsData.find((d) => String(d.id) === String(a.directionId))?.name
                              ?? unitsData.find((u) => String(u.id) === String(a.unitId))?.name
                              ?? "—"}
                    </div>
                  </div>
                  <AvailabilityBadge value={a.availability} open={a.open} />
                </div>
                <div className="grid grid-cols-2 gap-2 rounded-xl bg-muted/30 px-2 py-2 text-center">
                  <div>
                    <div className="text-sm font-bold">{a.open}</div>
                    <div className="text-[10px] text-muted-foreground">Ouverts</div>
                  </div>
                  <div>
                    <div className={cn("text-sm font-bold", a.critical > 0 && "text-destructive")}>{a.critical}</div>
                    <div className="text-[10px] text-muted-foreground">Critiques</div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-1 text-xs text-muted-foreground">
                  <span>En cours : <strong className="text-foreground">{a.inProgress}</strong></span>
                  <span>En attente : <strong className="text-foreground">{a.pending}</strong></span>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
        <PaginationBar
          page={agPage}
          totalPages={agTotalPages}
          total={agTotal}
          pageSize={agPageSize}
          onChange={setAgPage}
          onPageSizeChange={setAgPageSize}
        />
      </GlassCard>

      {/* ── Dialog : Réaffecter ── */}
      <Dialog open={canReassignEscalation && reassignOpen} onOpenChange={setReassignOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Réaffecter l'escalade</DialogTitle>
            <DialogDescription>
              Choisissez l'agent qui prendra en charge le ticket {reassignEsc?.requestRef}.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>Agent <span className="text-destructive">*</span></Label>
            <Select value={reassignAgentId} onValueChange={setReassignAgentId}>
              <SelectTrigger className="h-11">
                <SelectValue placeholder="Sélectionner un agent" />
              </SelectTrigger>
              <SelectContent>
                {agents.map((a) => (
                  <SelectItem key={a.id} value={a.id}>{a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Label>Note (optionnelle)</Label>
            <Textarea
              value={reassignNote}
              onChange={(e) => setReassignNote(e.target.value)}
              placeholder="Motif de la réaffectation…"
              className="resize-none"
              rows={2}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={() => setReassignOpen(false)}>
              Annuler
            </Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={!reassignAgentId || reassignMut.isPending}
              onClick={() => reassignMut.mutate()}
            >
              {reassignMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Confirmer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Dialog : Transférer au Directeur ── */}
      <Dialog open={canTransferToDirector && transferOpen} onOpenChange={setTransferOpen}>
        <DialogContent className="max-h-[90dvh] overflow-y-auto sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Transférer au Directeur</DialogTitle>
            <DialogDescription>
              Le ticket {transferEsc?.requestRef} sera escaladé au niveau Directeur (L3).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Label>Motif <span className="text-destructive">*</span></Label>
            <Textarea
              value={transferReason}
              onChange={(e) => setTransferReason(e.target.value)}
              placeholder="Justification du transfert au Directeur…"
              className="resize-none"
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button variant="ghost" className="rounded-full" onClick={() => setTransferOpen(false)}>
              Annuler
            </Button>
            <Button
              className="rounded-full gradient-primary"
              disabled={!transferReason.trim() || transferMut.isPending}
              onClick={() => transferMut.mutate()}
            >
              {transferMut.isPending && <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />}
              Confirmer le transfert
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

type DirectorSupervisionCenterProps = {
  directionId: string;
  tickets: RequestItem[];
  agents: AccountUser[];
  chiefs: AccountUser[];
  units: Unit[];
  directions: Direction[];
  escalations: EscalationItem[];
  loading: boolean;
  error: boolean;
  onRefresh: () => void;
};

type DirectorSortKey = "updated_desc" | "created_desc" | "sla_urgency" | "priority" | "status";

const ALL_FILTER = "__all__";
type DirectorQuickFilterKind =
  | "service"
  | "chief-service"
  | "agent-support"
  | "status"
  | "priority"
  | "category"
  | "escalation"
  | "sla"
  | "reopened"
  | "period";

function quickFilterValue(kind: DirectorQuickFilterKind, value: string) {
  return `${kind}:${value}`;
}

function parseQuickFilter(filter: string): { kind: "all" | DirectorQuickFilterKind; value: string } {
  if (filter === ALL_FILTER) return { kind: "all", value: "" };
  const index = filter.indexOf(":");
  if (index === -1) return { kind: "all", value: "" };
  return {
    kind: filter.slice(0, index) as DirectorQuickFilterKind,
    value: filter.slice(index + 1),
  };
}

const priorityWeight: Record<string, number> = {
  critical: 4,
  high: 3,
  medium: 2,
  low: 1,
};

function DirectorSupervisionCenter({
  directionId,
  tickets,
  agents,
  chiefs,
  units,
  directions,
  escalations,
  loading,
  error,
  onRefresh,
}: DirectorSupervisionCenterProps) {
  const [search, setSearch] = useState("");
  const [quickFilter, setQuickFilter] = useState(ALL_FILTER);
  const sortKey: DirectorSortKey = "updated_desc";

  const directionName = directions.find((d) => String(d.id) === String(directionId))?.name ?? "Direction";

  const unitMap = useMemo(
    () => new Map(units.map((u) => [String(u.id), u])),
    [units],
  );
  const agentMap = useMemo(
    () => new Map(agents.map((a) => [String(a.id), a])),
    [agents],
  );
  const chiefByUnit = useMemo(() => {
    const map = new Map<string, AccountUser>();
    chiefs.forEach((chief) => {
      if (chief.unit_id) map.set(String(chief.unit_id), chief);
    });
    return map;
  }, [chiefs]);

  const ticketIds = useMemo(() => new Set(tickets.map((t) => String(t.id))), [tickets]);
  const scopedEscalations = useMemo(
    () => escalations.filter((e) => e.requestId && ticketIds.has(String(e.requestId))),
    [escalations, ticketIds],
  );
  const activeEscalations = useMemo(
    () => scopedEscalations.filter((e) => !isEscalationClosed(e)),
    [scopedEscalations],
  );
  const latestEscalationByTicket = useMemo(() => {
    const map = new Map<string, EscalationItem>();
    [...scopedEscalations]
      .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
      .forEach((e) => {
        if (e.requestId && !map.has(String(e.requestId))) map.set(String(e.requestId), e);
      });
    return map;
  }, [scopedEscalations]);

  const serviceIds = useMemo(() => {
    const ids = new Set<string>();
    units.forEach((u) => ids.add(String(u.id)));
    tickets.forEach((t) => {
      if (t.serviceId) ids.add(String(t.serviceId));
    });
    return [...ids];
  }, [tickets, units]);

  const categoryOptions = useMemo(
    () => [...new Set(tickets.map((t) => t.category).filter(Boolean))].sort((a, b) => a.localeCompare(b)),
    [tickets],
  );
  const statusOptions = useMemo(
    () => [...new Set(tickets.map((t) => t.status))],
    [tickets],
  );

  const filteredTickets = useMemo(() => {
    const q = search.trim().toLowerCase();
    const scope = parseQuickFilter(quickFilter);
    const now = Date.now();
    const periodDays = scope.kind === "period"
      ? scope.value === "7d" ? 7 : scope.value === "30d" ? 30 : scope.value === "90d" ? 90 : null
      : null;

    const filtered = tickets.filter((ticket) => {
      const serviceId = ticket.serviceId ?? "";
      const chief = serviceId ? chiefByUnit.get(String(serviceId)) : undefined;
      const escalation = latestEscalationByTicket.get(String(ticket.id));
      const createdTime = new Date(ticket.createdAt).getTime();
      const isReopened = ticket.status === "reopened" || ticket.timeline?.some((event) => event.type === "reopened");

      if (scope.kind === "service" && String(serviceId) !== scope.value) return false;
      if (scope.kind === "chief-service" && String(chief?.id ?? "") !== scope.value) return false;
      if (scope.kind === "agent-support" && String(ticket.assigneeId ?? "") !== scope.value) return false;
      if (scope.kind === "status" && ticket.status !== scope.value) return false;
      if (scope.kind === "priority" && ticket.priority !== scope.value) return false;
      if (scope.kind === "category" && ticket.category !== scope.value) return false;
      if (scope.kind === "escalation" && scope.value === "none" && escalation) return false;
      if (scope.kind === "escalation" && scope.value !== "none" && escalation?.level !== scope.value) return false;
      if (scope.kind === "sla" && scope.value === "late" && !isTicketLate(ticket)) return false;
      if (scope.kind === "sla" && scope.value === "ok" && isTicketLate(ticket)) return false;
      if (scope.kind === "reopened" && scope.value === "yes" && !isReopened) return false;
      if (scope.kind === "reopened" && scope.value === "no" && isReopened) return false;
      if (periodDays && createdTime < now - periodDays * 24 * 60 * 60 * 1000) return false;

      if (!q) return true;
      const haystack = [
        ticket.ref,
        ticket.title,
        ticket.description,
        ticket.category,
        ticket.status,
        ticket.priority,
        getServiceName(serviceId, unitMap),
        directionName,
        chief?.name,
        ticket.assigneeName ?? agentMap.get(String(ticket.assigneeId ?? ""))?.name,
        ticket.requesterName,
        escalation?.level,
        escalation?.reason,
      ].filter(Boolean).join(" ").toLowerCase();
      return haystack.includes(q);
    });

    return [...filtered].sort((a, b) => sortTickets(a, b, sortKey));
  }, [
    agentMap,
    chiefByUnit,
    directionName,
    latestEscalationByTicket,
    quickFilter,
    search,
    tickets,
    unitMap,
  ]);

  const {
    page,
    setPage,
    totalPages,
    paged: pagedTickets,
    total: filteredTotal,
    pageSize,
    setPageSize,
  } = usePagination(filteredTickets, 15);

  useEffect(() => {
    setPage(1);
  }, [search, quickFilter, setPage]);

  const statusCount = useMemo(() => {
    const count: Record<string, number> = {};
    tickets.forEach((ticket) => {
      count[ticket.status] = (count[ticket.status] ?? 0) + 1;
    });
    return count;
  }, [tickets]);

  const serviceStats = useMemo(() => {
    return serviceIds.map((id) => {
      const serviceTickets = tickets.filter((t) => String(t.serviceId ?? "") === id);
      const opened = serviceTickets.filter((t) => ACTIVE_STATUSES.has(t.status)).length;
      const closed = serviceTickets.filter((t) => t.status === "closed").length;
      const resolved = serviceTickets.filter((t) => t.status === "resolved" || t.status === "closed").length;
      const late = serviceTickets.filter(isTicketLate).length;
      const critical = serviceTickets.filter((t) => t.priority === "critical").length;
      const serviceAgents = agents.filter((a) => String(a.unit_id ?? "") === id);
      const chief = chiefByUnit.get(id);
      const avg = averageResolutionHours(serviceTickets);
      return {
        id,
        name: getServiceName(id, unitMap),
        chief: chief?.name ?? "—",
        total: serviceTickets.length,
        opened,
        closed,
        late,
        critical,
        avg,
        resolutionRate: serviceTickets.length ? Math.round((resolved / serviceTickets.length) * 100) : 0,
        slaBreachRate: serviceTickets.length ? Math.round((late / serviceTickets.length) * 100) : 0,
        agents: serviceAgents.length,
        workload: serviceAgents.length ? Math.round((opened / serviceAgents.length) * 10) / 10 : opened,
      };
    }).sort((a, b) => b.opened - a.opened || b.total - a.total);
  }, [agents, chiefByUnit, serviceIds, tickets, unitMap]);

  const priorityDistribution = useMemo(
    () => distribution(tickets, (t) => priorityLabels[t.priority] ?? t.priority),
    [tickets],
  );
  const categoryDistribution = useMemo(
    () => distribution(tickets, (t) => t.category || "Non catégorisé"),
    [tickets],
  );
  const serviceDistribution = useMemo(
    () => serviceStats.slice(0, 8).map((s) => ({ label: s.name, value: s.total })),
    [serviceStats],
  );

  const avgResolution = averageResolutionHours(tickets);
  const lateTickets = tickets.filter(isTicketLate).length;
  const criticalTickets = tickets.filter((t) => t.priority === "critical").length;
  const reopenedTickets = tickets.filter((t) => t.status === "reopened").length;

  const workflowStages = [
    { label: "Création", value: tickets.length, icon: CircleDot },
    { label: "Qualification", value: (statusCount.qualifying ?? 0) + tickets.filter((t) => t.inTriage).length, icon: ListFilter },
    { label: "Affectation", value: statusCount.assigned ?? 0, icon: UserCheck },
    { label: "Traitement", value: statusCount.in_progress ?? 0, icon: Activity },
    { label: "Validation", value: statusCount.qualified ?? 0, icon: CheckCircle2 },
    { label: "Résolution", value: statusCount.resolved ?? 0, icon: ClipboardList },
    { label: "Fermeture", value: statusCount.closed ?? 0, icon: Flag },
  ];

  if (loading && tickets.length === 0) {
    return <DirectorSupervisionSkeleton />;
  }

  return (
    <div className="mx-auto max-w-[1540px] space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Building2 className="h-3.5 w-3.5" />
            {directionName}
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Centre de supervision de la direction
          </h1>
          <p className="mt-1 max-w-3xl text-sm text-muted-foreground">
            Vue consolidée des services rattachés, des charges, délais, escalades et tickets critiques. Les données restent limitées au périmètre de votre direction.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            className="rounded-full"
            onClick={() => {
              onRefresh();
              toast.success("Rafraîchissement demandé.");
            }}
          >
            <RefreshCw className="mr-1.5 h-4 w-4" />
            Actualiser
          </Button>
          <Button
            variant="outline"
            className="rounded-full"
            onClick={async () => {
              try {
                await downloadReport("by-agent", "excel");
                toast.success("Export supervision téléchargé.");
              } catch {
                toast.error("Erreur lors de l'export.");
              }
            }}
          >
            <Download className="mr-1.5 h-4 w-4" />
            Exporter
          </Button>
        </div>
      </header>

      {error && (
        <div className="flex items-start gap-3 rounded-2xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          Certaines données n'ont pas pu être chargées. Les permissions et le périmètre direction restent appliqués.
        </div>
      )}

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        <DirectorMetricCard label="Total tickets" value={tickets.length} icon={ClipboardList} tone="primary" loading={loading} />
        <DirectorMetricCard label="Nouveaux" value={statusCount.new ?? 0} icon={CircleDot} tone="primary" loading={loading} />
        <DirectorMetricCard label="À qualifier" value={(statusCount.qualifying ?? 0) + tickets.filter((t) => t.inTriage).length} icon={ListFilter} tone="warning" loading={loading} />
        <DirectorMetricCard label="Affectés" value={statusCount.assigned ?? 0} icon={UserCheck} tone="primary" loading={loading} />
        <DirectorMetricCard label="En cours" value={statusCount.in_progress ?? 0} icon={Activity} tone="primary" loading={loading} />
        <DirectorMetricCard label="En attente" value={statusCount.pending ?? 0} icon={Timer} tone="warning" loading={loading} />
        <DirectorMetricCard label="Validés" value={statusCount.qualified ?? 0} icon={CheckCircle2} tone="success" loading={loading} />
        <DirectorMetricCard label="Résolus" value={statusCount.resolved ?? 0} icon={ClipboardList} tone="success" loading={loading} />
        <DirectorMetricCard label="Fermés" value={statusCount.closed ?? 0} icon={Flag} tone="success" loading={loading} />
        <DirectorMetricCard label="Réouverts" value={reopenedTickets} icon={RefreshCw} tone="warning" loading={loading} />
        <DirectorMetricCard label="Escaladés" value={activeEscalations.length || (statusCount.escalated ?? 0)} icon={ArrowUpRight} tone="destructive" loading={loading} />
        <DirectorMetricCard label="En retard délai" value={lateTickets} icon={Clock} tone="destructive" loading={loading} />
        <DirectorMetricCard label="Critiques" value={criticalTickets} icon={AlertTriangle} tone="destructive" loading={loading} />
        <DirectorMetricCard label="Moy. résolution" value={avgResolution == null ? "—" : `${avgResolution}h`} icon={Gauge} tone="primary" loading={loading} />
        <DirectorMetricCard label="Services suivis" value={serviceStats.length} icon={Layers} tone="primary" loading={loading} />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <GlassCard className="p-5">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="font-semibold">États du workflow</h2>
              <p className="text-xs text-muted-foreground">Lecture directionnelle du cycle complet des tickets</p>
            </div>
            <Badge variant="outline" className="rounded-full">
              <GitBranch className="mr-1 h-3 w-3" />
              Traçabilité active
            </Badge>
          </div>
          <div className="grid gap-3 md:grid-cols-7">
            {workflowStages.map((stage, index) => (
              <div key={stage.label} className="relative rounded-2xl border border-border/40 bg-card/40 p-3">
                {index < workflowStages.length - 1 && (
                  <div className="absolute right-[-14px] top-1/2 hidden h-px w-7 bg-border md:block" />
                )}
                <div className="mb-3 flex items-center justify-between gap-2">
                  <span className="grid h-8 w-8 place-items-center rounded-xl bg-primary/10 text-primary">
                    <stage.icon className="h-4 w-4" />
                  </span>
                  <span className="text-xl font-bold">{stage.value}</span>
                </div>
                <p className="text-xs font-medium">{stage.label}</p>
              </div>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <h2 className="font-semibold">Répartition par priorité</h2>
          <p className="mb-4 text-xs text-muted-foreground">Tickets de la direction, toutes unités confondues</p>
          <DistributionBars data={priorityDistribution} total={tickets.length} emptyLabel="Aucune priorité à afficher." />
        </GlassCard>
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <GlassCard className="p-5">
          <h2 className="font-semibold">Répartition par service</h2>
          <p className="mb-4 text-xs text-muted-foreground">Volume par unité de la direction</p>
          <DistributionBars data={serviceDistribution} total={tickets.length} emptyLabel="Aucun service actif." />
        </GlassCard>
        <GlassCard className="p-5 xl:col-span-2">
          <h2 className="font-semibold">Répartition par catégorie</h2>
          <p className="mb-4 text-xs text-muted-foreground">Catégories réelles issues des tickets</p>
          <DistributionBars data={categoryDistribution.slice(0, 10)} total={tickets.length} emptyLabel="Aucune catégorie à afficher." />
        </GlassCard>
      </section>

      <GlassCard className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">Supervision des services</h2>
            <p className="text-xs text-muted-foreground">Charge, critiques et performance par service de la direction</p>
          </div>
          <Badge variant="outline" className="rounded-full">
            {serviceStats.length} service{serviceStats.length !== 1 ? "s" : ""}
          </Badge>
        </div>
        {serviceStats.length === 0 ? (
          <EmptyPanel title="Aucun service" text="Aucun service rattaché à cette direction n'a encore de données à superviser." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-sm">
              <thead className="text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="pb-3 text-left font-semibold">Service</th>
                  <th className="pb-3 text-left font-semibold">Chef</th>
                  <th className="pb-3 text-right font-semibold">Total</th>
                  <th className="pb-3 text-right font-semibold">Ouverts</th>
                  <th className="pb-3 text-right font-semibold">Fermés</th>
                  <th className="pb-3 text-right font-semibold">Critiques</th>
                  <th className="pb-3 text-right font-semibold">Moy. résol.</th>
                  <th className="pb-3 text-right font-semibold">Taux résol.</th>
                  <th className="pb-3 text-right font-semibold">Agents</th>
                  <th className="pb-3 text-right font-semibold">Charge</th>
                </tr>
              </thead>
              <tbody>
                {serviceStats.map((service) => (
                  <tr key={service.id} className="border-t border-border/40">
                    <td className="py-3 pr-4 font-medium">{service.name}</td>
                    <td className="py-3 pr-4 text-muted-foreground">{service.chief}</td>
                    <td className="py-3 text-right font-semibold">{service.total}</td>
                    <td className="py-3 text-right">{service.opened}</td>
                    <td className="py-3 text-right">{service.closed}</td>
                    <td className={cn("py-3 text-right font-semibold", service.critical > 0 ? "text-destructive" : "text-muted-foreground")}>{service.critical}</td>
                    <td className="py-3 text-right">{service.avg == null ? "—" : `${service.avg}h`}</td>
                    <td className="py-3 text-right">
                      <RateBadge value={service.resolutionRate} />
                    </td>
                    <td className="py-3 text-right">{service.agents}</td>
                    <td className="py-3 text-right">{service.workload}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      <GlassCard className="overflow-hidden p-0">
        <div className="space-y-4 border-b border-border/40 p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">Registre de supervision des tickets</h2>
              <p className="text-xs text-muted-foreground">
                {filteredTotal} résultat{filteredTotal !== 1 ? "s" : ""} sur {tickets.length} ticket{tickets.length !== 1 ? "s" : ""} de la direction
              </p>
            </div>
            <Badge variant="outline" className="rounded-full">
              <Eye className="mr-1 h-3 w-3" />
              Consultation directeur
            </Badge>
          </div>

          <div className="grid gap-2 lg:grid-cols-[minmax(0,1.5fr)_minmax(260px,0.8fr)]">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Recherche globale : numéro, objet, demandeur, agent..."
                className="h-10 rounded-full pl-9"
              />
            </div>
            <Select value={quickFilter} onValueChange={setQuickFilter}>
              <SelectTrigger className="h-10 rounded-full">
                <SelectValue placeholder="Filtre rapide" />
              </SelectTrigger>
              <SelectContent className="max-h-[420px]">
                <SelectItem value={ALL_FILTER}>Tout le périmètre</SelectItem>

                <SelectSeparator />
                <QuickFilterGroupLabel>Services</QuickFilterGroupLabel>
                {serviceIds.map((id) => (
                  <SelectItem key={id} value={quickFilterValue("service", id)}>
                    {getServiceName(id, unitMap)}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Chefs</QuickFilterGroupLabel>
                {chiefs.map((chief) => (
                  <SelectItem key={chief.id} value={quickFilterValue("chief-service", chief.id)}>
                    {chief.name}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Agents</QuickFilterGroupLabel>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={quickFilterValue("agent-support", agent.id)}>
                    {agent.name}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Statuts</QuickFilterGroupLabel>
                {statusOptions.map((status) => (
                  <SelectItem key={status} value={quickFilterValue("status", status)}>
                    {statusLabels[status] ?? status}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Priorités</QuickFilterGroupLabel>
                {Object.entries(priorityLabels).map(([key, label]) => (
                  <SelectItem key={key} value={quickFilterValue("priority", key)}>
                    {label}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Catégories</QuickFilterGroupLabel>
                {categoryOptions.map((category) => (
                  <SelectItem key={category} value={quickFilterValue("category", category)}>
                    {category}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Délai</QuickFilterGroupLabel>
                <SelectItem value={quickFilterValue("sla", "late")}>En retard</SelectItem>
                <SelectItem value={quickFilterValue("sla", "ok")}>Dans le délai</SelectItem>

                <SelectSeparator />
                <QuickFilterGroupLabel>Escalades</QuickFilterGroupLabel>
                <SelectItem value={quickFilterValue("escalation", "none")}>Sans escalade</SelectItem>
                {(["L1", "L2", "L3"] as const).map((level) => (
                  <SelectItem key={level} value={quickFilterValue("escalation", level)}>
                    {levelLabel[level]}
                  </SelectItem>
                ))}

                <SelectSeparator />
                <QuickFilterGroupLabel>Réouverture</QuickFilterGroupLabel>
                <SelectItem value={quickFilterValue("reopened", "yes")}>Réouverts</SelectItem>
                <SelectItem value={quickFilterValue("reopened", "no")}>Non réouverts</SelectItem>

                <SelectSeparator />
                <QuickFilterGroupLabel>Période</QuickFilterGroupLabel>
                <SelectItem value={quickFilterValue("period", "7d")}>7 derniers jours</SelectItem>
                <SelectItem value={quickFilterValue("period", "30d")}>30 derniers jours</SelectItem>
                <SelectItem value={quickFilterValue("period", "90d")}>90 derniers jours</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {filteredTotal === 0 ? (
          <EmptyPanel title="Aucun ticket trouvé" text="Aucun ticket de la direction ne correspond aux filtres sélectionnés." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1680px] text-sm">
              <thead className="bg-background/40 text-xs uppercase tracking-wider text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Numéro</th>
                  <th className="px-4 py-3 text-left font-semibold">Objet</th>
                  <th className="px-4 py-3 text-left font-semibold">Catégorie</th>
                  <th className="px-4 py-3 text-left font-semibold">Priorité</th>
                  <th className="px-4 py-3 text-left font-semibold">Statut</th>
                  <th className="px-4 py-3 text-left font-semibold">Service</th>
                  <th className="px-4 py-3 text-left font-semibold">Direction</th>
                  <th className="px-4 py-3 text-left font-semibold">Chef responsable</th>
                  <th className="px-4 py-3 text-left font-semibold">Agent affecté</th>
                  <th className="px-4 py-3 text-left font-semibold">Demandeur</th>
                  <th className="px-4 py-3 text-left font-semibold">Création</th>
                  <th className="px-4 py-3 text-left font-semibold">Mise à jour</th>
                  <th className="px-4 py-3 text-left font-semibold">Échéance délai</th>
                  <th className="px-4 py-3 text-left font-semibold">Escalade</th>
                  <th className="px-4 py-3 text-left font-semibold">Retard</th>
                  <th className="px-4 py-3 text-right font-semibold">Action</th>
                </tr>
              </thead>
              <tbody>
                {pagedTickets.map((ticket) => {
                  const serviceId = ticket.serviceId ?? "";
                  const chief = chiefByUnit.get(String(serviceId));
                  const escalation = latestEscalationByTicket.get(String(ticket.id));
                  const late = isTicketLate(ticket);
                  return (
                    <tr key={ticket.id} className="border-t border-border/40 transition hover:bg-card/40">
                      <td className="px-4 py-3">
                        <Link to="/app/supervision/tickets/$id" params={{ id: ticket.id }} className="font-mono text-xs font-semibold text-primary hover:underline">
                          {ticket.ref}
                        </Link>
                      </td>
                      <td className="max-w-[280px] px-4 py-3">
                        <div className="line-clamp-2 font-medium">{ticket.title}</div>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">{ticket.category || "—"}</td>
                      <td className="px-4 py-3"><PriorityBadge priority={ticket.priority} /></td>
                      <td className="px-4 py-3"><StatusBadge status={ticket.status} /></td>
                      <td className="px-4 py-3">{getServiceName(serviceId, unitMap)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{directionName}</td>
                      <td className="px-4 py-3">{chief?.name ?? "—"}</td>
                      <td className="px-4 py-3">{ticket.assigneeName ?? agentMap.get(String(ticket.assigneeId ?? ""))?.name ?? "—"}</td>
                      <td className="px-4 py-3">{ticket.requesterName || "—"}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDateTime(ticket.createdAt)}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDateTime(ticket.updatedAt)}</td>
                      <td className="px-4 py-3 text-xs text-muted-foreground">{formatDateTime(slaDeadline(ticket))}</td>
                      <td className="px-4 py-3">
                        {escalation ? (
                          <Badge className={cn("rounded-full", levelTone[escalation.level])}>
                            {levelLabel[escalation.level] ?? escalation.level}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        {late ? (
                          <Badge className="rounded-full bg-destructive/15 text-destructive">Délai dépassé</Badge>
                        ) : (
                          <Badge variant="outline" className="rounded-full text-success">Dans délai</Badge>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button asChild size="sm" variant="outline" className="h-8 rounded-full px-3 text-xs">
                          <Link to="/app/supervision/tickets/$id" params={{ id: ticket.id }}>
                            <Eye className="mr-1 h-3 w-3" />
                            Dossier
                          </Link>
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={filteredTotal}
          pageSize={pageSize}
          onChange={setPage}
          onPageSizeChange={setPageSize}
        />
      </GlassCard>
    </div>
  );
}

// ── Sous-composants ────────────────────────────────────────────────────────────

function isEscalationClosed(escalation: EscalationItem) {
  return escalation.status === "resolved" || escalation.status === "rejected";
}

function QuickFilterGroupLabel({ children }: { children: string }) {
  return (
    <div className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
      {children}
    </div>
  );
}

function isTicketLate(ticket: RequestItem) {
  return ACTIVE_STATUSES.has(ticket.status) && ticket.slaElapsed > ticket.slaHours;
}

function slaDeadline(ticket: RequestItem) {
  const created = new Date(ticket.createdAt).getTime();
  if (!Number.isFinite(created)) return undefined;
  return new Date(created + ticket.slaHours * 60 * 60 * 1000).toISOString();
}

function formatDateTime(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function resolutionHours(ticket: RequestItem) {
  const end = ticket.resolvedAt ?? ticket.closedAt;
  if (!end) return null;
  const startTime = new Date(ticket.createdAt).getTime();
  const endTime = new Date(end).getTime();
  if (!Number.isFinite(startTime) || !Number.isFinite(endTime) || endTime < startTime) return null;
  return Math.round(((endTime - startTime) / 3_600_000) * 10) / 10;
}

function averageResolutionHours(items: RequestItem[]) {
  const values = items
    .map(resolutionHours)
    .filter((value): value is number => typeof value === "number");
  if (values.length === 0) return null;
  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 10) / 10;
}

function getServiceName(serviceId: string | undefined, unitMap: Map<string, Unit>) {
  if (!serviceId) return "Non orienté";
  return unitMap.get(String(serviceId))?.name ?? `Service ${serviceId}`;
}

function sortTickets(a: RequestItem, b: RequestItem, sortKey: DirectorSortKey) {
  if (sortKey === "created_desc") {
    return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime();
  }
  if (sortKey === "sla_urgency") {
    return (a.slaHours - a.slaElapsed) - (b.slaHours - b.slaElapsed);
  }
  if (sortKey === "priority") {
    return (priorityWeight[b.priority] ?? 0) - (priorityWeight[a.priority] ?? 0);
  }
  if (sortKey === "status") {
    return (statusLabels[a.status] ?? a.status).localeCompare(statusLabels[b.status] ?? b.status);
  }
  return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
}

function distribution<T>(items: T[], labelFor: (item: T) => string) {
  const map = new Map<string, number>();
  items.forEach((item) => {
    const label = labelFor(item);
    map.set(label, (map.get(label) ?? 0) + 1);
  });
  return [...map.entries()]
    .map(([label, value]) => ({ label, value }))
    .sort((a, b) => b.value - a.value || a.label.localeCompare(b.label));
}

function DirectorSupervisionSkeleton() {
  return (
    <div className="mx-auto max-w-[1540px] space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-7 w-64 rounded-full" />
        <Skeleton className="h-10 w-[420px]" />
        <Skeleton className="h-4 w-[520px]" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
        {Array.from({ length: 15 }).map((_, i) => (
          <GlassCard key={i} className="space-y-3">
            <Skeleton className="h-4 w-28" />
            <Skeleton className="h-8 w-16" />
          </GlassCard>
        ))}
      </div>
      <GlassCard className="space-y-4 p-5">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="h-10 w-full rounded-full" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </GlassCard>
    </div>
  );
}

function DirectorMetricCard({
  label,
  value,
  icon: Icon,
  tone,
  loading,
}: {
  label: string;
  value: string | number;
  icon: typeof Activity;
  tone: "primary" | "success" | "warning" | "destructive";
  loading?: boolean;
}) {
  const tones = {
    primary: "bg-primary/10 text-primary",
    success: "bg-success/15 text-success",
    warning: "bg-warning/20 text-warning-foreground dark:text-warning",
    destructive: "bg-destructive/15 text-destructive",
  };
  return (
    <GlassCard className="flex min-h-[112px] flex-col justify-between gap-3 p-4">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={cn("grid h-9 w-9 place-items-center rounded-xl", tones[tone])}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      {loading ? (
        <Skeleton className="h-8 w-16" />
      ) : (
        <div className="text-3xl font-bold tracking-tight">{value}</div>
      )}
    </GlassCard>
  );
}

function DistributionBars({
  data,
  total,
  emptyLabel,
}: {
  data: { label: string; value: number }[];
  total: number;
  emptyLabel: string;
}) {
  if (data.length === 0 || total === 0) {
    return <p className="py-6 text-center text-sm text-muted-foreground">{emptyLabel}</p>;
  }
  return (
    <div className="space-y-3">
      {data.map((item) => {
        const pct = Math.round((item.value / Math.max(total, 1)) * 100);
        return (
          <div key={item.label} className="space-y-1.5">
            <div className="flex items-center justify-between gap-3 text-xs">
              <span className="truncate font-medium">{item.label}</span>
              <span className="shrink-0 text-muted-foreground">{item.value} · {pct}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-muted">
              <div className="h-full rounded-full bg-primary" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EmptyPanel({ title, text }: { title: string; text: string }) {
  return (
    <div className="grid min-h-[180px] place-items-center px-5 py-10 text-center">
      <div>
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl bg-muted">
          <ClipboardList className="h-5 w-5 text-muted-foreground" />
        </div>
        <h3 className="font-semibold">{title}</h3>
        <p className="mt-1 text-sm text-muted-foreground">{text}</p>
      </div>
    </div>
  );
}

function RateBadge({ value, dangerHigh = false }: { value: number; dangerHigh?: boolean }) {
  const good = dangerHigh ? value <= 10 : value >= 70;
  const warn = dangerHigh ? value <= 25 : value >= 40;
  return (
    <span className={cn(
      "inline-flex rounded-full px-2 py-0.5 text-xs font-semibold",
      good
        ? "bg-success/15 text-success"
        : warn
          ? "bg-warning/20 text-warning-foreground dark:text-warning"
          : "bg-destructive/15 text-destructive",
    )}>
      {value}%
    </span>
  );
}

function AvailabilityBadge({ value, open }: { value?: string; open: number }) {
  const computed = value ?? (open >= 8 ? "overload" : open >= 5 ? "busy" : "available");
  const toneMap: Record<string, string> = {
    available: "bg-success/15 text-success border-success/25",
    busy:      "bg-info/15 text-info border-info/25",
    overload:  "bg-destructive/15 text-destructive border-destructive/25",
    offline:   "bg-muted text-muted-foreground border-border",
    off:       "bg-muted text-muted-foreground border-border",
  };
  const labelMap: Record<string, string> = {
    available: "Disponible",
    busy:      "Occupé",
    overload:  "Surchargé",
    offline:   "Indisponible",
    off:       "Indisponible",
  };
  return (
    <span className={cn(
      "inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-medium",
      toneMap[computed] ?? toneMap["busy"],
    )}>
      {labelMap[computed] ?? computed}
    </span>
  );
}

function Kpi({
  label, value, hint, icon: Icon, tone, loading,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Activity;
  tone: "primary" | "success" | "warning" | "destructive";
  loading?: boolean;
}) {
  const tones = {
    primary:     "bg-primary/10 text-primary",
    success:     "bg-success/15 text-success",
    warning:     "bg-warning/20 text-warning-foreground dark:text-warning",
    destructive: "bg-destructive/15 text-destructive",
  };
  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={"grid h-9 w-9 place-items-center rounded-xl " + tones[tone]}>
          <Icon className="h-4 w-4" />
        </span>
      </div>
      <div>
        {loading
          ? <Loader2 className="h-7 w-7 animate-spin text-muted-foreground/40" />
          : <div className="text-3xl font-bold tracking-tight">{value}</div>}
        {hint && (
          <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
            <ChevronRight className="h-3 w-3" /> {hint}
          </div>
        )}
      </div>
    </GlassCard>
  );
}

export function ComingSoon({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="mx-auto max-w-3xl">
      <GlassCard strong className="py-16 text-center">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">{desc}</p>
      </GlassCard>
    </div>
  );
}
