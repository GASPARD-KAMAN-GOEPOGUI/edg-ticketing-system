import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useState, useEffect, useRef } from "react";
import { ArrowLeft, CheckCircle2, Eye, EyeOff, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { apiFetch, ApiError } from "@/lib/api/client";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({ meta: [{ title: "Mot de passe oublié — EDG Support" }] }),
  component: ForgotPassword,
});

function PasswordInput({
  id,
  value,
  onChange,
  placeholder,
}: {
  id?: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        id={id}
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className="mt-1.5 h-12 pr-11"
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
        aria-label={visible ? "Masquer" : "Afficher"}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

function useCountdown(seconds: number) {
  const [remaining, setRemaining] = useState(0);
  const ref = useRef<ReturnType<typeof setInterval> | null>(null);

  const start = () => {
    setRemaining(seconds);
    if (ref.current) clearInterval(ref.current);
    ref.current = setInterval(() => {
      setRemaining((p) => {
        if (p <= 1) { clearInterval(ref.current!); return 0; }
        return p - 1;
      });
    }, 1000);
  };

  useEffect(() => () => { if (ref.current) clearInterval(ref.current); }, []);
  return { remaining, start, done: remaining === 0 };
}

function ForgotPassword() {
  const navigate = useNavigate();

  // step: 1=email, 2=code, 3=nouveau mdp, 4=succès
  const [step, setStep] = useState(1);

  // Step 1
  const [email, setEmail] = useState("");
  const [sendLoading, setSendLoading] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  // Step 2 — code reçu (pré-rempli en mode dev)
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const countdown = useCountdown(180);

  // Step 3
  const [newPwd, setNewPwd] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);

  const pwdMismatch = confirmPwd.length > 0 && newPwd !== confirmPwd;
  const pwdValid = newPwd.length >= 6 && newPwd === confirmPwd;

  // ── Step 1 : demander le code ──────────────────────────────────────────────
  const sendCode = async () => {
    setSendLoading(true);
    setSendError(null);
    try {
      const res = await apiFetch<{ sent: boolean; dev_code?: string }>(
        "/auth/forgot-password",
        { method: "POST", body: JSON.stringify({ email: email.trim() }) },
      );
      const prefill = res?.dev_code ?? null;
      setDevCode(prefill);
      setCode(prefill ?? "");
      countdown.start();
      setStep(2);
    } catch (err) {
      if (err instanceof ApiError && err.status === 422) {
        setSendError("Adresse email invalide.");
      } else if (err instanceof ApiError) {
        setSendError(err.message || "Une erreur est survenue.");
      } else {
        setSendError("Impossible de contacter le serveur. Vérifiez votre connexion.");
      }
    } finally {
      setSendLoading(false);
    }
  };

  const resendCode = async () => {
    setCode("");
    setDevCode(null);
    await sendCode();
  };

  // ── Step 3 : réinitialiser le mot de passe ────────────────────────────────
  const resetPassword = async () => {
    setResetLoading(true);
    setResetError(null);
    try {
      await apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({
          email: email.trim(),
          code: code.trim(),
          new_password: newPwd,
        }),
      });
      setStep(4);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.errorCode === "RESET_CODE_EXPIRED") {
          setResetError("Ce code a expiré. Retournez à l'étape précédente pour en demander un nouveau.");
        } else if (err.errorCode === "RESET_CODE_INVALID") {
          setResetError("Code invalide ou déjà utilisé. Vérifiez le code saisi.");
        } else if (err.status === 422) {
          setResetError("Le mot de passe doit contenir au moins 6 caractères.");
        } else {
          setResetError(err.message || "Une erreur est survenue.");
        }
      } else {
        setResetError("Impossible de contacter le serveur. Vérifiez votre connexion.");
      }
    } finally {
      setResetLoading(false);
    }
  };

  const isSuccess = step === 4;
  const displayStep = Math.min(step, 3);

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between">
          <Button asChild size="sm" className="rounded-full bg-primary text-background hover:bg-primary/90 shadow-sm">
            <Link to="/login">
              <ArrowLeft className="mr-1.5 h-3.5 w-3.5" />
              Retour à la connexion
            </Link>
          </Button>
          <Link to="/" aria-label="Retour à l'accueil"><Logo size="lg" showText={false} /></Link>
          <div className="w-36" />
        </div>

        <GlassCard strong className="p-8">
          {!isSuccess && (
            <>
              <h1 className="text-2xl font-bold tracking-tight">Mot de passe oublié</h1>
              <p className="mt-1 text-sm text-muted-foreground">Étape {displayStep} sur 3</p>
              <div className="mt-4 flex gap-1.5">
                {[1, 2, 3].map((i) => (
                  <div
                    key={i}
                    className={cn("h-1.5 flex-1 rounded-full transition-colors",
                      displayStep >= i ? "bg-primary" : "bg-muted")}
                  />
                ))}
              </div>
            </>
          )}

          {/* ── Étape 1 : email ── */}
          {step === 1 && (
            <div className="mt-6 space-y-5 animate-fade-in">
              <p className="text-sm text-muted-foreground">
                Saisissez l'adresse email associée à votre compte.
                Nous vous enverrons un code de vérification.
              </p>
              <div>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setSendError(null); }}
                  placeholder="vous@edg.gn"
                  className="mt-1.5 h-12"
                  autoComplete="email"
                  onKeyDown={(e) => e.key === "Enter" && email.trim().length > 3 && !sendLoading && sendCode()}
                />
              </div>

              {sendError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                  {sendError}
                </div>
              )}

              <Button
                className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                disabled={email.trim().length < 5 || sendLoading}
                onClick={sendCode}
              >
                {sendLoading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Envoi en cours…</>
                ) : "Envoyer le code"}
              </Button>
            </div>
          )}

          {/* ── Étape 2 : code ── */}
          {step === 2 && (
            <div className="mt-6 space-y-5 animate-fade-in">
              <p className="text-sm text-muted-foreground">
                Entrez le code à 6 chiffres envoyé à{" "}
                <span className="font-medium text-foreground">{email}</span>.
              </p>

              {/* Bandeau dev : code affiché directement */}
              {devCode && (
                <div className="rounded-xl border border-primary/30 bg-primary/8 px-4 py-3 text-sm">
                  <span className="font-medium text-primary">Mode développement</span>
                  <span className="text-muted-foreground"> — email non envoyé. Code : </span>
                  <span className="font-mono font-bold tracking-widest text-primary">{devCode}</span>
                </div>
              )}

              <div>
                <Label htmlFor="code">Code de vérification</Label>
                <Input
                  id="code"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                  inputMode="numeric"
                  placeholder="— — — — — —"
                  maxLength={6}
                  className="mt-1.5 h-12 text-center tracking-[0.4em] font-mono text-lg"
                  autoComplete="one-time-code"
                />
              </div>

              <Button
                className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                disabled={code.length < 6}
                onClick={() => setStep(3)}
              >
                Vérifier
              </Button>

              <div className="flex items-center justify-between text-sm">
                <button
                  type="button"
                  disabled={!countdown.done}
                  onClick={resendCode}
                  className={cn(
                    "flex items-center gap-1.5 font-medium transition-colors",
                    countdown.done
                      ? "text-primary hover:underline cursor-pointer"
                      : "text-muted-foreground cursor-not-allowed",
                  )}
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {countdown.done ? "Renvoyer le code" : `Renvoyer dans ${countdown.remaining} s`}
                </button>
                <button
                  type="button"
                  onClick={() => { setStep(1); setCode(""); setDevCode(null); }}
                  className="text-muted-foreground hover:text-foreground hover:underline"
                >
                  Changer d'email
                </button>
              </div>
            </div>
          )}

          {/* ── Étape 3 : nouveau mot de passe ── */}
          {step === 3 && (
            <div className="mt-6 space-y-4 animate-fade-in">
              <p className="text-sm text-muted-foreground">
                Choisissez un nouveau mot de passe (6 caractères minimum).
              </p>

              <div>
                <Label htmlFor="newPwd">Nouveau mot de passe</Label>
                <PasswordInput
                  id="newPwd"
                  value={newPwd}
                  onChange={(e) => { setNewPwd(e.target.value); setResetError(null); }}
                  placeholder="6 caractères minimum"
                />
                {newPwd.length > 0 && newPwd.length < 6 && (
                  <p className="mt-1.5 text-xs text-destructive">
                    Le mot de passe doit contenir au moins 6 caractères.
                  </p>
                )}
              </div>

              <div>
                <Label htmlFor="confirmPwd">Confirmer le mot de passe</Label>
                <PasswordInput
                  id="confirmPwd"
                  value={confirmPwd}
                  onChange={(e) => setConfirmPwd(e.target.value)}
                  placeholder="Répétez le nouveau mot de passe"
                />
                {pwdMismatch && (
                  <p className="mt-1.5 text-xs text-destructive">
                    Les mots de passe ne correspondent pas.
                  </p>
                )}
                {!pwdMismatch && confirmPwd.length > 0 && newPwd === confirmPwd && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Mots de passe identiques
                  </p>
                )}
              </div>

              {resetError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                  {resetError}
                  {resetError.includes("précédente") && (
                    <button
                      type="button"
                      onClick={() => { setStep(2); setCode(""); setDevCode(null); setResetError(null); }}
                      className="mt-1 block font-medium underline"
                    >
                      Redemander un code
                    </button>
                  )}
                </div>
              )}

              <Button
                className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                disabled={!pwdValid || resetLoading}
                onClick={resetPassword}
              >
                {resetLoading ? (
                  <><Loader2 className="mr-2 h-4 w-4 animate-spin" />Réinitialisation…</>
                ) : "Réinitialiser le mot de passe"}
              </Button>
            </div>
          )}

          {/* ── Succès ── */}
          {step === 4 && (
            <div className="space-y-5 text-center animate-fade-in">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success/15">
                <CheckCircle2 className="h-8 w-8 text-success" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">Mot de passe mis à jour !</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Votre mot de passe a été réinitialisé avec succès.
                  Connectez-vous avec votre nouveau mot de passe.
                </p>
              </div>
              <Button
                className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                onClick={() => navigate({ to: "/login" })}
              >
                Aller à la connexion
              </Button>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
