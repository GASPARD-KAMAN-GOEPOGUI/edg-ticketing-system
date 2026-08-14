import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useState } from "react";
import { Eye, EyeOff, Loader2, ShieldCheck, ShieldAlert, TerminalSquare } from "lucide-react";
import { loginUser } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";
import { setUser, setTokens, clearSession, isAuthenticated, getRole } from "@/lib/session";
import { motion, AnimatePresence } from "framer-motion";
import type { Role } from "@/lib/mock-data";
import { redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/admin-login")({
  // SSR désactivé : voir login.tsx / app.tsx (isAuthenticated() dépend de
  // localStorage, absent côté serveur).
  ssr: false,
  head: () => ({ meta: [{ title: "Console Administrateur — EDG" }] }),
  beforeLoad: () => {
    if (isAuthenticated()) {
      // Admin déjà connecté → son espace admin
      if (getRole() === "admin") throw redirect({ to: "/app/admin/users" });
      // Autre rôle déjà connecté → son espace
      throw redirect({ to: "/app" });
    }
  },
  component: AdminLogin,
});

function AdminLogin() {
  const navigate = useNavigate();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accessGranted, setAccessGranted] = useState(false);

  const canSubmit = identifier.trim().length > 0 && password.length > 0;

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canSubmit || isLoading) return;

    setIsLoading(true);
    setError(null);
    const trimmedId = identifier.trim();

    try {
      const result = await loginUser({ identifier: trimmedId, password });

      if (result.user.role !== "admin") {
        clearSession();
        setError("Accès refusé — Ce compte ne dispose pas des privilèges administrateur système.");
        return;
      }

      setTokens(result.accessToken, result.refreshToken, result.expiresIn);
      setUser({
        id: result.user.id,
        name: result.user.name,
        email: result.user.email,
        role: (result.user.role as Role) || "admin",
        phone: result.user.phone,
        avatar: result.user.avatar,
        direction_id: result.user.direction_id ?? undefined,
        unit_id: result.user.unit_id ?? undefined,
      });

      setAccessGranted(true);
      setTimeout(() => navigate({ to: "/app/admin/users" }), 900);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401 && err.errorCode === "ACCOUNT_DISABLED") {
          setError("Ce compte administrateur est désactivé.");
        } else if (err.status === 401 || err.status === 422) {
          setError(
            err.status === 422
              ? "Identifiant invalide. Vérifiez l'email saisi."
              : "Identifiant ou mot de passe incorrect.",
          );
        } else {
          setError("Erreur de connexion. Vérifiez votre connexion réseau.");
        }
      } else {
        setError("Impossible de contacter le serveur. Vérifiez votre connexion.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        {/* Header */}
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
          <AnimatePresence mode="wait">
            {accessGranted ? (
              <motion.div
                key="granted"
                className="flex flex-col items-center gap-4 py-6"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 22 }}
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 ring-4 ring-primary/20 shadow-lg shadow-primary/20">
                  <ShieldCheck className="h-8 w-8 text-primary" strokeWidth={1.5} />
                </div>
                <div className="text-center">
                  <p className="text-base font-semibold tracking-tight">Accès autorisé</p>
                  <p className="mt-1 text-sm text-muted-foreground">Redirection vers la console…</p>
                </div>
                <div className="flex gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-primary"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                    />
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div key="form" initial={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="mb-6 flex items-start gap-3">
                  <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                    <ShieldAlert className="h-5 w-5 text-primary" strokeWidth={1.5} />
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold tracking-tight">Console Administrateur</h1>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      Accès réservé aux administrateurs système.
                    </p>
                  </div>
                </div>

                <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/8 px-3.5 py-2.5">
                  <TerminalSquare className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <p className="text-xs leading-relaxed text-amber-700 dark:text-amber-400">
                    Zone d&apos;accès restreint — réservée aux comptes disposant du rôle administrateur.
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="identifier">Adresse email administrateur</Label>
                    <Input
                      id="identifier"
                      type="email"
                      placeholder="admin@edg.gn"
                      value={identifier}
                      onChange={(e) => { setIdentifier(e.target.value); setError(null); }}
                      className="mt-1.5 h-12"
                      required
                      autoComplete="username"
                      inputMode="email"
                    />
                  </div>

                  <div>
                    <Label htmlFor="password">Mot de passe</Label>
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
                        aria-label={showPassword ? "Masquer" : "Afficher"}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  <AnimatePresence>
                    {error && (
                      <motion.div
                        className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive"
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                      >
                        {error}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <Button
                    type="submit"
                    disabled={!canSubmit || isLoading}
                    className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Vérification en cours…
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        Accéder à la console
                      </>
                    )}
                  </Button>
                </form>
              </motion.div>
            )}
          </AnimatePresence>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/login" className="hover:underline">← Connexion standard</Link>
          <span className="mx-2 opacity-40">·</span>
          <Link to="/" className="hover:underline">Portail public</Link>
        </p>
      </div>
    </div>
  );
}
