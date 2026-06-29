import { createFileRoute, Link } from "@tanstack/react-router";
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
import { priorityLabels } from "@/lib/mock-data";
import { fetchDirections } from "@/lib/api/directions-units";
import type { EscalationItem } from "@/lib/mock-data";
import { useMemo, useState, useEffect } from "react";
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
  beforeLoad: () => requireRole("chief", "director", "admin"),
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
  DG: "bg-gradient-to-r from-primary to-accent text-background",
};

const levelLabel: Record<EscalationItem["level"], string> = {
  L1: "Agent N1",
  L2: "Chef de service",
  L3: "Directeur",
  DG: "Direction Générale",
};

// ── Composant principal ────────────────────────────────────────────────────────

function SupervisionPage() {
  const [role] = useRole();
  const qc = useQueryClient();
  const sessionUser = useUser();
  const directionId = sessionUser?.direction_id;
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
        role_names: ["agent"],
        direction_ids: [],
      }),
    }),
    onSuccess: () => { toast.success("Message envoyé à votre équipe."); setTeamMsg(""); },
    onError: () => toast.error("Erreur lors de l'envoi du message."),
  });

  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | EscalationItem["status"]>("all");
  const [agentLayout, setAgentLayout] = useState<LayoutMode>("list");
  const [escLayout, setEscLayout] = useState<LayoutMode>("list");

  // ── Dialogs ────────────────────────────────────────────────────────────────
  const [reassignOpen, setReassignOpen] = useState(false);
  const [reassignEsc, setReassignEsc] = useState<EscalationItem | null>(null);
  const [reassignAgentId, setReassignAgentId] = useState("");
  const [reassignNote, setReassignNote] = useState("");

  const [transferOpen, setTransferOpen] = useState(false);
  const [transferEsc, setTransferEsc] = useState<EscalationItem | null>(null);
  const [transferReason, setTransferReason] = useState("");

  // ── Queries ────────────────────────────────────────────────────────────────
  const { data: dirsData = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 60_000,
  });

  const { data: escData, isLoading: loadEsc } = useQuery({
    queryKey: ["escalations"],
    queryFn: () => fetchEscalations({ limit: 100 }),
    staleTime: 30_000,
  });
  const esc: EscalationItem[] = escData?.items ?? [];

  const { data: agentsData, isLoading: loadAgents } = useQuery({
    queryKey: ["agents-supervision", directionId],
    queryFn: () => fetchUsers({ role: "agent", direction_id: directionId, limit: 100 }),
    staleTime: 60_000,
  });
  const agents: AccountUser[] = agentsData?.items ?? [];

  const { data: ticketsData, isLoading: loadTickets } = useQuery({
    queryKey: ["tickets-supervision", directionId],
    queryFn: () => fetchRequests({ direction_id: directionId, limit: 500 }),
    enabled: !!directionId,
    staleTime: 30_000,
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
        name: agent.name,
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
    const filtered = esc.filter((e) => filter === "all" || e.status === filter);
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

  if (role === "dg") {
    return (
      <div className="mx-auto max-w-3xl">
        <GlassCard className="py-16 text-center">
          <h1 className="text-2xl font-bold tracking-tight">Accès restreint</h1>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            La supervision opérationnelle est réservée aux chefs de service et administrateurs.
            Consultez la vue globale DG pour le pilotage stratégique.
          </p>
          <div className="mt-6">
            <Link
              to="/app/dg"
              className="inline-flex items-center gap-2 rounded-full gradient-primary px-5 py-2.5 text-sm font-semibold text-background shadow-lg"
            >
              Vue globale DG
            </Link>
          </div>
        </GlassCard>
      </div>
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
            Supervision du service
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Charge, SLA agent par agent et escalades en cours — mis à jour en continu.
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
      {role === "chief" && (
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
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi label="Escalades ouvertes"  value={kpis.escalationsOpen}  tone="destructive" icon={AlertTriangle} hint={`${esc.length} au total`}               loading={loadEsc} />
        <Kpi label="Demandes en charge"  value={kpis.totalOpen}        tone="primary"     icon={Activity}     hint={`${agentStats.length} agents actifs`}     loading={loadingStats} />
        <Kpi label="SLA dépassés"        value={kpis.slaBreachedTotal} tone="warning"     icon={Clock}        hint="Tickets en retard sur le service"          loading={loadingStats} />
        <Kpi label="Agents surchargés"   value={kpis.overloadCount}    tone="warning"     icon={Users2}       hint="≥ 8 tickets ouverts"                       loading={loadingStats} />
      </div>

      {/* ── Charts ── */}
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="font-semibold">Charge & retards par agent</h3>
              <p className="text-xs text-muted-foreground">Tickets ouverts vs SLA dépassés</p>
            </div>
          </div>
          {loadingStats ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/40" />
            </div>
          ) : chartData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              Aucun agent dans le service
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
                  <Bar dataKey="retards" name="SLA dépassés"  fill="var(--chart-4)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <GlassCard>
          <h3 className="font-semibold">Distribution des escalades</h3>
          <p className="mb-4 text-xs text-muted-foreground">Niveaux actuellement actifs</p>
          <div className="space-y-3">
            {(["L1", "L2", "L3", "DG"] as const).map((lvl) => {
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
      <GlassCard className="space-y-4 p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Escalades en cours</h3>
            <p className="text-xs text-muted-foreground">
              {visibleEsc.length} résultat(s) — triées par urgence SLA décroissante
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-4 w-4 text-muted-foreground" />
            <Select value={filter} onValueChange={(v) => setFilter(v as typeof filter)}>
              <SelectTrigger className="h-9 w-full rounded-full sm:w-44">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
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
                        to="/app/requests/$id"
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
                    <div className="text-xs text-muted-foreground">SLA dépassé</div>
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
                      {e.requestId && (
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
                      {e.requestId && (
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
                      {e.requestId && (
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
              <GlassCard key={e.id} className="flex flex-col gap-2 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={cn("rounded-full px-2.5 py-0.5 text-[10px] font-bold tracking-wider", levelTone[e.level])}>
                    {levelLabel[e.level] ?? e.level}
                  </span>
                  {e.requestId ? (
                    <Link
                      to="/app/requests/$id"
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
                          disabled={reviewMut.isPending} onClick={() => reviewMut.mutate(e.id)}>
                          En revue
                        </Button>
                      )}
                      {e.requestId && (
                        <>
                          <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                            onClick={() => { setReassignEsc(e); setReassignAgentId(""); setReassignOpen(true); }}>
                            <UserPlus className="h-2.5 w-2.5" />
                          </Button>
                          <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                            disabled={returnToAgentMut.isPending} onClick={() => returnToAgentMut.mutate(e)}>
                            <RotateCcw className="h-2.5 w-2.5" />
                          </Button>
                          <Button size="sm" variant="outline" className="h-6 rounded-full px-2 text-[10px]"
                            disabled={takeOverMut.isPending} onClick={() => takeOverMut.mutate(e)}>
                            <ArrowRight className="h-2.5 w-2.5" />
                          </Button>
                          <Button size="sm"
                            className="h-6 rounded-full px-2 text-[10px] gradient-primary text-background"
                            onClick={() => { setTransferEsc(e); setTransferReason(""); setTransferOpen(true); }}>
                            <ArrowUpRight className="h-2.5 w-2.5" />
                          </Button>
                        </>
                      )}
                      <Button size="sm"
                        className="h-6 rounded-full px-2 text-[10px] gradient-primary text-background"
                        disabled={resolveMut.isPending} onClick={() => resolveMut.mutate(e.id)}>
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
      <GlassCard className="overflow-hidden p-0">
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
              ? "Aucun agent trouvé pour ce service."
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
                  <th className="px-5 py-3 text-right font-semibold">SLA dépassés</th>
                  <th className="px-5 py-3 text-right font-semibold">Critiques</th>
                  <th className="px-5 py-3 text-right font-semibold">Disponibilité</th>
                </tr>
              </thead>
              <tbody>
                {pagedAgents.map((a) => (
                  <tr
                    key={a.id}
                    className={cn(
                      "border-t border-border/40 transition hover:bg-card/40",
                      a.slaBreached > 0 && "bg-destructive/[0.02]",
                    )}
                  >
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-3">
                        <span className="grid h-9 w-9 place-items-center rounded-full gradient-primary text-[11px] font-bold text-background">
                          {a.name.split(" ").map((p) => p[0]).join("").slice(0, 2)}
                        </span>
                        <div>
                          <div className="font-medium">{a.name}</div>
                          <div className="text-xs text-muted-foreground">
                            {dirsData.find((d) => String(d.id) === String(a.directionId))?.name ?? a.unitId ?? "—"}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right font-semibold">{a.open}</td>
                    <td className="px-5 py-3.5 text-right text-muted-foreground">{a.inProgress}</td>
                    <td className="px-5 py-3.5 text-right text-muted-foreground">{a.pending}</td>
                    <td className="px-5 py-3.5 text-right">
                      {a.slaBreached > 0
                        ? <span className="font-semibold text-destructive">{a.slaBreached}</span>
                        : <span className="text-muted-foreground">0</span>}
                    </td>
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
                      {dirsData.find((d) => String(d.id) === String(a.directionId))?.name ?? a.unitId ?? "—"}
                    </div>
                  </div>
                  <AvailabilityBadge value={a.availability} open={a.open} />
                </div>
                <div className="grid grid-cols-3 gap-2 rounded-xl bg-muted/30 px-2 py-2 text-center">
                  <div>
                    <div className="text-sm font-bold">{a.open}</div>
                    <div className="text-[10px] text-muted-foreground">Ouverts</div>
                  </div>
                  <div>
                    <div className={cn("text-sm font-bold", a.slaBreached > 0 && "text-destructive")}>{a.slaBreached}</div>
                    <div className="text-[10px] text-muted-foreground">Retards</div>
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
      <Dialog open={reassignOpen} onOpenChange={setReassignOpen}>
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
      <Dialog open={transferOpen} onOpenChange={setTransferOpen}>
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

// ── Sous-composants ────────────────────────────────────────────────────────────

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
