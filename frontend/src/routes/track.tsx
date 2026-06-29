import { createFileRoute, Link } from "@tanstack/react-router";
import { useState } from "react";
import { PublicLayout } from "@/components/public-layout";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { StatusBadge, PriorityBadge } from "@/components/status-badge";
import type { RequestStatus, Appreciation } from "@/lib/mock-data";
import {
  EscalationProgressBar,
} from "@/components/escalation-progress-bar";
import { CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { AppreciationForm } from "@/components/appreciation-form";
import { trackRequest } from "@/lib/api/requests";
import { submitAppreciation, updateRequestAppreciation } from "@/lib/api/csat";
import type { RequestItem } from "@/lib/mock-data";

export const Route = createFileRoute("/track")({
  head: () => ({
    meta: [
      { title: "Suivre une demande — EDG Support" },
      { name: "description", content: "Suivez l'avancement de votre demande EDG par numéro." },
    ],
  }),
  component: Track,
});

function externalProgressSteps(status: RequestStatus) {
  const done = (s: boolean) => (s ? "done" as const : "pending" as const);
  const active = (s: boolean) => (s ? "active" as const : "pending" as const);

  const isInProgress = ["assigned", "in_progress", "qualifying", "qualified", "pending", "escalated"].includes(status);
  const isResolved = ["resolved", "closed"].includes(status);

  return [
    { level: "Soumise", status: done(true) },
    { level: "En cours de traitement", status: isResolved ? done(true) : active(isInProgress) },
    { level: "Résolue", status: done(isResolved) },
  ];
}

function Track() {
  const [ref, setRef] = useState("");
  const [credential, setCredential] = useState("");
  const [found, setFound] = useState<RequestItem | null>(null);
  const [appreciation, setAppreciation] = useState<Appreciation | undefined>(undefined);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [notFound, setNotFound] = useState(false);

  const search = async () => {
    const trimmedRef = ref.trim().toUpperCase();
    const trimmedCred = credential.trim();
    if (!trimmedRef || !trimmedCred) return;
    setLoading(true);
    setSearched(false);
    setFound(null);
    setNotFound(false);
    try {
      const result = await trackRequest(trimmedRef, trimmedCred);
      setFound(result);
    } catch {
      setNotFound(true);
      toast.error("Aucune demande trouvée pour ces coordonnées.");
    } finally {
      setSearched(true);
      setLoading(false);
    }
  };

  const isExternal = found?.requesterType === "external" || (found && found.isExternal && !found.requesterType);

  return (
    <PublicLayout>
      <section className="mx-auto max-w-3xl px-4 py-12 sm:px-6 sm:py-20">
        <div className="text-center">
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Suivre votre demande
          </h1>
          <p className="mt-2 text-muted-foreground">
            Saisissez votre numéro de suivi pour consulter l'état d'avancement.
          </p>
        </div>

        <GlassCard strong className="mt-8 p-6 sm:p-8">
          <div className="grid gap-4 sm:grid-cols-[1fr_1fr_auto]">
            <div>
              <Label>Numéro de demande</Label>
              <Input
                className="mt-1.5 h-12 font-mono"
                placeholder="EDG-2026-XXXX"
                value={ref}
                onChange={(e) => setRef(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
              />
            </div>
            <div>
              <Label>Email ou téléphone associé</Label>
              <Input
                className="mt-1.5 h-12"
                placeholder="email@edg.gn ou +224…"
                value={credential}
                onChange={(e) => setCredential(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()}
              />
              <p className="mt-1.5 text-[11px] text-muted-foreground">
                Coordonnées liées au compte ayant soumis cette demande.
              </p>
            </div>
            <div className="flex items-end pb-[22px]">
              <Button
                onClick={search}
                disabled={loading || !ref.trim() || !credential.trim()}
                className="h-12 w-full rounded-full gradient-primary sm:w-auto"
              >
                {loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Rechercher
              </Button>
            </div>
          </div>
        </GlassCard>

        {searched && notFound && (
          <GlassCard className="mt-6 text-center">
            <p className="text-muted-foreground">
              Aucune demande trouvée pour ce numéro.
            </p>
          </GlassCard>
        )}

        {found && (
          <GlassCard className="mt-6 space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="font-mono text-sm text-muted-foreground">{found.ref}</div>
                <h2 className="mt-1 text-xl font-semibold">{found.title}</h2>
                <div className="mt-2 flex flex-wrap gap-2">
                  <StatusBadge status={found.status} />
                  <PriorityBadge priority={found.priority} />
                </div>
              </div>
            </div>

            <p className="text-sm text-muted-foreground">{found.description}</p>

            {isExternal && (
              <>
                <div>
                  <h3 className="mb-3 text-sm font-semibold">Avancement de votre demande</h3>
                  <EscalationProgressBar
                    steps={externalProgressSteps(found.status)}
                  />
                  <p className="mt-3 text-xs text-muted-foreground">
                    Pour des raisons de confidentialité, les informations sur le traitement
                    interne ne sont pas communiquées. Un agent vous contactera si nécessaire.
                  </p>
                </div>

                {found.comments.filter((c) => c.isPublic).length > 0 && (
                  <div>
                    <h3 className="mb-3 text-sm font-semibold">Mises à jour</h3>
                    <div className="space-y-2">
                      {found.comments
                        .filter((c) => c.isPublic)
                        .map((c) => (
                          <div
                            key={c.id}
                            className="rounded-2xl border border-border/50 bg-background/60 p-4"
                          >
                            <div className="text-sm">{c.body}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              Équipe EDG · {new Date(c.createdAt).toLocaleString("fr-FR")}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {!isExternal && (
              <>
                <div>
                  <h3 className="mb-3 text-sm font-semibold">Historique</h3>
                  <ol className="space-y-3 border-l border-border pl-4">
                    {found.timeline.map((t) => (
                      <li key={t.id} className="relative">
                        <span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full bg-primary ring-4 ring-primary/15" />
                        <div className="text-sm font-medium">{t.label}</div>
                        <div className="text-xs text-muted-foreground">
                          {new Date(t.at).toLocaleString("fr-FR")}
                          {t.by && ` · ${t.by}`}
                        </div>
                      </li>
                    ))}
                  </ol>
                </div>

                {found.comments.filter((c) => c.isPublic).length > 0 && (
                  <div>
                    <h3 className="mb-3 text-sm font-semibold">Mises à jour</h3>
                    <div className="space-y-2">
                      {found.comments
                        .filter((c) => c.isPublic)
                        .map((c) => (
                          <div
                            key={c.id}
                            className="rounded-2xl border border-border/50 bg-background/60 p-4"
                          >
                            <div className="text-sm">{c.body}</div>
                            <div className="mt-1 text-xs text-muted-foreground">
                              {c.author} · {new Date(c.createdAt).toLocaleString("fr-FR")}
                            </div>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </>
            )}

            {(found.status === "resolved" || found.status === "closed") && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-success" />
                  <span className="font-semibold text-success">Demande résolue</span>
                </div>
                <AppreciationForm
                  requestId={found.id}
                  authorType="external"
                  existing={appreciation ?? found.appreciation}
                  isClosed={found.status === "closed"}
                  onSubmit={(appr) => setAppreciation(appr)}
                  onReopen={() => {
                    setFound({ ...found, status: "reopened" });
                    toast.info("Demande réouverte. Un agent vous contactera prochainement.");
                  }}
                  onSave={async (data) => {
                    const hasExisting = !!(appreciation ?? found.appreciation);
                    if (hasExisting) {
                      await updateRequestAppreciation(found.id, data);
                    } else {
                      await submitAppreciation(found.id, { ...data, authorType: "external" });
                    }
                  }}
                />
              </div>
            )}

            <div className="flex justify-end">
              <Button asChild variant="outline" className="rounded-full">
                <Link to="/login">Se connecter pour interagir</Link>
              </Button>
            </div>
          </GlassCard>
        )}
      </section>
    </PublicLayout>
  );
}
