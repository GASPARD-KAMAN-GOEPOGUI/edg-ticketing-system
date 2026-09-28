import { createFileRoute } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useRole, useUser, roleLabels, setUser, clearUser } from "@/lib/session";
import { useTheme } from "@/lib/use-theme";
import { fetchDirections, fetchUnits } from "@/lib/api/directions-units";
import { ApiError } from "@/lib/api/client";
import { toast } from "sonner";
import { useState, useEffect, useRef } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchMe, updateMe, uploadAvatar, deleteAvatar, buildAvatarUrl } from "@/lib/api/accounts";
import { changeMyPassword } from "@/lib/api/auth";
import { fetchRequests } from "@/lib/api/requests";
import { cn } from "@/lib/utils";
import { PHONE_FORMAT_HINT } from "@/lib/phone";
import { usePhoneInput } from "@/hooks/use-phone-input";
import type { LucideIcon } from "lucide-react";
import {
  User,
  Shield,
  Bell,
  Palette,
  Camera,
  Loader2,
  Building2,
  Briefcase,
  Phone,
  Mail,
  Lock,
  CheckCircle2,
  Sun,
  Moon,
  Monitor,
  Globe,
  LogOut,
  Zap,
  FileText,
  ChevronRight,
  Info,
  Smartphone,
  Trash2,
} from "lucide-react";

export const Route = createFileRoute("/app/profile")({
  head: () => ({ meta: [{ title: "Profil & Paramètres — EDG Support" }] }),
  component: ProfilePage,
});

type Section = "info" | "pro" | "security" | "notifications" | "appearance";

// ── Section card header ───────────────────────────────────────────────────
function SectionHeader({
  icon: Icon,
  label,
  desc,
  color = "bg-primary/10",
  iconColor = "text-primary",
  asDialogTitle = false,
}: {
  icon: LucideIcon;
  label: string;
  desc: string;
  color?: string;
  iconColor?: string;
  /** Dans une modale, ce titre EST le titre accessible : pas de second titre
   *  `sr-only` en doublon, le lecteur d'écran n'annonce qu'une seule fois. */
  asDialogTitle?: boolean;
}) {
  const Title = asDialogTitle ? DialogTitle : "h3";
  return (
    <div className="flex items-center gap-3 border-b border-border/40 pb-4">
      <div className={cn("grid h-9 w-9 shrink-0 place-items-center rounded-xl", color)}>
        <Icon className={cn("h-5 w-5", iconColor)} />
      </div>
      <div>
        <Title className="font-semibold">{label}</Title>
        <p className="text-xs text-muted-foreground">{desc}</p>
      </div>
    </div>
  );
}

// ── Notification row ──────────────────────────────────────────────────────
function NotifRow({
  label,
  desc,
  value,
  set,
}: {
  label: string;
  desc: string;
  value: boolean;
  set: (v: boolean) => void;
}) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-card/40 px-4 py-3">
      <div>
        <div className="text-sm font-medium">{label}</div>
        <div className="text-xs text-muted-foreground">{desc}</div>
      </div>
      <Switch checked={value} onCheckedChange={set} />
    </div>
  );
}

// ── Page principale ───────────────────────────────────────────────────────
function ProfilePage() {
  const [role] = useRole();
  const [dark, toggleDark] = useTheme();
  const sessionUser = useUser();
  const queryClient = useQueryClient();

  const { data: me } = useQuery({
    queryKey: ["me"],
    queryFn: () => fetchMe(),
  });

  const { data: directionsData = [] } = useQuery({
    queryKey: ["directions"],
    queryFn: () => fetchDirections(),
    staleTime: 10 * 60_000,
  });

  const { data: unitsData = [] } = useQuery({
    queryKey: ["units"],
    queryFn: () => fetchUnits(),
    staleTime: 10 * 60_000,
  });

  const updateMeMut = useMutation({
    mutationFn: (data: Parameters<typeof updateMe>[0]) => updateMe(data),
    onSuccess: (updated) => {
      toast.success("Modifications enregistrées");
      if (sessionUser) {
        setUser({
          ...sessionUser,
          name: updated.name,
          firstname: updated.firstname ?? undefined,
          email: updated.email,
          phone: updated.phone ?? undefined,
          avatar: updated.avatar,
        });
      }
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: (err: unknown) => {
      // Log pour debug

      console.error("updateMe error:", err);
      // Si ApiError (détail backend), afficher message + hint
      if (err instanceof ApiError || (err as any)?.errorCode) {
        const e = err as any;
        const parts = [e.message];
        if (e.hint) parts.push(e.hint);
        if (e.errorCode) parts.push(`(${e.errorCode})`);
        toast.error(parts.filter(Boolean).join(" — "));
        return;
      }
      const msg = (err as any)?.message ?? "Erreur lors de la sauvegarde";
      toast.error(String(msg));
    },
  });

  // ── Avatar ─────────────────────────────────────────────────────────────────
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [avatarPreview, setAvatarPreview] = useState<string | undefined>(undefined);

  const uploadAvatarMut = useMutation({
    mutationFn: (file: File) => uploadAvatar(file),
    onSuccess: (updated) => {
      toast.success("Photo de profil mise à jour");
      setAvatarPreview(updated.avatar);
      if (sessionUser) {
        setUser({ ...sessionUser, avatar: updated.avatar });
      }
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => toast.error("Erreur lors de l'upload de la photo"),
  });

  const deleteAvatarMut = useMutation({
    mutationFn: () => deleteAvatar(),
    onSuccess: () => {
      toast.success("Photo de profil supprimée");
      setAvatarPreview(undefined);
      if (sessionUser) {
        setUser({ ...sessionUser, avatar: undefined });
      }
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
    onError: () => toast.error("Erreur lors de la suppression de la photo"),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const preview = URL.createObjectURL(file);
    setAvatarPreview(preview);
    uploadAvatarMut.mutate(file);
    e.target.value = "";
  };

  // Sync session localStorage avec les données réelles de l'API
  // Corrige le conflit header ≠ profil si la session est désynchronisée
  useEffect(() => {
    if (!me || !sessionUser) return;
    if (
      me.name !== sessionUser.name ||
      (me.firstname ?? undefined) !== sessionUser.firstname ||
      me.email !== sessionUser.email ||
      (me.phone ?? undefined) !== sessionUser.phone
    ) {
      setUser({
        ...sessionUser,
        name: me.name,
        firstname: me.firstname ?? undefined,
        email: me.email,
        phone: me.phone ?? undefined,
        avatar: me.avatar ?? undefined,
        direction_id: me.direction_id ?? undefined,
        unit_id: me.unit_id ?? undefined,
      });
    }
  }, [me?.firstname, me?.name, me?.email, me?.phone]);

  // Sync avatar from backend when loaded
  useEffect(() => {
    if (me?.avatar && !avatarPreview) {
      setAvatarPreview(me.avatar);
    }
  }, [me]);

  // ── Stats rapides (propres à l'utilisateur connecté) ──────────────────────
  const _statsOpts = {
    enabled: !!sessionUser?.id,
    staleTime: 60_000,
    refetchInterval: 60_000,
  } as const;

  const { data: statTotal } = useQuery({
    queryKey: ["profile-stats", "total", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, limit: 1 }),
    ..._statsOpts,
  });
  const { data: statResolved } = useQuery({
    queryKey: ["profile-stats", "resolved", sessionUser?.id],
    queryFn: () =>
      fetchRequests({ requester_id: sessionUser!.id, request_status: "resolved", limit: 1 }),
    ..._statsOpts,
  });
  const { data: statSlaOk } = useQuery({
    queryKey: ["profile-stats", "sla-ok", sessionUser?.id],
    queryFn: () => fetchRequests({ requester_id: sessionUser!.id, sla_breached: false, limit: 1 }),
    ..._statsOpts,
  });

  const totalRequests = statTotal?.total ?? 0;
  const totalResolved = statResolved?.total ?? 0;
  const slaPercent =
    totalRequests > 0 ? Math.round(((statSlaOk?.total ?? 0) / totalRequests) * 100) : 100;

  const fullDisplayName = me ? [me.firstname, me.name].filter(Boolean).join(" ") : "Démo EDG";
  const parts = fullDisplayName.split(" ");
  const initials = parts
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const [section, setSection] = useState<Section>("info");
  const [modalOpen, setModalOpen] = useState(false);

  // ── Changement de mot de passe (self-service, sans email) ──────────────────
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);

  const resetPasswordForm = () => {
    setNewPassword("");
    setConfirmPassword("");
    setShowPassword(false);
  };

  const passwordsMatch = newPassword === confirmPassword;
  const passwordLongEnough = newPassword.length >= 8;
  const canSubmitPassword = passwordLongEnough && passwordsMatch && confirmPassword.length > 0;

  const changePasswordMut = useMutation({
    mutationFn: () => changeMyPassword(newPassword, confirmPassword),
    onSuccess: () => {
      toast.success("Mot de passe modifié. Il est actif immédiatement.");
      setPasswordModalOpen(false);
      resetPasswordForm();
    },
    onError: (e) =>
      toast.error(
        e instanceof ApiError ? e.message : "Impossible de modifier le mot de passe. Réessayez.",
      ),
  });

  const openSection = (id: Section) => {
    setSection(id);
    setModalOpen(true);
  };

  // Informations personnelles
  const [fName, setFName] = useState("");
  const [lName, setLName] = useState("");
  const [email, setEmail] = useState("");
  const phoneInput = usePhoneInput();
  const [lang, setLang] = useState("fr");

  useEffect(() => {
    if (!me) return;
    if (me.firstname) {
      setFName(me.firstname);
      setLName(me.name);
    } else {
      const nameParts = me.name.split(" ");
      setFName(nameParts[0] ?? "");
      setLName(nameParts.slice(1).join(" ") ?? "");
    }
    setEmail(me.email);
    phoneInput.reset(me.phone ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [me]);

  // Sécurité
  const [twoFactor, setTwoFactor] = useState(false);

  // Notifications in-app
  const [nInApp, setNInApp] = useState(true);
  const [nSLA, setNSLA] = useState(me?.notif_sla_alerts ?? true);
  const [nEscalade, setNEscalade] = useState(me?.notif_escalations ?? true);
  const [nResolution, setNResolution] = useState(me?.notif_resolutions ?? true);
  // Notifications email
  const [nEmail, setNEmail] = useState(true);
  const [nEmailComments, setNEmailComments] = useState(me?.notif_comments ?? false);
  const [nEmailWeekly, setNEmailWeekly] = useState(false);

  // Sync notif prefs when me loads
  useEffect(() => {
    if (!me) return;
    setNSLA(me.notif_sla_alerts);
    setNEscalade(me.notif_escalations);
    setNResolution(me.notif_resolutions);
    setNEmailComments(me.notif_comments);
  }, [me]);

  // Apparence
  const [compact, setCompact] = useState(false);

  const navItems: { id: Section; label: string; desc: string; icon: LucideIcon }[] = [
    { id: "info", label: "Informations personnelles", desc: "Nom, email, téléphone", icon: User },
    {
      id: "pro",
      label: "Profil professionnel",
      desc: "Poste, direction, badge",
      icon: Briefcase,
    },
    { id: "security", label: "Sécurité", desc: "Mot de passe, 2FA, sessions", icon: Shield },
    { id: "notifications", label: "Notifications", desc: "Email, in-app, alertes", icon: Bell },
    { id: "appearance", label: "Apparence", desc: "Thème, langue, densité", icon: Palette },
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* ── En-tête ── */}
      <header>
        <div className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1 text-xs font-medium text-primary">
          <User className="h-3 w-3" /> Mon compte
        </div>
        <h1 className="mt-3 text-2xl font-bold tracking-tight sm:text-3xl">Profil & Paramètres</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Gérez vos informations personnelles et vos préférences.
        </p>
      </header>

      {/* ── Layout principal ── */}
      <div className="mx-auto max-w-lg space-y-4">
        {/* ════ Carte profil ════ */}
        <GlassCard className="overflow-hidden p-0">
          {/* Bannière avec dégradé EDG */}
          <div className="relative h-28 bg-primary">
            {/* Badge rôle en haut à droite */}
            <span className="absolute right-4 top-4 rounded-full bg-white/20 px-2.5 py-1 text-[11px] font-semibold text-white backdrop-blur-sm">
              {roleLabels[role as keyof typeof roleLabels] ?? role}
            </span>
          </div>

          {/* Identité : avatar + nom + email */}
          <div className="flex items-end gap-4 px-6 pb-5 -mt-10">
            {/* Avatar */}
            <div className="relative shrink-0">
              {avatarPreview ? (
                <img
                  src={buildAvatarUrl(avatarPreview)}
                  alt={fullDisplayName}
                  className="h-20 w-20 rounded-2xl border-4 border-background object-cover shadow-lg"
                />
              ) : (
                <div className="grid h-20 w-20 place-items-center rounded-2xl border-4 border-background gradient-primary text-2xl font-bold text-background shadow-lg">
                  {initials}
                </div>
              )}
              {/* Camera button — change photo */}
              <button
                type="button"
                title="Changer la photo de profil"
                disabled={uploadAvatarMut.isPending || deleteAvatarMut.isPending}
                onClick={() => fileInputRef.current?.click()}
                className="absolute -bottom-1 -right-1 grid h-7 w-7 place-items-center rounded-full border-2 border-background bg-card shadow-md transition hover:bg-muted disabled:opacity-50"
              >
                {uploadAvatarMut.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                ) : (
                  <Camera className="h-3.5 w-3.5 text-muted-foreground" />
                )}
              </button>
              {/* Trash button — delete photo (only when avatar exists) */}
              {avatarPreview && (
                <button
                  type="button"
                  title="Supprimer la photo de profil"
                  disabled={deleteAvatarMut.isPending || uploadAvatarMut.isPending}
                  onClick={() => deleteAvatarMut.mutate()}
                  className="absolute -bottom-1 -left-1 grid h-7 w-7 place-items-center rounded-full border-2 border-background bg-card shadow-md transition hover:bg-destructive/10 disabled:opacity-50"
                >
                  {deleteAvatarMut.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin text-destructive" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5 text-destructive" />
                  )}
                </button>
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={handleFileChange}
              />
            </div>

            {/* Nom + email + statut */}
            <div className="flex-1 pb-1 pt-12">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold leading-tight">
                  {fName} {lName}
                </h2>
                <span className="flex items-center gap-1 text-[11px] text-success">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" />
                  En ligne
                </span>
              </div>
              <p className="text-sm text-muted-foreground">{email}</p>
            </div>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 divide-x divide-border/40 border-t border-border/40 text-center">
            <div className="py-4">
              <div className="text-2xl font-bold">
                {statTotal ? (
                  totalRequests
                ) : (
                  <span className="text-base text-muted-foreground">—</span>
                )}
              </div>
              <div className="mt-0.5 text-[11px] font-medium text-muted-foreground">Tickets</div>
            </div>
            <div className="py-4">
              <div className="text-2xl font-bold text-success">
                {statResolved ? (
                  totalResolved
                ) : (
                  <span className="text-base text-muted-foreground">—</span>
                )}
              </div>
              <div className="mt-0.5 text-[11px] font-medium text-muted-foreground">Résolues</div>
            </div>
            <div className="py-4">
              <div className="text-2xl font-bold text-primary">
                {statTotal ? (
                  `${slaPercent}%`
                ) : (
                  <span className="text-base text-muted-foreground">—</span>
                )}
              </div>
              <div className="mt-0.5 text-[11px] font-medium text-muted-foreground">
                Respect délai
              </div>
            </div>
          </div>
        </GlassCard>

        {/* ════ Navigation en grille ════ */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          {navItems.map(({ id, label, desc, icon: Icon }, idx) => {
            const active = section === id && modalOpen;
            const isLastOdd = idx === navItems.length - 1 && navItems.length % 2 !== 0;
            return (
              <button
                key={id}
                type="button"
                onClick={() => openSection(id)}
                className={cn(
                  "group flex flex-col gap-3 rounded-2xl border p-4 text-left transition-all duration-150",
                  isLastOdd && "sm:col-span-1 col-span-2",
                  active
                    ? "border-primary/50 bg-primary/8 shadow-sm shadow-primary/10"
                    : "border-border/40 bg-card/50 hover:border-border/70 hover:bg-card hover:shadow-sm",
                )}
              >
                <div
                  className={cn(
                    "grid h-10 w-10 place-items-center rounded-xl transition-colors",
                    active
                      ? "bg-primary text-background"
                      : "bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary",
                  )}
                >
                  <Icon className="h-5 w-5" />
                </div>
                <div>
                  <p
                    className={cn(
                      "text-sm font-semibold leading-tight",
                      active ? "text-primary" : "text-foreground",
                    )}
                  >
                    {label}
                  </p>
                  <p className="mt-0.5 text-[11px] text-muted-foreground">{desc}</p>
                </div>
              </button>
            );
          })}
        </div>

        {/* ════ Déconnexion ════ */}
        <Button
          variant="outline"
          className="w-full gap-2 rounded-xl border-destructive/30 text-destructive hover:bg-destructive/8 hover:border-destructive/50"
          onClick={() => {
            clearUser();
            window.location.href = "/";
          }}
        >
          <LogOut className="h-4 w-4" />
          Se déconnecter
        </Button>
      </div>

      {/* ── Modal sections ── */}
      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent className="max-w-2xl">
          {/* ── Informations personnelles ── */}
          {section === "info" && (
            <div className="space-y-6">
              <SectionHeader
                asDialogTitle
                icon={User}
                label="Informations personnelles"
                desc="Modifiez vos données de contact"
              />

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="grid gap-2">
                  <Label htmlFor="fname">Prénom</Label>
                  <Input
                    id="fname"
                    value={fName}
                    onChange={(e) => setFName(e.target.value)}
                    placeholder="Prénom"
                  />
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="lname">Nom de famille</Label>
                  <Input
                    id="lname"
                    value={lName}
                    onChange={(e) => setLName(e.target.value)}
                    placeholder="Nom"
                  />
                </div>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="email" className="flex items-center gap-1.5">
                  <Mail className="h-3.5 w-3.5 text-muted-foreground" />
                  Adresse email
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="votre@email.com"
                />
              </div>

              <div className="grid gap-2">
                <Label htmlFor="phone" className="flex items-center gap-1.5">
                  <Phone className="h-3.5 w-3.5 text-muted-foreground" />
                  Téléphone
                </Label>
                <Input
                  id="phone"
                  ref={phoneInput.ref}
                  type="tel"
                  inputMode="tel"
                  value={phoneInput.display}
                  onChange={phoneInput.onChange}
                  placeholder="+224 6XX XX XX XX"
                />
                {phoneInput.hasError && (
                  <p className="text-xs text-destructive">
                    Format invalide. Attendu : {PHONE_FORMAT_HINT}.
                  </p>
                )}
              </div>

              <div className="flex justify-end border-t border-border/40 pt-4">
                <Button
                  className="rounded-xl gradient-primary text-background shadow-md shadow-primary/30"
                  disabled={updateMeMut.isPending || phoneInput.hasError}
                  onClick={() =>
                    updateMeMut.mutate(
                      {
                        firstname: fName.trim() || undefined,
                        name: lName.trim() || fName.trim(),
                        phone: phoneInput.value || undefined,
                        email: email.trim() || undefined,
                      },
                      { onSuccess: () => setModalOpen(false) },
                    )
                  }
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Enregistrer les modifications
                </Button>
              </div>
            </div>
          )}

          {/* ── Profil professionnel ── */}
          {section === "pro" && (
            <div className="space-y-5">
              <SectionHeader
                asDialogTitle
                icon={Briefcase}
                label="Profil professionnel"
                desc="Données gérées par les Ressources Humaines"
                color="bg-info/10"
                iconColor="text-info"
              />

              <div className="flex items-start gap-2 rounded-xl border border-info/20 bg-info/5 p-3 text-sm text-info">
                <Info className="mt-0.5 h-4 w-4 shrink-0" />
                <span>
                  Ces informations sont en lecture seule. Contactez les Ressources Humaines pour
                  toute modification.
                </span>
              </div>

              <div className="space-y-2">
                {[
                  { label: "Badge", value: me?.matricule ?? "—", icon: FileText, mono: true },
                  { label: "Poste", value: me?.job ?? "—", icon: Briefcase, mono: false },
                  {
                    label: "Direction",
                    value: (
                      directionsData.find((d) => d.id === me?.direction_id)?.name ??
                      me?.direction_id ??
                      "—"
                    ).toUpperCase(),
                    icon: Building2,
                    mono: false,
                  },
                  {
                    label: "Service",
                    value: unitsData.find((u) => u.id === me?.unit_id)?.name ?? me?.unit_id ?? "—",
                    icon: Zap,
                    mono: false,
                  },
                ].map(({ label, value, icon: Icon, mono }) => (
                  <div
                    key={label}
                    className="flex items-center justify-between rounded-xl bg-card/40 px-4 py-3"
                  >
                    <div className="flex items-center gap-3">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm text-muted-foreground">{label}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className={cn("text-sm font-medium", mono && "font-mono text-primary")}>
                        {value}
                      </span>
                      <Lock className="h-3.5 w-3.5 text-muted-foreground/40" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Sécurité ── */}
          {section === "security" && (
            <div className="space-y-3">
              <SectionHeader
                asDialogTitle
                icon={Shield}
                label="Mot de passe"
                desc="Identité gérée par la plateforme centrale EDG"
              />
              <p className="text-sm text-muted-foreground">
                Vous pouvez modifier votre mot de passe directement ici. La mise à jour est
                immédiate et s&apos;applique partout où vous utilisez votre compte EDG.
              </p>
              <Button
                variant="outline"
                className="rounded-full"
                onClick={() => setPasswordModalOpen(true)}
              >
                Modifier mon mot de passe
              </Button>
            </div>
          )}

          {/* ── Notifications ── */}
          {section === "notifications" && (
            <div className="space-y-6">
              <SectionHeader
                asDialogTitle
                icon={Bell}
                label="Préférences de notification"
                desc="Choisissez ce que vous souhaitez recevoir"
              />

              <div>
                <h4 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <Bell className="h-3.5 w-3.5" />
                  Notifications in-app
                </h4>
                <div className="space-y-2">
                  <NotifRow
                    label="Toutes les notifications"
                    desc="Activez ou désactivez toutes les alertes in-app"
                    value={nInApp}
                    set={setNInApp}
                  />
                  <NotifRow
                    label="Alertes délais critiques"
                    desc="Délais dépassés ou proches d'expiration"
                    value={nSLA}
                    set={setNSLA}
                  />
                  {/* Bascule "Escalades reçues" retirée le 2026-09-26 avec le statut
                      "escalated" : plus aucune notification d'escalade n'est émise. La
                      colonne `notif_escalations` reste écrite telle quelle ci-dessous —
                      la table `account` est partagée avec la plateforme centrale et son
                      schéma ne doit pas être modifié. */}
                  <NotifRow
                    label="Résolution de tickets"
                    desc="Notification quand un ticket est résolu"
                    value={nResolution}
                    set={setNResolution}
                  />
                </div>
              </div>

              <div>
                <h4 className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  <Mail className="h-3.5 w-3.5" />
                  Email
                </h4>
                <div className="space-y-2">
                  <NotifRow
                    label="Alertes délais par email"
                    desc="Envoi email pour les délais critiques"
                    value={nEmail}
                    set={setNEmail}
                  />
                  <NotifRow
                    label="Nouveaux commentaires"
                    desc="Réponses sur vos tickets en cours"
                    value={nEmailComments}
                    set={setNEmailComments}
                  />
                </div>
              </div>

              <div className="flex justify-end border-t border-border/40 pt-4">
                <Button
                  className="rounded-xl gradient-primary text-background shadow-md shadow-primary/30"
                  disabled={updateMeMut.isPending}
                  onClick={() =>
                    updateMeMut.mutate(
                      {
                        notif_sla_alerts: nSLA,
                        notif_escalations: nEscalade,
                        notif_resolutions: nResolution,
                        notif_comments: nEmailComments,
                      },
                      { onSuccess: () => setModalOpen(false) },
                    )
                  }
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Enregistrer
                </Button>
              </div>
            </div>
          )}

          {/* ── Apparence ── */}
          {section === "appearance" && (
            <div className="space-y-6">
              <SectionHeader
                asDialogTitle
                icon={Palette}
                label="Apparence"
                desc="Personnalisez l'interface selon vos préférences"
                color="bg-primary/10"
                iconColor="text-primary"
              />

              <div>
                <Label className="mb-3 block text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Thème
                </Label>
                <div className="grid grid-cols-3 gap-3">
                  <button
                    type="button"
                    onClick={() => {
                      if (dark) toggleDark();
                    }}
                    className={cn(
                      "relative flex flex-col overflow-hidden rounded-2xl border-2 transition hover:scale-[1.02]",
                      !dark
                        ? "border-primary shadow-md shadow-primary/20"
                        : "border-border/40 hover:border-border",
                    )}
                  >
                    <div className="h-20 w-full bg-white p-2">
                      <div className="mb-1.5 h-3 w-full rounded bg-slate-100" />
                      <div className="flex gap-1">
                        <div className="h-12 w-8 rounded bg-slate-50 border border-slate-100" />
                        <div className="flex-1 space-y-1 pt-0.5">
                          <div className="h-2 w-full rounded bg-slate-200" />
                          <div className="h-2 w-3/4 rounded bg-slate-200" />
                          <div className="h-2 w-1/2 rounded bg-slate-200" />
                        </div>
                      </div>
                    </div>
                    <div
                      className={cn(
                        "flex items-center justify-center gap-1.5 py-2 text-xs font-medium",
                        !dark ? "text-primary" : "text-muted-foreground",
                      )}
                    >
                      <Sun className="h-3.5 w-3.5" />
                      Clair
                    </div>
                    {!dark && (
                      <div className="absolute right-2 top-2 grid h-5 w-5 place-items-center rounded-full bg-primary text-background">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      if (!dark) toggleDark();
                    }}
                    className={cn(
                      "relative flex flex-col overflow-hidden rounded-2xl border-2 transition hover:scale-[1.02]",
                      dark
                        ? "border-primary shadow-md shadow-primary/20"
                        : "border-border/40 hover:border-border",
                    )}
                  >
                    <div className="h-20 w-full bg-slate-900 p-2">
                      <div className="mb-1.5 h-3 w-full rounded bg-slate-800" />
                      <div className="flex gap-1">
                        <div className="h-12 w-8 rounded bg-slate-800/80" />
                        <div className="flex-1 space-y-1 pt-0.5">
                          <div className="h-2 w-full rounded bg-slate-700" />
                          <div className="h-2 w-3/4 rounded bg-slate-700" />
                          <div className="h-2 w-1/2 rounded bg-slate-700" />
                        </div>
                      </div>
                    </div>
                    <div
                      className={cn(
                        "flex items-center justify-center gap-1.5 py-2 text-xs font-medium",
                        dark ? "text-primary" : "text-muted-foreground",
                      )}
                    >
                      <Moon className="h-3.5 w-3.5" />
                      Sombre
                    </div>
                    {dark && (
                      <div className="absolute right-2 top-2 grid h-5 w-5 place-items-center rounded-full bg-primary text-background">
                        <CheckCircle2 className="h-3 w-3" />
                      </div>
                    )}
                  </button>

                  <div className="relative flex cursor-not-allowed flex-col overflow-hidden rounded-2xl border-2 border-border/30 opacity-40">
                    <div className="h-20 w-full bg-gradient-to-br from-white to-slate-900 p-2">
                      <div className="mb-1.5 h-3 w-full rounded bg-slate-400/30" />
                      <div className="flex gap-1">
                        <div className="h-12 w-8 rounded bg-slate-400/20" />
                        <div className="flex-1 space-y-1 pt-0.5">
                          <div className="h-2 w-full rounded bg-slate-400/30" />
                          <div className="h-2 w-3/4 rounded bg-slate-400/30" />
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center justify-center gap-1.5 py-2 text-xs font-medium text-muted-foreground">
                      <Monitor className="h-3.5 w-3.5" />
                      Système
                    </div>
                    <span className="absolute inset-x-0 bottom-8 text-center text-[9px] text-muted-foreground">
                      Bientôt
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end border-t border-border/40 pt-4">
                <Button
                  className="rounded-xl gradient-primary text-background shadow-md shadow-primary/30"
                  onClick={() => {
                    toast.success("Préférences d'apparence enregistrées");
                    setModalOpen(false);
                  }}
                >
                  <CheckCircle2 className="mr-2 h-4 w-4" />
                  Appliquer
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* ── Modale : changer mon mot de passe (sans email ni code) ────────── */}
      <Dialog
        open={passwordModalOpen}
        onOpenChange={(open) => {
          // Ne pas fermer pendant l'envoi — évite de perdre l'état en cours.
          if (changePasswordMut.isPending) return;
          setPasswordModalOpen(open);
          if (!open) resetPasswordForm();
        }}
      >
        <DialogContent className="max-w-md">
          <DialogTitle>Modifier mon mot de passe</DialogTitle>
          <p className="text-sm text-muted-foreground">
            Saisissez votre nouveau mot de passe. La modification est immédiate et s&apos;applique
            partout où vous utilisez votre compte EDG.
          </p>

          <form
            className="space-y-4"
            onSubmit={(e) => {
              e.preventDefault();
              if (!canSubmitPassword || changePasswordMut.isPending) return;
              changePasswordMut.mutate();
            }}
          >
            <div>
              <Label htmlFor="new-password">Nouveau mot de passe</Label>
              <Input
                id="new-password"
                type={showPassword ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                autoFocus
                className="mt-1.5"
                disabled={changePasswordMut.isPending}
              />
              {newPassword.length > 0 && !passwordLongEnough && (
                <p className="mt-1 text-xs text-destructive">8 caractères minimum.</p>
              )}
            </div>

            <div>
              <Label htmlFor="confirm-password">Confirmer le mot de passe</Label>
              <Input
                id="confirm-password"
                type={showPassword ? "text" : "password"}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
                className="mt-1.5"
                disabled={changePasswordMut.isPending}
              />
              {confirmPassword.length > 0 && !passwordsMatch && (
                <p className="mt-1 text-xs text-destructive">
                  Les deux mots de passe ne correspondent pas.
                </p>
              )}
            </div>

            <label className="flex items-center gap-2 text-sm text-muted-foreground">
              <input
                type="checkbox"
                checked={showPassword}
                onChange={(e) => setShowPassword(e.target.checked)}
                disabled={changePasswordMut.isPending}
              />
              Afficher les mots de passe
            </label>

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                className="rounded-full"
                disabled={changePasswordMut.isPending}
                onClick={() => {
                  setPasswordModalOpen(false);
                  resetPasswordForm();
                }}
              >
                Annuler
              </Button>
              <Button
                type="submit"
                className="gradient-primary rounded-full"
                disabled={!canSubmitPassword || changePasswordMut.isPending}
              >
                {changePasswordMut.isPending ? "Modification…" : "Valider"}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
