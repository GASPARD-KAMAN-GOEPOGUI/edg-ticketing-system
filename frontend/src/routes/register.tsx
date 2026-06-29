import { createFileRoute, Link, useNavigate, useRouter } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useState } from "react";
import { ArrowLeft, ArrowRight, CheckCircle2, Eye, EyeOff, Loader2 } from "lucide-react";
import { registerUser } from "@/lib/api/auth";
import { ApiError } from "@/lib/api/client";

export const Route = createFileRoute("/register")({
  head: () => ({ meta: [{ title: "Inscription — EDG Support" }] }),
  component: Register,
});

function PasswordInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  placeholder?: string;
  className?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <Input
        type={visible ? "text" : "password"}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        className={className + " pr-11"}
      />
      <button
        type="button"
        onClick={() => setVisible((v) => !v)}
        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
        aria-label={visible ? "Masquer le mot de passe" : "Afficher le mot de passe"}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  );
}

function Register() {
  const [step, setStep] = useState(1);
  const navigate = useNavigate();
  const router = useRouter();

  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    phone: "",
    password: "",
    confirmPassword: "",
  });

  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm({ ...form, [k]: e.target.value });

  const passwordMismatch =
    form.confirmPassword.length > 0 && form.password !== form.confirmPassword;
  const passwordTooShort = form.password.length > 0 && form.password.length < 8;
  const canContinue =
    !!form.firstName &&
    !!form.email &&
    form.password.length >= 8 &&
    form.password === form.confirmPassword;

  const handleRegister = async () => {
    setIsLoading(true);
    setApiError(null);
    try {
      const lastName = form.lastName.trim();
      const firstName = form.firstName.trim();
      await registerUser({
        name: lastName || firstName,         // nom de famille (obligatoire en base)
        firstname: lastName ? firstName : undefined, // prénom uniquement si nom fourni
        email: form.email.trim(),
        phone: form.phone.trim() || undefined,
        password: form.password,
      });
      // Ne pas stocker la session — l'utilisateur doit se connecter explicitement
      setStep(3);
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 409) {
          setApiError("Cette adresse email est déjà utilisée. Essayez de vous connecter.");
        } else if (err.status === 422) {
          setApiError("Données invalides. Vérifiez les informations saisies.");
        } else {
          setApiError(err.message || "Une erreur est survenue. Réessayez.");
        }
      } else {
        setApiError("Impossible de contacter le serveur. Vérifiez votre connexion.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-between">
          <button
            onClick={() => router.history.back()}
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-foreground/8 hover:text-foreground"
            aria-label="Retour"
          >
            <ArrowLeft className="h-4 w-4" />
            Retour
          </button>
          <Link to="/" aria-label="Retour à l'accueil">
            <Logo size="lg" />
          </Link>
          <div className="w-20" />
        </div>

        <GlassCard strong className="p-8">
          <h1 className="text-2xl font-bold tracking-tight">Créer un compte</h1>
          <p className="mt-1 text-sm text-muted-foreground">Étape {step} sur 3</p>
          <div className="mt-4 flex gap-1.5">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className={"h-1.5 flex-1 rounded-full transition-colors " + (step >= i ? "bg-primary" : "bg-muted")}
              />
            ))}
          </div>

          {/* ── Étape 1 : Informations ── */}
          {step === 1 && (
            <div className="mt-6 space-y-4 animate-fade-in">
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <Label>Prénom <span className="text-destructive">*</span></Label>
                  <Input className="mt-1.5 h-12" placeholder="Votre prénom" value={form.firstName} onChange={set("firstName")} />
                </div>
                <div>
                  <Label>Nom</Label>
                  <Input className="mt-1.5 h-12" placeholder="Votre nom" value={form.lastName} onChange={set("lastName")} />
                </div>
              </div>

              <div>
                <Label>Email <span className="text-destructive">*</span></Label>
                <Input className="mt-1.5 h-12" type="email" placeholder="vous@example.com" value={form.email} onChange={set("email")} />
              </div>

              <div>
                <Label>Téléphone</Label>
                <Input className="mt-1.5 h-12" placeholder="+224 6XX XX XX XX" value={form.phone} onChange={set("phone")} />
              </div>

              <div>
                <Label>Mot de passe <span className="text-destructive">*</span></Label>
                <PasswordInput
                  className="mt-1.5 h-12"
                  placeholder="Minimum 8 caractères"
                  value={form.password}
                  onChange={set("password")}
                />
                {passwordTooShort && (
                  <p className="mt-1.5 text-xs text-destructive">
                    Le mot de passe doit contenir au moins 8 caractères.
                  </p>
                )}
              </div>

              <div>
                <Label>Confirmer le mot de passe <span className="text-destructive">*</span></Label>
                <PasswordInput
                  className="mt-1.5 h-12"
                  placeholder="Répétez votre mot de passe"
                  value={form.confirmPassword}
                  onChange={set("confirmPassword")}
                />
                {passwordMismatch && (
                  <p className="mt-1.5 text-xs text-destructive">
                    Les mots de passe ne correspondent pas.
                  </p>
                )}
                {!passwordMismatch && form.confirmPassword.length > 0 && form.password === form.confirmPassword && (
                  <p className="mt-1.5 flex items-center gap-1 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Mots de passe identiques
                  </p>
                )}
              </div>

              <Button
                onClick={() => setStep(2)}
                className="h-12 w-full rounded-full gradient-primary"
                disabled={!canContinue}
              >
                Continuer <ArrowRight className="ml-1 h-4 w-4" />
              </Button>

              <p className="text-center text-xs text-muted-foreground">
                Déjà un compte ?{" "}
                <Link to="/login" className="font-medium text-primary hover:underline">
                  Se connecter
                </Link>
              </p>
            </div>
          )}

          {/* ── Étape 2 : Résumé + envoi API ── */}
          {step === 2 && (
            <div className="mt-6 space-y-5 animate-fade-in">
              <h3 className="font-semibold">Vérifiez vos informations</h3>
              <dl className="space-y-2 rounded-2xl border border-border/50 bg-background/50 p-4 text-sm">
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Nom complet</dt>
                  <dd>{form.firstName} {form.lastName}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Email</dt>
                  <dd className="truncate">{form.email}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Téléphone</dt>
                  <dd>{form.phone || "—"}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Mot de passe</dt>
                  <dd className="tracking-widest">••••••••</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-muted-foreground">Rôle attribué</dt>
                  <dd className="font-medium">Simple utilisateur</dd>
                </div>
              </dl>

              <p className="text-xs text-muted-foreground">
                Seul un administrateur EDG peut faire évoluer votre rôle après inscription.
              </p>

              {/* Message d'erreur API */}
              {apiError && (
                <div className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
                  {apiError}
                </div>
              )}

              <div className="flex gap-2">
                <Button variant="ghost" onClick={() => { setStep(1); setApiError(null); }} disabled={isLoading}>
                  <ArrowLeft className="mr-1 h-4 w-4" /> Retour
                </Button>
                <Button
                  className="ml-auto h-12 rounded-full gradient-primary"
                  onClick={handleRegister}
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Création en cours…
                    </>
                  ) : (
                    "Valider mon inscription"
                  )}
                </Button>
              </div>
            </div>
          )}

          {/* ── Étape 3 : Confirmation ── */}
          {step === 3 && (
            <div className="mt-6 space-y-5 text-center animate-fade-in">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-success/15">
                <CheckCircle2 className="h-8 w-8 text-success" />
              </div>
              <div>
                <h2 className="text-xl font-semibold">
                  Compte créé, {form.firstName} !
                </h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  Votre compte a bien été créé. Connectez-vous pour accéder à votre espace.
                </p>
              </div>
              <Button
                onClick={() => navigate({ to: "/login" })}
                className="h-12 w-full rounded-full gradient-primary"
              >
                Se connecter
              </Button>
            </div>
          )}
        </GlassCard>
      </div>
    </div>
  );
}
