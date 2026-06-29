import { createFileRoute, redirect } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useState } from "react";
import { toast } from "sonner";
import {
  Settings2,
  Shield,
  Clock,
  Bell,
  Globe,
  Database,
  CheckCircle2,
  Server,
} from "lucide-react";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/app/admin/settings")({
  beforeLoad: () => { throw redirect({ to: "/app/admin/users" }); },
  component: () => null,
});

// ── Sections de paramètres ────────────────────────────────────────────────────

type SettingSection = {
  id: string;
  label: string;
  icon: typeof Settings2;
  description: string;
};

const sections: SettingSection[] = [
  { id: "general", label: "Général", icon: Globe, description: "Nom de l'application, logo, fuseau horaire" },
  { id: "security", label: "Sécurité", icon: Shield, description: "Durée des sessions, MFA, politique de mots de passe" },
  { id: "notifications", label: "Notifications", icon: Bell, description: "Canaux par défaut, fréquences d'envoi, modèles" },
  { id: "sla", label: "SLA & Délais", icon: Clock, description: "Délais par défaut, alertes d'escalade" },
  { id: "system", label: "Système", icon: Server, description: "API, base de données, cache" },
  { id: "data", label: "Données", icon: Database, description: "Rétention des logs, sauvegardes, exports" },
];

function AdminSettings() {
  const [active, setActive] = useState("general");

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <header>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <Settings2 className="h-3 w-3" /> Administration
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Paramètres système</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Configuration globale de la plateforme EDG Support.
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-[240px_1fr]">
        {/* Sidebar navigation */}
        <aside className="space-y-1">
          {sections.map((s) => {
            const Icon = s.icon;
            return (
              <button
                key={s.id}
                onClick={() => setActive(s.id)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm transition",
                  active === s.id
                    ? "gradient-primary text-primary-foreground shadow"
                    : "hover:bg-card/60 text-foreground/70",
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                <span className="font-medium">{s.label}</span>
              </button>
            );
          })}
        </aside>

        {/* Panel */}
        <div>
          {active === "general" && <GeneralSettings />}
          {active === "security" && <SecuritySettings />}
          {active === "notifications" && <NotificationSettings />}
          {active === "sla" && <SlaSettings />}
          {active === "system" && <SystemInfo />}
          {active === "data" && <DataSettings />}
        </div>
      </div>
    </div>
  );
}

// ── Panneau Général ───────────────────────────────────────────────────────────

function GeneralSettings() {
  const [appName, setAppName] = useState("EDG Support");
  const [timezone, setTimezone] = useState("Africa/Conakry");
  const [lang, setLang] = useState("fr");

  return (
    <GlassCard className="space-y-6 p-6">
      <SectionTitle icon={Globe} title="Paramètres généraux" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Nom de l'application" value={appName} onChange={setAppName} />
        <Field label="Fuseau horaire" value={timezone} onChange={setTimezone} />
        <Field label="Langue par défaut" value={lang} onChange={setLang} />
      </div>
      <SaveButton />
    </GlassCard>
  );
}

// ── Panneau Sécurité ──────────────────────────────────────────────────────────

function SecuritySettings() {
  const [sessionMin, setSessionMin] = useState("30");
  const [refreshDays, setRefreshDays] = useState("7");
  const [maxAttempts, setMaxAttempts] = useState("5");
  const [lockMin, setLockMin] = useState("15");

  return (
    <GlassCard className="space-y-6 p-6">
      <SectionTitle icon={Shield} title="Sécurité & Sessions" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Durée session access token (min)" value={sessionMin} onChange={setSessionMin} type="number" />
        <Field label="Durée refresh token (jours)" value={refreshDays} onChange={setRefreshDays} type="number" />
        <Field label="Tentatives max avant blocage" value={maxAttempts} onChange={setMaxAttempts} type="number" />
        <Field label="Durée de blocage (min)" value={lockMin} onChange={setLockMin} type="number" />
      </div>
      <div className="rounded-xl border border-warning/40 bg-warning/10 p-4 text-sm text-warning-foreground">
        <strong>Note :</strong> Ces paramètres nécessitent un redémarrage du serveur pour être appliqués.
      </div>
      <SaveButton />
    </GlassCard>
  );
}

// ── Panneau Notifications ─────────────────────────────────────────────────────

function NotificationSettings() {
  const [emailEnabled, setEmailEnabled] = useState(true);
  const [smsEnabled, setSmsEnabled] = useState(false);
  const [pushEnabled, setPushEnabled] = useState(true);

  return (
    <GlassCard className="space-y-6 p-6">
      <SectionTitle icon={Bell} title="Canaux de notification" />
      <div className="space-y-4">
        <Toggle label="Notifications par email" description="Envoyer des alertes par email" enabled={emailEnabled} onChange={setEmailEnabled} />
        <Toggle label="Notifications SMS" description="Envoyer des alertes par SMS" enabled={smsEnabled} onChange={setSmsEnabled} />
        <Toggle label="Notifications push (in-app)" description="Notifications temps réel dans l'application" enabled={pushEnabled} onChange={setPushEnabled} />
      </div>
      <SaveButton />
    </GlassCard>
  );
}

// ── Panneau SLA ───────────────────────────────────────────────────────────────

function SlaSettings() {
  const [warnPercent, setWarnPercent] = useState("80");
  const [critPercent, setCritPercent] = useState("100");

  return (
    <GlassCard className="space-y-6 p-6">
      <SectionTitle icon={Clock} title="SLA & Alertes" />
      <p className="text-sm text-muted-foreground">
        Les politiques SLA détaillées sont configurées dans{" "}
        <a href="/app/admin/sla" className="text-primary underline">SLA & Priorités</a>.
      </p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Alerte à X% du délai SLA" value={warnPercent} onChange={setWarnPercent} type="number" />
        <Field label="Escalade automatique à X% du délai" value={critPercent} onChange={setCritPercent} type="number" />
      </div>
      <SaveButton />
    </GlassCard>
  );
}

// ── Panneau Système ───────────────────────────────────────────────────────────

function SystemInfo() {
  const info = [
    { label: "Version API", value: "v1.0.0" },
    { label: "Environnement", value: "Production" },
    { label: "Base de données", value: "PostgreSQL 15" },
    { label: "Cache", value: "Redis 7.0" },
    { label: "Serveur SSE", value: "asyncio event bus" },
    { label: "Authentification", value: "JWT HS256 + Argon2id" },
  ];

  return (
    <GlassCard className="space-y-4 p-6">
      <SectionTitle icon={Server} title="Informations système" />
      <dl className="space-y-3">
        {info.map((i) => (
          <div key={i.label} className="flex items-center justify-between border-b border-border/30 pb-2 text-sm">
            <dt className="text-muted-foreground">{i.label}</dt>
            <dd className="font-mono font-medium">{i.value}</dd>
          </div>
        ))}
      </dl>
      <div className="flex items-center gap-2 rounded-xl bg-success/10 px-4 py-2.5 text-sm text-success">
        <CheckCircle2 className="h-4 w-4 shrink-0" />
        Tous les services opérationnels
      </div>
    </GlassCard>
  );
}

// ── Panneau Données ───────────────────────────────────────────────────────────

function DataSettings() {
  const [logRetentionDays, setLogRetentionDays] = useState("365");

  return (
    <GlassCard className="space-y-6 p-6">
      <SectionTitle icon={Database} title="Rétention & Données" />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Rétention des journaux (jours)" value={logRetentionDays} onChange={setLogRetentionDays} type="number" />
      </div>
      <div className="flex flex-wrap gap-3 pt-2">
        <Button
          variant="outline"
          className="rounded-full"
          onClick={() => toast.success("Export des logs démarré (simulé).")}
        >
          <Database className="mr-2 h-4 w-4" /> Exporter les journaux
        </Button>
        <Button
          variant="outline"
          className="rounded-full"
          onClick={() => toast.success("Sauvegarde de la base de données démarrée (simulé).")}
        >
          <Server className="mr-2 h-4 w-4" /> Sauvegarder la base
        </Button>
      </div>
      <SaveButton />
    </GlassCard>
  );
}

// ── Composants helpers ────────────────────────────────────────────────────────

function SectionTitle({ icon: Icon, title }: { icon: typeof Settings2; title: string }) {
  return (
    <div className="flex items-center gap-2 border-b border-border/40 pb-4">
      <Icon className="h-5 w-5 text-primary" />
      <h2 className="font-semibold">{title}</h2>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label>{label}</Label>
      <Input type={type} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}

function Toggle({
  label,
  description,
  enabled,
  onChange,
}: {
  label: string;
  description: string;
  enabled: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl border border-border/40 p-4">
      <div>
        <div className="font-medium text-sm">{label}</div>
        <div className="text-xs text-muted-foreground">{description}</div>
      </div>
      <button
        onClick={() => onChange(!enabled)}
        className={cn(
          "relative h-6 w-11 rounded-full transition",
          enabled ? "gradient-primary" : "bg-muted",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform",
            enabled ? "translate-x-5" : "translate-x-0.5",
          )}
        />
      </button>
    </div>
  );
}

function SaveButton() {
  return (
    <div className="flex justify-end pt-2">
      <Button
        className="gradient-primary rounded-full"
        onClick={() => toast.success("Paramètres enregistrés.")}
      >
        Enregistrer
      </Button>
    </div>
  );
}
