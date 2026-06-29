import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { logCategoryLabels, roleLabels } from "@/lib/mock-data";
import type { Role } from "@/lib/mock-data";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchActivityLogs, searchActivityLogs } from "@/lib/api/activityLogs";
import type { ActivityLogEntry } from "@/lib/api/activityLogs";
import { useRole } from "@/lib/session";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Search,
  XCircle,
  Filter,
  Download,
  Lock,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { PaginationBar } from "@/components/pagination-bar";
import { LayoutToggle, type LayoutMode } from "@/components/layout-toggle";
import { useDebounce } from "@/lib/hooks/use-debounce";

export const Route = createFileRoute("/app/admin/logs")({
  head: () => ({ meta: [{ title: "Journaux d'activité — Admin EDG" }] }),
  component: ActivityLogsPage,
});

const statusIcon = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
} as const;

const statusTone = {
  success: "text-success bg-success/15",
  warning: "text-warning-foreground dark:text-warning bg-warning/20",
  error: "text-destructive bg-destructive/15",
} as const;

function fmtTime(iso: string) {
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function relative(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "à l'instant";
  if (diff < 3600) return `il y a ${Math.round(diff / 60)} min`;
  if (diff < 86400) return `il y a ${Math.round(diff / 3600)} h`;
  return `il y a ${Math.round(diff / 86400)} j`;
}

const LOG_CATEGORIES = Object.keys(logCategoryLabels) as (keyof typeof logCategoryLabels)[];

function ActivityLogsPage() {
  const [role] = useRole();
  const canSeeSensitive = role === "admin" || role === "dg";

  const [q, setQ] = useState("");
  const debouncedQ = useDebounce(q, 400);
  const [categoryFilter, setCategoryFilter] = useState<"all" | string>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | ActivityLogEntry["log_status"]>("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [selected, setSelected] = useState<ActivityLogEntry | null>(null);
  const [layout, setLayout] = useState<LayoutMode>("list");

  // ── Queries ────────────────────────────────────────────────────────────────
  const fetchFn = debouncedQ.trim()
    ? () => searchActivityLogs(debouncedQ.trim(), { page, limit: pageSize })
    : () => fetchActivityLogs({ page, limit: pageSize });

  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["activity-logs", debouncedQ, page, pageSize],
    queryFn: fetchFn,
    staleTime: 30_000,
  });

  const allItems: ActivityLogEntry[] = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  // Client-side filter by category and status (fast, no extra request)
  const filtered = useMemo(() =>
    allItems.filter((l) => {
      const matchCat = categoryFilter === "all" || l.category === categoryFilter;
      const matchSt = statusFilter === "all" || l.log_status === statusFilter;
      return matchCat && matchSt;
    }),
    [allItems, categoryFilter, statusFilter],
  );

  // Stats from current page (lightweight)
  const counts = useMemo(() => ({
    total,
    errors: allItems.filter((l) => l.log_status === "error").length,
    warnings: allItems.filter((l) => l.log_status === "warning").length,
    today: allItems.filter((l) => Date.now() - new Date(l.created_at).getTime() < 86400000).length,
  }), [allItems, total]);

  // Reset to page 1 when query changes
  function handleSearch(value: string) {
    setQ(value);
    setPage(1);
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
            <Activity className="h-3 w-3" /> Audit & sécurité
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Journaux d'activité
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Toutes les actions effectuées sur la plateforme — utilisateurs, système, sécurité.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <LayoutToggle layout={layout} onChange={setLayout} />
          <Button
            variant="outline"
            size="icon"
            className="rounded-full"
            title="Rafraîchir"
            onClick={() => refetch()}
            disabled={isFetching}
          >
            <RefreshCw className={cn("h-4 w-4", isFetching && "animate-spin")} />
          </Button>
          <Button
            variant="outline"
            className="rounded-full"
            onClick={() => toast.success("Export CSV — fonctionnalité à venir.")}
          >
            <Download className="mr-1.5 h-4 w-4" /> Exporter CSV
          </Button>
        </div>
      </header>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        <GlassCard>
          <div className="text-sm text-muted-foreground">Événements (24h)</div>
          <div className="mt-2 text-3xl font-bold">{counts.today}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Erreurs</div>
          <div className="mt-2 text-3xl font-bold text-destructive">{counts.errors}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Alertes</div>
          <div className="mt-2 text-3xl font-bold text-warning">{counts.warnings}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Total enregistré</div>
          <div className="mt-2 text-3xl font-bold">{total}</div>
        </GlassCard>
      </div>

      <GlassCard className="space-y-4 p-4">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={q}
              onChange={(e) => handleSearch(e.target.value)}
              placeholder="Rechercher acteur, action, cible…"
              className="h-10 rounded-full pl-9"
            />
          </div>
          <Filter className="h-4 w-4 shrink-0 text-muted-foreground" />
          <Select value={categoryFilter} onValueChange={(v) => { setCategoryFilter(v); setPage(1); }}>
            <SelectTrigger className="h-10 w-full rounded-full sm:w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Toutes catégories</SelectItem>
              {LOG_CATEGORIES.map((k) => (
                <SelectItem key={k} value={k}>{logCategoryLabels[k]}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => { setStatusFilter(v as typeof statusFilter); setPage(1); }}>
            <SelectTrigger className="h-10 w-full rounded-full sm:w-36">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Tous statuts</SelectItem>
              <SelectItem value="success">Succès</SelectItem>
              <SelectItem value="warning">Alerte</SelectItem>
              <SelectItem value="error">Erreur</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* List / Grid */}
        {isLoading ? (
          <div className="py-12 text-center text-sm text-muted-foreground">Chargement…</div>
        ) : layout === "list" ? (
          <ul className="divide-y divide-border/40">
            {filtered.map((l) => {
              const Icon = statusIcon[l.log_status] ?? CheckCircle2;
              const tone = statusTone[l.log_status] ?? statusTone.success;
              return (
                <li key={l.id}>
                  <button
                    onClick={() => setSelected(l)}
                    className="flex w-full items-center gap-4 rounded-xl px-2 py-3 text-left transition hover:bg-card/50"
                  >
                    <span className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", tone)}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-medium">{l.action}</span>
                        <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                          {logCategoryLabels[l.category as keyof typeof logCategoryLabels] ?? l.category}
                        </span>
                      </div>
                      <div className="mt-0.5 truncate text-xs text-muted-foreground">
                        <span className="font-medium text-foreground/80">{l.actor}</span>
                        {l.target !== "—" && (
                          <> · cible : <span className="font-mono">{l.target}</span></>
                        )}
                        {canSeeSensitive && l.ip_address && <> · IP {l.ip_address}</>}
                      </div>
                    </div>
                    <div className="hidden text-right text-xs text-muted-foreground sm:block">
                      <div>{fmtTime(l.created_at)}</div>
                      <div>{relative(l.created_at)}</div>
                    </div>
                  </button>
                </li>
              );
            })}
            {filtered.length === 0 && (
              <li className="py-12 text-center text-sm text-muted-foreground">
                Aucun événement ne correspond.
              </li>
            )}
          </ul>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((l) => {
              const Icon = statusIcon[l.log_status] ?? CheckCircle2;
              const tone = statusTone[l.log_status] ?? statusTone.success;
              return (
                <GlassCard
                  key={l.id}
                  className="cursor-pointer p-3 transition hover:border-primary/30"
                  onClick={() => setSelected(l)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={cn("grid h-8 w-8 shrink-0 place-items-center rounded-lg", tone)}>
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                      {logCategoryLabels[l.category as keyof typeof logCategoryLabels] ?? l.category}
                    </span>
                  </div>
                  <div className="mt-2 text-sm font-semibold leading-snug">{l.action}</div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    <span className="font-medium text-foreground/80">{l.actor}</span>
                    {l.target !== "—" && <> · {l.target}</>}
                  </div>
                  <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                    <span>{fmtTime(l.created_at)}</span>
                    <span>{relative(l.created_at)}</span>
                  </div>
                </GlassCard>
              );
            })}
            {filtered.length === 0 && (
              <p className="col-span-full py-12 text-center text-sm text-muted-foreground">
                Aucun événement ne correspond.
              </p>
            )}
          </div>
        )}

        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={pageSize}
          onChange={(p) => setPage(p)}
          onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
        />
      </GlassCard>

      {/* Detail sheet */}
      <Sheet open={!!selected} onOpenChange={(o) => !o && setSelected(null)}>
        <SheetContent className="w-full overflow-y-auto sm:max-w-md">
          {selected && (
            <>
              <SheetHeader>
                <div className={cn(
                  "inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium",
                  statusTone[selected.log_status] ?? statusTone.success,
                )}>
                  {selected.log_status.toUpperCase()}
                </div>
                <SheetTitle className="mt-2">{selected.action}</SheetTitle>
                <SheetDescription>
                  {fmtTime(selected.created_at)} · {relative(selected.created_at)}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-4 text-sm">
                <Row
                  k="Acteur"
                  v={`${selected.actor} (${roleLabels[selected.actor_role as Role] ?? selected.actor_role})`}
                />
                <Row
                  k="Catégorie"
                  v={logCategoryLabels[selected.category as keyof typeof logCategoryLabels] ?? selected.category}
                />
                <Row k="Cible" v={selected.target} mono />

                {canSeeSensitive ? (
                  <>
                    {selected.ip_address && <Row k="Adresse IP" v={selected.ip_address} mono />}
                    {selected.user_agent && (
                      <Row k="User-Agent" v={selected.user_agent} mono small />
                    )}
                  </>
                ) : (
                  <div className="flex items-center gap-1.5 rounded-lg bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                    <Lock className="h-3 w-3 shrink-0" />
                    <span>Certaines informations techniques sont réservées à l'administrateur.</span>
                  </div>
                )}

                <Row k="ID événement" v={selected.id} mono />
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}

function Row({ k, v, mono, small }: { k: string; v: string; mono?: boolean; small?: boolean }) {
  return (
    <div>
      <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">{k}</div>
      <div className={cn("mt-1 break-all", mono && "font-mono", small ? "text-xs" : "text-sm")}>{v}</div>
    </div>
  );
}
