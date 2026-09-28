import { createFileRoute, Link, redirect, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useState } from "react";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { loginUser } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { setUser, setTokens, clearSession, getDefaultRouteForRole, isAuthenticated, getRole, setPendingConsent } from "@/lib/session";
import type { Role } from "@/lib/mock-data";

export const Route = createFileRoute("/login")({
  // SSR désactivé : isAuthenticated() lit localStorage, invisible côté serveur
  // (voir app.tsx). Sans ce flag, un utilisateur déjà connecté qui rouvrait
  // /login directement pouvait rester bloqué sur le formulaire au lieu d'être
  // redirigé vers son espace.
  ssr: false,
  head: () => ({ meta: [{ title: "Connexion — EDG Support" }] }),
  beforeLoad: () => {
    if (isAuthenticated()) {
      throw redirect({ to: getDefaultRouteForRole(getRole()) as "/" });
    }
  },
  component: Login,
});

function Login() {
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canSubmit = identifier.trim().length > 0 && password.length > 0;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canSubmit || isLoading) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await loginUser({ identifier: identifier.trim(), password });

      if (result.needsConsent) {
        // Authentifié par le central, mais aucun compte local ni groupe support
        // de cette application — écran de consentement avant tout accès.
        setPendingConsent({
          accessToken: result.accessToken,
          refreshToken: result.refreshToken,
          expiresIn: result.expiresIn,
          email: result.email,
          suggestedName: result.suggestedName,
          suggestedFirstname: result.suggestedFirstname,
          suggestedPhone: result.suggestedPhone,
          consentVersion: result.consentVersion,
        });
        navigate({ to: "/consent", replace: true });
        return;
      }

      clearSession();
      setTokens(result.accessToken, result.refreshToken, result.expiresIn);

      const role = (result.user.role as Role) || "user";
      const directionId = result.user.direction_id ?? undefined;
      setUser({
        id: result.user.id,
        name: result.user.name,
        firstname: result.user.firstname ?? undefined,
        email: result.user.email,
        role,
        phone: result.user.phone,
        avatar: result.user.avatar,
        direction_id: directionId,
        unit_id: result.user.unit_id ?? undefined,
      });

      // isLoading reste true pendant toute la navigation — le composant se démontera,
      // donc pas besoin de le remettre à false sur le chemin succès.
      navigate({ to: getDefaultRouteForRole(role) as "/", replace: true });
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          if (err.errorCode === "ACCOUNT_DISABLED") {
            setError("Ce compte est désactivé. Contactez l'administration EDG.");
          } else {
            setError("Identifiant ou mot de passe incorrect. Vérifiez vos informations.");
          }
        } else if (err.status === 422) {
          setError("Identifiant invalide. Vérifiez l'email ou le numéro saisi.");
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
          <h1 className="text-2xl font-bold tracking-tight">Connexion</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Accédez à votre espace EDG Support.
          </p>

          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <div>
              <Label htmlFor="identifier">Email ou téléphone</Label>
              <Input
                id="identifier"
                type="text"
                placeholder="vous@edg.gn ou +224 6XX XXX XXX"
                value={identifier}
                onChange={(e) => { setIdentifier(e.target.value); setError(null); }}
                className="mt-1.5 h-12"
                required
                autoComplete="username"
                inputMode="text"
              />
            </div>

            <div>
              <div className="flex items-center justify-between">
                <Label htmlFor="password">Mot de passe</Label>
                <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                  Oublié ?
                </Link>
              </div>
              <div className="relative mt-1.5">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Votre mot de passe"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(null); }}
                  className="h-12 pr-11"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
                  aria-label={showPassword ? "Masquer le mot de passe" : "Afficher le mot de passe"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Message d'erreur */}
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
                  Connexion en cours…
                </>
              ) : (
                "Se connecter"
              )}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-muted-foreground">
            Pas encore de compte ?{" "}
            <Link to="/register" className="font-medium text-primary hover:underline">
              Créer un compte
            </Link>
          </p>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/" className="hover:underline">← Retour au portail public</Link>
        </p>

        <p className="sr-only">
          <Link to="/admin-login">Console administrateur</Link>
        </p>
      </div>
    </div>
  );
}
