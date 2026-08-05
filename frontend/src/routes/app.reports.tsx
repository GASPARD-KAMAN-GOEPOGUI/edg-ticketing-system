import { createFileRoute } from "@tanstack/react-router";
import { requireRole } from "@/lib/auth-guard";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  BarChart3,
  FileSpreadsheet,
  FileText,
  Star,
  Download,
  CalendarRange,
  Filter,
  Loader2,
  MoreHorizontal,
} from "lucide-react";
import { statusLabels } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { useState, useMemo } from "react";
import { useRole, useUser } from "@/lib/session";
import { useQuery } from "@tanstack/react-query";
import { fetchRequests } from "@/lib/api/requests";
import { fetchCsatStats, fetchCsatMonthly } from "@/lib/api/csat";
import { downloadReport, fetchAgentReport, fetchUnityReport, type ExportFormat } from "@/lib/api/reports";
import { toast } from "sonner";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
} from "recharts";

export const Route = createFileRoute("/app/reports")({
  beforeLoad: () => requireRole("chief-service", "chief-departement", "director", "admin"),
  head: () => ({ meta: [{ title: "Rapports — EDG Support" }] }),
  component: ReportsPage,
});

const ACTIVE = new Set(["new", "qualifying", "qualified", "assigned", "in_progress", "pending", "reopened"]);
const COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

function isDirectionUnit(label?: string) {
  return (label ?? "").trim().toLowerCase().startsWith("direction ");
}

function ReportsPage() {
  const [role] = useRole();
  const sessionUser = useUser();
  const directorDirectionId = role === "director"
    ? (sessionUser?.direction_id ?? sessionUser?.unit_id)
    : undefined;
  const [period, setPeriod] = useState("year");
  const [direction, setDirection] = useState(
    role === "director" ? (directorDirectionId ?? "all") : "all",
  );
  const [exportFormat, setExportFormat] = useState<ExportFormat>("excel");
  const [exportPending, setExportPending] = useState(false);

  const directionFilter =
    role === "director"
      ? directorDirectionId
      : direction === "all"
        ? undefined
        : direction;

  const { data: reqData, isLoading: loadReq } = useQuery({
    queryKey: ["report-requests", directionFilter],
    queryFn: () => fetchRequests({ direction_id: directionFilter, limit: 500 }),
    enabled: role !== "director" || !!directionFilter,
    staleTime: 60_000,
  });

  const { data: csat, isLoading: loadCsat } = useQuery({
    queryKey: ["csat-stats"],
    queryFn: fetchCsatStats,
    staleTime: 60_000,
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    staleTime: 300_000,
  });

  const { data: agentReport = [], isLoading: loadAgent } = useQuery({
    queryKey: ["report-agents"],
    queryFn: () => fetchAgentReport(),
    staleTime: 60_000,
  });

  const { data: unityReport = [], isLoading: loadUnity } = useQuery({
    queryKey: ["report-unity", directionFilter],
    queryFn: () => fetchUnityReport(undefined, undefined, directionFilter),
    enabled: !!directionFilter,
    staleTime: 60_000,
  });

  const { data: scopedUnits = [], isLoading: loadScopedUnits } = useQuery({
    queryKey: ["report-service-units", directionFilter],
    queryFn: () => fetchUnits(directionFilter),
    enabled: !!directionFilter,
    staleTime: 60_000,
  });

  const { data: csatMonthly = [] } = useQuery({
    queryKey: ["csat-monthly"],
    queryFn: () => fetchCsatMonthly(12),
    staleTime: 60_000,
  });

  const isLoading = loadReq || loadCsat;
  const items = reqData?.items ?? [];
  const total = reqData?.total ?? 0;

  const avgResolutionH = useMemo(() => {
    const resolved = items.filter(
      (r) => ["resolved", "closed"].includes(r.status) && r.slaElapsed > 0,
    );
    if (resolved.length === 0) return null;
    return Math.round(resolved.reduce((acc, r) => acc + r.slaElapsed, 0) / resolved.length);
  }, [items]);

  const openCount = items.filter((r) => ACTIVE.has(r.status)).length;
  const slaActive = items.filter((r) => ACTIVE.has(r.status));
  const slaOk = slaActive.filter((r) => r.slaElapsed <= r.slaHours).length;
  const slaPct = slaActive.length > 0 ? Math.round((slaOk / slaActive.length) * 100) : null;
  const csatScore = csat?.global != null ? csat.global.toFixed(1) : null;
  const csatCount = csat?.count ?? 0;

  const categoryData = useMemo(() => {
    const acc: Record<string, number> = {};
    items.forEach((r) => { acc[r.category] = (acc[r.category] ?? 0) + 1; });
    return Object.entries(acc)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 5);
  }, [items]);

  const statusBarData = useMemo(() => {
    const acc: Record<string, number> = {};
    items.forEach((r) => { acc[r.status] = (acc[r.status] ?? 0) + 1; });
    return Object.entries(acc)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({
        name: (statusLabels as Record<string, string>)[k] ?? k,
        count: v,
      }))
      .sort((a, b) => b.count - a.count);
  }, [items]);

  const directionBarData = useMemo(() => {
    const acc: Record<string, { total: number; resolved: number }> = {};
    items.forEach((r) => {
      const d = r.directionId ?? "—";
      if (!acc[d]) acc[d] = { total: 0, resolved: 0 };
      acc[d].total++;
      if (["resolved", "closed"].includes(r.status)) acc[d].resolved++;
    });
    return Object.entries(acc)
      .slice(0, 8)
      .map(([id, st]) => {
        const dir = directions.find((d) => d.id === id);
        const name = dir
          ? dir.name.replace("Direction ", "").substring(0, 20)
          : id.toUpperCase().substring(0, 10);
        return {
          name,
          demandes: st.total,
          sla: st.total > 0 ? Math.round((st.resolved / st.total) * 100) : 0,
        };
      });
  }, [items]);

  const csatDistData = useMemo(() => {
    if (!csat?.distribution) return [];
    return Object.entries(csat.distribution)
      .map(([k, v]) => ({ name: `${k}★`, value: Number(v) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [csat]);

  const visibleUnityReport = useMemo(() => {
    if (!directionFilter) return [];
    const serviceUnits = scopedUnits.filter((unit) => !isDirectionUnit(unit.name));
    const byUnit = new Map(unityReport.map((row) => [String(row.unity_id), row]));
    const merged = serviceUnits.map((unit) => byUnit.get(unit.id) ?? ({
      unity_id: unit.id,
      unity_label: unit.name,
      unity_codename: unit.code,
      total: 0,
      resolved: 0,
      active: 0,
      sla_breached: 0,
      assigned_total: 0,
      resolved_total: 0,
      pending_total: 0,
      escalated_total: 0,
      avg_resolution_hours: null,
      resolution_rate: 0,
    }));
    const seen = new Set(merged.map((row) => String(row.unity_id)));
    for (const row of unityReport) {
      if (seen.has(String(row.unity_id)) || isDirectionUnit(row.unity_label)) continue;
      merged.push(row);
      seen.add(String(row.unity_id));
    }
    return merged.sort((a, b) => {
      const aTotal = Number(a.assigned_total ?? a.total ?? 0);
      const bTotal = Number(b.assigned_total ?? b.total ?? 0);
      if (bTotal !== aTotal) return bTotal - aTotal;
      return a.unity_label.localeCompare(b.unity_label);
    });
  }, [directionFilter, scopedUnits, unityReport]);

  const handleExport = async (type: Parameters<typeof downloadReport>[0], fmt?: ExportFormat) => {
    if (type === "by-unity" && !directionFilter) {
      toast.error("Sélectionnez une direction pour exporter ses services.");
      return;
    }
    setExportPending(true);
    try {
      const now = new Date();
      const params: Record<string, string> = {};

      if (type === "daily") {
        params.date = now.toISOString().slice(0, 10);
      } else {
        // Traduire le filtre period en start/end pour tous les autres exports
        let start: Date;
        if (period === "month") {
          start = new Date(now.getFullYear(), now.getMonth(), 1);
        } else if (period === "quarter") {
          const q = Math.floor(now.getMonth() / 3);
          start = new Date(now.getFullYear(), q * 3, 1);
        } else if (period === "ytd") {
          start = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
        } else {
          start = new Date(now.getFullYear(), 0, 1);
        }
        params.start = start.toISOString().slice(0, 10);
        params.end = now.toISOString().slice(0, 10);
        if (type === "monthly") {
          params.year = String(now.getFullYear());
          params.month = String(now.getMonth() + 1);
        }
        if (directionFilter) params.direction_id = String(directionFilter);
      }

      await downloadReport(type, fmt ?? exportFormat, params);
      toast.success("Export téléchargé.");
    } catch {
      toast.error("Erreur lors de l'export — vérifiez que le backend est démarré.");
    } finally {
      setExportPending(false);
    }
  };

  const roleLabel =
    role === "director" ? "Direction"
    : role === "chief-service" || role === "chief-departement" ? "Service"
    : "Globaux";

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <BarChart3 className="h-3 w-3" /> Rapports {roleLabel}
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Rapports &amp; Analyses
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Indicateurs en temps réel — données connectées au backend de production.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={exportFormat} onValueChange={(v) => setExportFormat(v as ExportFormat)}>
            <SelectTrigger className="h-9 w-28 rounded-full sm:w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="excel">
                <span className="flex items-center gap-1.5"><FileSpreadsheet className="h-3.5 w-3.5" />Excel</span>
              </SelectItem>
              <SelectItem value="csv">
                <span className="flex items-center gap-1.5"><FileSpreadsheet className="h-3.5 w-3.5" />CSV</span>
              </SelectItem>
              <SelectItem value="pdf">
                <span className="flex items-center gap-1.5"><FileText className="h-3.5 w-3.5" />PDF</span>
              </SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            className="rounded-full"
            disabled={exportPending}
            onClick={() => handleExport("monthly", "pdf")}
          >
            {exportPending
              ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              : <FileText className="mr-1.5 h-4 w-4" />}
            PDF
          </Button>
          <Button
            className="rounded-full gradient-primary text-background shadow-lg shadow-primary/30"
            onClick={() => handleExport("monthly")}
            disabled={exportPending}
          >
            {exportPending
              ? <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
              : <Download className="mr-1.5 h-4 w-4" />}
            Exporter rapport
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" className="rounded-full" disabled={exportPending}>
                <MoreHorizontal className="h-4 w-4" />
                <span className="sr-only">Autres exports</span>
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              <DropdownMenuLabel className="text-xs text-muted-foreground">
                Autres exports
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => handleExport("daily")}>
                <Download className="h-4 w-4" /> Journalier
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleExport("by-agent")}>
                <Download className="h-4 w-4" /> Par agent
              </DropdownMenuItem>
              <DropdownMenuItem
                disabled={!directionFilter}
                onSelect={() => handleExport("by-unity")}
              >
                <Download className="h-4 w-4" /> Par service
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleExport("sla")}>
                <Download className="h-4 w-4" /> Délai
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => handleExport("csat")}>
                <Download className="h-4 w-4" /> CSAT
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <GlassCard className="flex flex-wrap items-center gap-3 p-4">
        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Filter className="h-3.5 w-3.5" /> Filtres
        </div>
        <Select value={period} onValueChange={setPeriod}>
          <SelectTrigger className="h-9 w-full rounded-full sm:w-44">
            <CalendarRange className="mr-1 h-3.5 w-3.5" />
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="month">Ce mois</SelectItem>
            <SelectItem value="quarter">Ce trimestre</SelectItem>
            <SelectItem value="year">Année en cours</SelectItem>
            <SelectItem value="ytd">Glissant 12 mois</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={direction}
          onValueChange={setDirection}
          disabled={role === "director"}
        >
          <SelectTrigger className="h-9 w-full rounded-full sm:w-56">
            <SelectValue placeholder="Direction" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes les directions</SelectItem>
            {directions.map((d) => (
              <SelectItem key={d.id} value={d.id}>
                {d.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {isLoading ? (
          <Loader2 className="ml-auto h-4 w-4 animate-spin text-muted-foreground" />
        ) : (
          <span className="ml-auto text-xs text-muted-foreground">
            {total.toLocaleString("fr-FR")} tickets chargés
          </span>
        )}
      </GlassCard>

      {/* KPIs réels */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <GlassCard>
          <div className="text-sm text-muted-foreground">Volume total</div>
          {isLoading ? (
            <Loader2 className="mt-2 h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <>
              <div className="mt-2 text-3xl font-bold tracking-tight">
                {total.toLocaleString("fr-FR")}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {openCount} en cours
              </div>
            </>
          )}
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Taux délai (actif)</div>
          {isLoading ? (
            <Loader2 className="mt-2 h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <>
              <div
                className={`mt-2 text-3xl font-bold tracking-tight ${
                  slaPct != null && slaPct >= 90 ? "text-success" : "text-warning"
                }`}
              >
                {slaPct != null ? `${slaPct}%` : "—"}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">Objectif ≥ 90%</div>
            </>
          )}
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Délai moyen résolution</div>
          {isLoading ? (
            <Loader2 className="mt-2 h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <>
              <div className="mt-2 text-3xl font-bold tracking-tight">
                {avgResolutionH != null ? `${avgResolutionH}h` : "—"}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {avgResolutionH != null ? "Moyenne sur tickets résolus" : "Aucun ticket résolu"}
              </div>
            </>
          )}
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Satisfaction (CSAT)</div>
          {loadCsat ? (
            <Loader2 className="mt-2 h-6 w-6 animate-spin text-muted-foreground" />
          ) : (
            <>
              <div className="mt-2 flex items-baseline gap-1">
                <span className="text-3xl font-bold tracking-tight">
                  {csatScore ?? "—"}
                </span>
                {csatScore && (
                  <span className="text-base text-muted-foreground">/ 5</span>
                )}
              </div>
              <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                <Star className="h-3 w-3 text-amber-400" />
                {csatCount > 0 ? `${csatCount} avis` : "Aucun avis"}
              </div>
            </>
          )}
        </GlassCard>
      </div>

      {/* Graphiques principaux */}
      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <div className="mb-4">
            <h3 className="font-semibold">Distribution par statut</h3>
            <p className="text-xs text-muted-foreground">
              Répartition actuelle des tickets
            </p>
          </div>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : statusBarData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              Aucune donnée disponible
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={statusBarData}
                  layout="vertical"
                  margin={{ left: 4 }}
                >
                  <CartesianGrid
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={80}
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    dataKey="count"
                    name="Tickets"
                    fill="var(--chart-1)"
                    radius={[0, 6, 6, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <GlassCard>
          <h3 className="font-semibold">Répartition par catégorie</h3>
          <p className="mb-2 text-xs text-muted-foreground">Top motifs sur la période</p>
          {isLoading ? (
            <div className="flex h-56 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : categoryData.length === 0 ? (
            <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">
              Aucune donnée
            </div>
          ) : (
            <>
              <div className="h-44">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={categoryData}
                      dataKey="value"
                      nameKey="name"
                      cx="50%"
                      cy="50%"
                      innerRadius={40}
                      outerRadius={70}
                      paddingAngle={3}
                      stroke="none"
                    >
                      {categoryData.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "var(--popover)",
                        border: "1px solid var(--border)",
                        borderRadius: 12,
                        fontSize: 12,
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="grid grid-cols-1 gap-1.5 text-xs">
                {categoryData.map((c, i) => (
                  <li key={c.name} className="flex items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-sm"
                      style={{ background: COLORS[i % COLORS.length] }}
                    />
                    <span className="truncate text-muted-foreground">{c.name}</span>
                    <span className="ml-auto font-medium">{c.value}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </GlassCard>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <GlassCard className="lg:col-span-2">
          <h3 className="mb-1 font-semibold">Performance par direction</h3>
          <p className="mb-4 text-xs text-muted-foreground">
            Volume total et taux de résolution
          </p>
          {isLoading ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : directionBarData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              Aucune donnée par direction
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={directionBarData}
                  layout="vertical"
                  margin={{ left: 4 }}
                >
                  <CartesianGrid
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                    horizontal={false}
                  />
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    width={80}
                    tick={{ fontSize: 10 }}
                    stroke="var(--muted-foreground)"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar
                    dataKey="demandes"
                    name="Tickets"
                    fill="var(--chart-1)"
                    radius={[0, 4, 4, 0]}
                  />
                  <Bar
                    dataKey="sla"
                    name="% résolu"
                    fill="var(--chart-2)"
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>

        <GlassCard>
          <h3 className="mb-1 font-semibold">Distribution CSAT</h3>
          <p className="mb-4 text-xs text-muted-foreground">Répartition des notes reçues</p>
          {loadCsat ? (
            <div className="flex h-64 items-center justify-center">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : csatDistData.length === 0 ? (
            <div className="flex h-64 items-center justify-center text-sm text-muted-foreground">
              Aucun avis reçu
            </div>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={csatDistData}>
                  <CartesianGrid
                    stroke="var(--border)"
                    strokeDasharray="3 3"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    stroke="var(--muted-foreground)"
                  />
                  <Tooltip
                    contentStyle={{
                      background: "var(--popover)",
                      border: "1px solid var(--border)",
                      borderRadius: 12,
                      fontSize: 12,
                    }}
                  />
                  <Bar
                    dataKey="value"
                    name="Avis"
                    fill="var(--chart-3)"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </GlassCard>
      </div>

      {/* Évolution CSAT mensuelle */}
      <GlassCard>
        <h3 className="mb-1 font-semibold">Évolution CSAT mensuelle</h3>
        <p className="mb-4 text-xs text-muted-foreground">
          Score moyen sur les 12 derniers mois (1 à 5)
        </p>
        {csatMonthly.length === 0 ? (
          <div className="flex h-56 items-center justify-center text-sm text-muted-foreground">
            Aucune donnée mensuelle disponible
          </div>
        ) : (
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={csatMonthly} margin={{ left: -8 }}>
                <CartesianGrid
                  stroke="var(--border)"
                  strokeDasharray="3 3"
                  vertical={false}
                />
                <XAxis
                  dataKey="month"
                  tick={{ fontSize: 11 }}
                  stroke="var(--muted-foreground)"
                />
                <YAxis
                  domain={[0, 5]}
                  tickCount={6}
                  tick={{ fontSize: 11 }}
                  stroke="var(--muted-foreground)"
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: 12,
                    fontSize: 12,
                  }}
                  formatter={(v: number) => [`${v.toFixed(2)} / 5`, "Score CSAT"]}
                />
                <Line
                  type="monotone"
                  dataKey="avg"
                  name="Score CSAT"
                  stroke="var(--chart-4)"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: "var(--chart-4)" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </GlassCard>

      {/* Rapport par agent */}
      <GlassCard>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Performance par agent</h3>
            <p className="text-xs text-muted-foreground">
              Tickets assignés, résolus et taux de résolution par agent DSI
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="rounded-full"
            onClick={() => handleExport("by-agent")}
            disabled={exportPending}
          >
            {exportPending
              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              : <Download className="mr-1.5 h-3.5 w-3.5" />}
            Exporter agents
          </Button>
        </div>
        {loadAgent ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : agentReport.length === 0 ? (
          <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
            Aucune donnée agent disponible pour cette période.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/40 text-left">
                  <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">Agent</th>
                  <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">Unité</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Assignés</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Résolus</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Escaladés</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Moy. résol. (h)</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">Taux</th>
                </tr>
              </thead>
              <tbody>
                {agentReport.map((row, i) => (
                  <tr key={i} className="border-b border-border/20 last:border-0">
                    <td className="py-2.5 pr-4 font-medium">{row.agent_name}</td>
                    <td className="py-2.5 pr-4 text-muted-foreground">{row.unity_label}</td>
                    <td className="py-2.5 pr-4 text-right">{row.assigned_total}</td>
                    <td className="py-2.5 pr-4 text-right text-success">{row.resolved_total}</td>
                    <td className="py-2.5 pr-4 text-right text-warning">{row.escalated_total}</td>
                    <td className="py-2.5 pr-4 text-right">{row.avg_resolution_hours?.toFixed(1) ?? "—"}</td>
                    <td className={`py-2.5 text-right font-semibold ${row.resolution_rate >= 80 ? "text-success" : row.resolution_rate >= 50 ? "text-warning" : "text-destructive"}`}>
                      {row.resolution_rate}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

      {/* Rapport par service */}
      <GlassCard>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold">Performance par service</h3>
            <p className="text-xs text-muted-foreground">
              Tickets traités, résolus et taux de résolution par service (unité)
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            className="rounded-full"
            onClick={() => handleExport("by-unity")}
            disabled={exportPending || !directionFilter}
          >
            {exportPending
              ? <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              : <Download className="mr-1.5 h-3.5 w-3.5" />}
            Exporter services
          </Button>
        </div>
        {loadUnity || (!!directionFilter && loadScopedUnits) ? (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : visibleUnityReport.length === 0 ? (
          <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
            {directionFilter
              ? "Aucun service rattaché à cette direction pour cette période."
              : "Sélectionnez une direction pour voir ses services."}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border/40 text-left">
                  <th className="pb-2 pr-4 text-xs font-medium text-muted-foreground">Service</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Assignés</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Résolus</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">En attente</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Escaladés</th>
                  <th className="pb-2 pr-4 text-right text-xs font-medium text-muted-foreground">Moy. résol. (h)</th>
                  <th className="pb-2 text-right text-xs font-medium text-muted-foreground">Taux</th>
                </tr>
              </thead>
              <tbody>
                {visibleUnityReport.map((row, i) => {
                  const assigned = row.assigned_total ?? row.total ?? 0;
                  const resolved = row.resolved_total ?? row.resolved ?? 0;
                  const pending = row.pending_total ?? 0;
                  const escalated = row.escalated_total ?? 0;
                  const rate = Number(row.resolution_rate ?? 0);
                  return (
                    <tr key={i} className="border-b border-border/20 last:border-0">
                      <td className="py-2.5 pr-4 font-medium">{row.unity_label}</td>
                      <td className="py-2.5 pr-4 text-right">{assigned}</td>
                      <td className="py-2.5 pr-4 text-right text-success">{resolved}</td>
                      <td className="py-2.5 pr-4 text-right text-warning">{pending}</td>
                      <td className="py-2.5 pr-4 text-right text-destructive">{escalated}</td>
                      <td className="py-2.5 pr-4 text-right">{row.avg_resolution_hours?.toFixed(1) ?? "—"}</td>
                      <td className={`py-2.5 text-right font-semibold ${rate >= 80 ? "text-success" : rate >= 50 ? "text-warning" : "text-destructive"}`}>
                        {rate}%
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </GlassCard>

    </div>
  );
}
