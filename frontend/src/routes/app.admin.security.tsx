import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSecurityIncidents,
  resolveIncident,
  deleteIncident,
  type SecurityIncident,
} from "@/lib/api/securityIncidents";
import { getAccessToken } from "@/lib/session";
import { _BACKEND_ORIGIN } from "@/lib/api/accounts";
import {
  ShieldX,
  Camera,
  CheckCircle2,
  Clock,
  RefreshCw,
  Trash2,
  Eye,
  MapPin,
  Monitor,
  Mail,
  AlertTriangle,
  Globe,
  Cpu,
  Smartphone,
  Hash,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { PaginationBar } from "@/components/pagination-bar";

export const Route = createFileRoute("/app/admin/security")({
  head: () => ({ meta: [{ title: "Incidents sécurité — Admin EDG" }] }),
  component: SecurityIncidentsPage,
});

function useAuthPhoto(path: string | null): string | null {
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (!path) return;
    let revoked = false;
    const token = getAccessToken();
    fetch(`${_BACKEND_ORIGIN}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.blob())
      .then((blob) => {
        if (!revoked) setSrc(URL.createObjectURL(blob));
      })
      .catch(() => {});
    return () => {
      revoked = true;
      setSrc((prev) => { if (prev) URL.revokeObjectURL(prev); return null; });
    };
  }, [path]);
  return src;
}

function fmtDate(iso: string | null) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function IncidentPhoto({ path }: { path: string | null }) {
  const [open, setOpen] = useState(false);
  const src = useAuthPhoto(path);

  if (!path || !src) {
    return (
      <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground">
        <Camera className="h-6 w-6 opacity-40" />
      </div>
    );
  }
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="group relative h-16 w-16 shrink-0 overflow-hidden rounded-lg border border-border/50 bg-muted"
        title="Agrandir la photo"
      >
        <img
          src={src}
          alt="Photo de la tentative"
          className="h-full w-full object-cover transition-opacity group-hover:opacity-80"
        />
        <span className="absolute inset-0 flex items-center justify-center opacity-0 transition-opacity group-hover:opacity-100">
          <Eye className="h-5 w-5 text-white drop-shadow" />
        </span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Photo capturée</DialogTitle>
          </DialogHeader>
          <img
            src={src}
            alt="Photo de la tentative"
            className="w-full rounded-lg object-contain"
          />
        </DialogContent>
      </Dialog>
    </>
  );
}

function ResolveDialog({
  incident,
  onClose,
}: {
  incident: SecurityIncident;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [notes, setNotes] = useState(incident.notes ?? "");

  const mutation = useMutation({
    mutationFn: () => resolveIncident(incident.id, notes || undefined),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-incidents"] });
      toast.success("Incident marqué comme résolu");
      onClose();
    },
    onError: () => toast.error("Impossible de résoudre l'incident"),
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Résoudre l'incident</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Identifiant : <span className="font-medium text-foreground">{incident.email_attempted ?? "inconnu"}</span>
        </p>
        <Textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes sur la résolution (optionnel)…"
          rows={3}
        />
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Enregistrement…" : "Marquer résolu"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function DeleteDialog({
  incident,
  onClose,
}: {
  incident: SecurityIncident;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => deleteIncident(incident.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["security-incidents"] });
      toast.success("Incident supprimé");
      onClose();
    },
    onError: () => toast.error("Impossible de supprimer l'incident"),
  });

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Supprimer l'incident</DialogTitle>
        </DialogHeader>
        <p className="text-sm text-muted-foreground">
          Cette action est irréversible. L'incident sera retiré du journal de sécurité.
        </p>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Annuler
          </Button>
          <Button
            variant="destructive"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending ? "Suppression…" : "Supprimer"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function IncidentCard({ incident }: { incident: SecurityIncident }) {
  const [resolving, setResolving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  return (
    <>
      <GlassCard className="flex gap-4">
        <IncidentPhoto path={incident.photo_path} />

        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold",
                incident.resolved
                  ? "bg-success/15 text-success"
                  : "bg-destructive/15 text-destructive",
              )}
            >
              {incident.resolved ? (
                <><CheckCircle2 className="h-3 w-3" /> Résolu</>
              ) : (
                <><AlertTriangle className="h-3 w-3" /> Non résolu</>
              )}
            </span>
            {incident.attempt_count > 1 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2.5 py-0.5 text-xs font-semibold text-amber-600 dark:text-amber-400">
                <Hash className="h-3 w-3" />{incident.attempt_count} tentatives
              </span>
            )}
            <span className="text-xs text-muted-foreground">
              <Clock className="mr-1 inline h-3 w-3" />
              {fmtDate(incident.occurred_at ?? incident.created_at)}
            </span>
          </div>

          <div className="grid gap-1 sm:grid-cols-2 text-sm">
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <Mail className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{incident.email_attempted ?? "—"}</span>
            </div>
            <div className="flex items-center gap-1.5 text-muted-foreground">
              <MapPin className="h-3.5 w-3.5 shrink-0" />
              <span>{incident.ip_address ?? "—"}</span>
            </div>
            {incident.browser && (
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Globe className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{incident.browser}</span>
              </div>
            )}
            {incident.os_info && (
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Cpu className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{incident.os_info}</span>
              </div>
            )}
            {incident.device_type && (
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <Smartphone className="h-3.5 w-3.5 shrink-0" />
                <span className="capitalize">{incident.device_type}</span>
              </div>
            )}
            {incident.location_approx && (
              <div className="flex items-center gap-1.5 text-muted-foreground">
                <MapPin className="h-3.5 w-3.5 shrink-0 text-amber-500" />
                <span className="truncate">{incident.location_approx}</span>
              </div>
            )}
            <div className="flex items-center gap-1.5 text-muted-foreground col-span-full">
              <Monitor className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate text-xs">{incident.user_agent ?? "—"}</span>
            </div>
          </div>

          {incident.resolved && incident.notes && (
            <p className="rounded-md bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
              <span className="font-medium text-foreground">Note : </span>
              {incident.notes}
            </p>
          )}

          <div className="flex gap-2 pt-1">
            {!incident.resolved && (
              <Button
                size="sm"
                className="rounded-full"
                onClick={() => setResolving(true)}
              >
                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" />
                Résoudre
              </Button>
            )}
            <Button
              size="sm"
              variant="outline"
              className="rounded-full text-destructive hover:text-destructive"
              onClick={() => setDeleting(true)}
            >
              <Trash2 className="mr-1.5 h-3.5 w-3.5" />
              Supprimer
            </Button>
          </div>
        </div>
      </GlassCard>

      {resolving && (
        <ResolveDialog incident={incident} onClose={() => setResolving(false)} />
      )}
      {deleting && (
        <DeleteDialog incident={incident} onClose={() => setDeleting(false)} />
      )}
    </>
  );
}

function SecurityIncidentsPage() {
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<"all" | "unresolved" | "resolved">("all");
  const qc = useQueryClient();

  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ["security-incidents", page],
    queryFn: () => fetchSecurityIncidents({ page, limit: 20 }),
    staleTime: 30_000,
  });

  const allItems = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = data?.pages ?? 1;

  const filtered = allItems.filter((i) => {
    if (filter === "unresolved") return !i.resolved;
    if (filter === "resolved") return i.resolved;
    return true;
  });

  const unresolvedCount = allItems.filter((i) => !i.resolved).length;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center gap-1.5 rounded-full bg-destructive/10 px-3 py-1 text-xs font-medium text-destructive">
            <ShieldX className="h-3 w-3" /> Sécurité
          </div>
          <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">
            Incidents de sécurité
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Tentatives d'accès non autorisées sur l'interface d'administration — photos et métadonnées capturées.
          </p>
        </div>
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
      </header>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <GlassCard>
          <div className="text-sm text-muted-foreground">Total incidents</div>
          <div className="mt-2 text-3xl font-bold">{total}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Non résolus</div>
          <div className="mt-2 text-3xl font-bold text-destructive">{unresolvedCount}</div>
        </GlassCard>
        <GlassCard>
          <div className="text-sm text-muted-foreground">Résolus</div>
          <div className="mt-2 text-3xl font-bold text-success">
            {allItems.filter((i) => i.resolved).length}
          </div>
        </GlassCard>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-1 rounded-xl bg-muted/50 p-1 w-fit">
        {(["all", "unresolved", "resolved"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={cn(
              "rounded-lg px-4 py-1.5 text-sm font-medium transition-colors",
              filter === f
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground",
            )}
          >
            {f === "all" ? "Tous" : f === "unresolved" ? "Non résolus" : "Résolus"}
          </button>
        ))}
      </div>

      {/* List */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-32 animate-pulse rounded-2xl bg-muted/50" />
          ))}
        </div>
      ) : filtered.length === 0 ? (
        <GlassCard className="flex flex-col items-center gap-3 py-16 text-center">
          <ShieldX className="h-10 w-10 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            {filter === "unresolved"
              ? "Aucun incident non résolu. Tout est sous contrôle."
              : "Aucun incident enregistré."}
          </p>
        </GlassCard>
      ) : (
        <div className="space-y-3">
          {filtered.map((incident) => (
            <IncidentCard key={incident.id} incident={incident} />
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <PaginationBar
          page={page}
          totalPages={totalPages}
          total={total}
          pageSize={20}
          onChange={setPage}
        />
      )}
    </div>
  );
}
