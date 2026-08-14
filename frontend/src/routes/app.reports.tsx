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
  Loader2,
  MoreHorizontal,
} from "lucide-react";
import { statusLabels } from "@/lib/mock-data";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { useState, useMemo } from "react";
import { useRole, useUser } from "@/lib/session";
import { useQuery } from "@tanstack/react-query";
import { fetchRequests } from "@/lib/api/requests";
import { downloadReport, fetchAgentReport, fetchCsatReport, fetchUnityReport, type ExportFormat } from "@/lib/api/reports";
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
  const isChiefService = role === "chief-service";
  const directorDirectionId = role === "director"
    ? (sessionUser?.direction_id ?? sessionUser?.unit_id)
    : undefined;
  const [period] = useState("year");
  const [direction] = useState(
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
  const serviceReportReady = isChiefService || !!directionFilter;

  const { data: reqData, isLoading: loadReq } = useQuery({
    queryKey: ["report-requests", directionFilter],
    queryFn: () => fetchRequests({ direction_id: directionFilter, limit: 500 }),
    enabled: role !== "director" || !!directionFilter,
    staleTime: 60_000,
  });

  const { data: csatReport, isLoading: loadCsat } = useQuery({
    queryKey: ["report-csat", role, sessionUser?.unit_id],
    queryFn: () => fetchCsatReport(),
    staleTime: 60_000,
  });

  const { data: directions = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: fetchDirections,
    enabled: !isChiefService,
    staleTime: 300_000,
  });

  const { data: agentReport = [], isLoading: loadAgent } = useQuery({
    queryKey: ["report-agents", role, sessionUser?.unit_id],
    queryFn: () => fetchAgentReport(),
    staleTime: 60_000,
  });

  const { data: unityReport = [], isLoading: loadUnity } = useQuery({
    queryKey: ["report-unity", directionFilter, role, sessionUser?.unit_id],
    queryFn: () => fetchUnityReport(undefined, undefined, directionFilter),
    enabled: isChiefService || !!directionFilter,
    staleTime: 60_000,
  });

  const { data: scopedUnits = [], isLoading: loadScopedUnits } = useQuery({
    queryKey: ["report-service-units", directionFilter],
    queryFn: () => fetchUnits(directionFilter),
    enabled: !!directionFilter,
    staleTime: 60_000,
  });

  const isLoading = loadReq || loadCsat;
  const items = reqData?.items ?? [];
  const total = reqData?.total ?? 0;

  const openCount = items.filter((r) => ACTIVE.has(r.status)).length;
  const csatScore = csatReport?.summary?.avg_rating != null
    ? Number(csatReport.summary.avg_rating).toFixed(1)
    : null;
  const csatCount = csatReport?.summary?.total_ratings ?? 0;

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
    if (!csatReport?.by_rating) return [];
    return csatReport.by_rating
      .map((row) => ({ name: `${row.rating}★`, value: Number(row.count) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  }, [csatReport]);
  const csatMonthly = useMemo(
    () => (csatReport?.monthly_evolution ?? []).map((row) => ({
      month: row.month,
      avg: Number(row.avg_rating ?? 0),
      count: Number(row.total_ratings ?? 0),
    })),
    [csatReport],
  );

  const visibleUnityReport = useMemo(() => {
    if (isChiefService) return unityReport;
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
  }, [directionFilter, scopedUnits, unityReport, isChiefService]);

  const handleExport = async (type: Parameters<typeof downloadReport>[0], fmt?: ExportFormat) => {
    if (type === "by-unity" && !directionFilter && !isChiefService) {
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
        if (directionFilter && !isChiefService) params.direction_id = String(directionFilter);
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
                disabled={!serviceReportReady}
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

      {/* KPIs réels */}
      <div className="grid gap-4 sm:grid-cols-2">
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

    </div>
  );
}
