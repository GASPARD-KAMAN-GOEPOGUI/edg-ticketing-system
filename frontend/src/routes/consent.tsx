import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Logo } from "@/components/logo";
import { useState } from "react";
import { Loader2, ShieldCheck } from "lucide-react";
import { acceptConsent } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import {
  getPendingConsent,
  clearPendingConsent,
  setUser,
  setTokens,
  getDefaultRouteForRole,
} from "@/lib/session";
import { usePhoneInput } from "@/hooks/use-phone-input";
import type { Role } from "@/lib/mock-data";

export const Route = createFileRoute("/consent")({
  // SSR désactivé : le consentement en attente vit en sessionStorage, invisible
  // côté serveur (même raison que login.tsx/app.tsx).
  ssr: false,
  head: () => ({ meta: [{ title: "Rattachement de votre compte — EDG Support" }] }),
  beforeLoad: () => {
    if (typeof window !== "undefined" && !getPendingConsent()) {
      // Accès direct à /consent sans passer par un login ayant renvoyé
      // needs_consent — rien à faire ici.
      throw redirect({ to: "/login" });
    }
  },
  component: ConsentScreen,
});

function ConsentScreen() {
  const navigate = useNavigate();
  const pending = getPendingConsent();

  const [name, setName] = useState(pending?.suggestedName ?? "");
  const [firstname, setFirstname] = useState(pending?.suggestedFirstname ?? "");
  const phoneInput = usePhoneInput(pending?.suggestedPhone);
  const [accepted, setAccepted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!pending) return null; // redirigé par beforeLoad — évite un flash de formulaire

  const canSubmit = name.trim().length > 0 && !phoneInput.hasError && accepted;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canSubmit || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await acceptConsent({
        accessToken: pending.accessToken,
        refreshToken: pending.refreshToken,
        expiresIn: pending.expiresIn,
        consentVersion: pending.consentVersion,
        name: name.trim(),
        firstname: firstname.trim() || undefined,
        phone: phoneInput.value || undefined,
      });

      clearPendingConsent();
      setTokens(result.accessToken, result.refreshToken, result.expiresIn);
      const role = (result.user.role as Role) || "user";
      setUser({
        id: result.user.id,
        name: result.user.name,
        firstname: result.user.firstname ?? undefined,
        email: result.user.email,
        role,
        phone: result.user.phone,
        avatar: result.user.avatar,
        unit_id: result.user.unit_id ?? undefined,
      });

      navigate({ to: getDefaultRouteForRole(role) as "/", replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError("Votre session a expiré. Reconnectez-vous pour recommencer.");
        } else if (err.status === 422) {
          setError(err.message || "Données invalides. Vérifiez les informations saisies.");
        } else {
          setError(err.message || "Une erreur est survenue. Réessayez.");
        }
      } else {
        setError("Échec de connexion. Veuillez réessayer.");
      }
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-8 flex flex-col items-center gap-3">
          <Link to="/" aria-label="Retour à l'accueil">
            <Logo size="xl" showText={false} />
          </Link>
          <div className="text-center">
            <p className="text-lg font-bold tracking-tight">
              EDG<span className="text-primary">-SUP</span>
            </p>
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground/70">
              EDG Support
            </p>
          </div>
        </div>

        <GlassCard strong className="p-8">
          <div className="mb-5 flex items-start gap-3">
            <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
              <ShieldCheck className="h-5 w-5 text-primary" strokeWidth={1.5} />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">Bienvenue sur EDG Support</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                Votre identité a été vérifiée par la plateforme centrale EDG. Pour accéder à cette
                application, complétez votre profil et acceptez les conditions d'utilisation.
              </p>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label>Email (vérifié par la plateforme centrale)</Label>
              <Input value={pending.email} disabled className="mt-1.5 h-12 bg-muted/50" />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <Label htmlFor="name">Nom</Label>
                <Input
                  id="name"
                  value={name}
                  disabled
                  placeholder="Diallo"
                  className="mt-1.5 h-12 bg-muted/50"
                  required
                  autoComplete="family-name"
                />
              </div>
              <div>
                <Label htmlFor="firstname">Prénom</Label>
                <Input
                  id="firstname"
                  value={firstname}
                  disabled
                  placeholder="Mamadou"
                  className="mt-1.5 h-12 bg-muted/50"
                  autoComplete="given-name"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="phone">Téléphone (optionnel)</Label>
              <Input
                id="phone"
                type="tel"
                inputMode="tel"
                value={phoneInput.display}
                disabled
                placeholder="+224 6XX XX XX XX"
                className="mt-1.5 h-12 bg-muted/50"
                autoComplete="tel"
              />
              <p className="mt-1.5 text-xs text-muted-foreground">
                Informations utilisées : identité, email, téléphone et données nécessaires au
                fonctionnement de votre compte.
              </p>
            </div>

            <div className="flex items-start gap-2.5 rounded-xl border border-border/60 bg-muted/30 px-3.5 py-3">
              <Checkbox
                id="accept-terms"
                checked={accepted}
                onCheckedChange={(v) => {
                  setAccepted(v === true);
                  setError(null);
                }}
                className="mt-0.5"
              />
              <Label
                htmlFor="accept-terms"
                className="cursor-pointer text-xs font-normal leading-relaxed text-muted-foreground"
              >
                J'ai lu et j'accepte les{" "}
                <Link
                  to="/legal/terms"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary hover:underline"
                >
                  conditions d'utilisation
                </Link>{" "}
                et la{" "}
                <Link
                  to="/legal/privacy"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="font-medium text-primary hover:underline"
                >
                  politique de confidentialité
                </Link>{" "}
                d'EDG Support.
              </Label>
            </div>

            {error && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={!canSubmit || isLoading}
              className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
            >
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Rattachement en cours…
                </>
              ) : (
                "Accepter et continuer"
              )}
            </Button>
          </form>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/login" onClick={() => clearPendingConsent()} className="hover:underline">
            Annuler et revenir à la connexion
          </Link>
        </p>
      </div>
    </div>
  );
}
