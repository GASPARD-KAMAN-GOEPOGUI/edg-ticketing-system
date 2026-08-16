import { createFileRoute } from "@tanstack/react-router";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Megaphone, Plus, Settings2, BarChart3, Send, Trash2, Edit3,
  Eye, AlertTriangle, Bell, Mail, Smartphone, Monitor, Globe,
  X, Clock, FileText, Users, ChevronDown,
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import {
  announcementCategoryLabels,
  announcementPriorityLabels,
  announcementStatusLabels,
  defaultCommunicationSettings,
  type Announcement,
  type AnnouncementCategory,
  type AnnouncementPriority,
  type AnnouncementChannel,
  type AnnouncementAudience,
  type AnnouncementStatus,
  type CommunicationSettings,
  type Role,
} from "@/lib/mock-data";
import {
  fetchAnnouncements,
  createAnnouncement,
  updateAnnouncement,
  publishAnnouncement,
  closeAnnouncement,
  deleteAnnouncement,
  fetchCommSettings,
  updateCommSettings,
} from "@/lib/api/communication";
import { fetchMe } from "@/lib/api/accounts";

export const Route = createFileRoute("/app/admin/communication")({
  component: AdminCommunication,
});

const CATEGORIES = Object.entries(announcementCategoryLabels) as [AnnouncementCategory, string][];
const PRIORITIES = Object.entries(announcementPriorityLabels) as [AnnouncementPriority, string][];
const ROLES_LIST: { value: Role; label: string }[] = [
  { value: "user", label: "Demandeurs internes" },
  { value: "agent", label: "Agents" },
  { value: "chief", label: "Chefs de service" },
  { value: "director", label: "Directeurs" },
  { value: "admin", label: "Administrateurs" },
];

const CHANNEL_META: { key: AnnouncementChannel; label: string; icon: React.ElementType; comingSoon?: boolean }[] = [
  { key: "internal_notif", label: "Notifications internes",   icon: Bell },
  { key: "email",          label: "Email",                    icon: Mail },
  { key: "sms",            label: "SMS",                      icon: Smartphone },
  { key: "dashboard",      label: "Tableau de bord",          icon: Monitor },
  { key: "homepage",       label: "Page d'accueil",           icon: Globe },
];

const PRIORITY_COLORS: Record<AnnouncementPriority, string> = {
  low:                "text-slate-400 bg-slate-500/10 border-slate-500/20",
  medium:             "text-info bg-info/10 border-info/20",
  high:               "text-yellow-400 bg-yellow-500/10 border-yellow-500/20",
  critical:           "text-red-400 bg-red-500/10 border-red-500/20",
  absolute_emergency: "text-red-200 bg-red-900/30 border-red-400/40",
};

const STATUS_COLORS: Record<AnnouncementStatus, string> = {
  draft:     "text-slate-400",
  published: "text-green-400",
  expired:   "text-orange-400",
  closed:    "text-muted-foreground",
};

type FormState = {
  title: string;
  description: string;
  category: AnnouncementCategory;
  priority: AnnouncementPriority;
  publishedAt: string;
  expiresAt: string;
  audience: AnnouncementAudience;
  selectedRoles: Role[];
  selectedDirections: string[];
  channels: AnnouncementChannel[];
};

const emptyForm = (): FormState => ({
  title: "",
  description: "",
  category: "general",
  priority: "medium",
  publishedAt: new Date().toISOString().slice(0, 16),
  expiresAt: "",
  audience: "internal",
  selectedRoles: ["user", "agent", "chief", "director", "admin"],
  selectedDirections: [],
  channels: ["internal_notif", "email"],
});

function formFromAnnouncement(a: Announcement): FormState {
  return {
    title: a.title,
    description: a.description,
    category: a.category,
    priority: a.priority,
    publishedAt: a.publishedAt.slice(0, 16),
    expiresAt: a.expiresAt ? a.expiresAt.slice(0, 16) : "",
    audience: a.targets.audience,
    selectedRoles: [...a.targets.roles],
    selectedDirections: [...a.targets.directions],
    channels: [...a.channels],
  };
}

const CHART_COLORS = ["#6366f1", "#22d3ee", "#f59e0b", "#10b981", "#f43f5e"];

function AdminCommunication() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<"list" | "stats" | "settings">("list");
  const [filterStatus, setFilterStatus] = useState<AnnouncementStatus | "all">("all");
  const [filterPriority, setFilterPriority] = useState<AnnouncementPriority | "all">("all");
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm());
  const [showPreview, setShowPreview] = useState<string | null>(null);
  const [localSettings, setLocalSettings] = useState<CommunicationSettings>({ ...defaultCommunicationSettings });

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: () => fetchMe() });
  const meId = meData?.id;

  const { data: annData } = useQuery({
    queryKey: ["admin", "announcements"],
    queryFn: () => fetchAnnouncements({ limit: 100 }),
  });
  const list: Announcement[] = annData?.items ?? [];

  const { data: settingsData } = useQuery({
    queryKey: ["comm-settings"],
    queryFn: () => fetchCommSettings(),
  });
  useEffect(() => {
    if (settingsData) setLocalSettings(settingsData);
  }, [settingsData]);

  const invalidate = () => qc.invalidateQueries({ queryKey: ["admin", "announcements"] });

  const createMut = useMutation({
    mutationFn: createAnnouncement,
    onSuccess: (a) => {
      invalidate();
      toast.success(a.status === "draft" ? "Brouillon créé." : "Publication envoyée avec succès !");
      closeForm();
    },
    onError: () => toast.error("Erreur lors de la création."),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateAnnouncement>[1] }) =>
      updateAnnouncement(id, payload),
    onSuccess: (a) => {
      invalidate();
      toast.success(a.status === "draft" ? "Brouillon mis à jour." : "Publication mise à jour.");
      closeForm();
    },
    onError: () => toast.error("Erreur lors de la mise à jour."),
  });

  const publishMut = useMutation({
    mutationFn: publishAnnouncement,
    onSuccess: () => { invalidate(); toast.success("Publication envoyée !"); },
    onError: () => toast.error("Erreur lors de la publication."),
  });

  const closeMut = useMutation({
    mutationFn: closeAnnouncement,
    onSuccess: () => { invalidate(); toast.success("Publication clôturée."); },
    onError: () => toast.error("Erreur lors de la clôture."),
  });

  const deleteMut = useMutation({
    mutationFn: deleteAnnouncement,
    onSuccess: () => { invalidate(); toast.success("Publication supprimée."); },
    onError: () => toast.error("Erreur lors de la suppression."),
  });

  const saveSettingsMut = useMutation({
    mutationFn: (payload: Parameters<typeof updateCommSettings>[0]) => updateCommSettings(payload),
    onSuccess: (updated) => {
      qc.invalidateQueries({ queryKey: ["comm-settings"] });
      qc.invalidateQueries({ queryKey: ["active-alerts"] });
      setLocalSettings(updated);
      toast.success("Paramètres sauvegardés.");
    },
    onError: () => toast.error("Erreur lors de la sauvegarde des paramètres."),
  });

  function openCreate() {
    setEditingId(null);
    setForm(emptyForm());
    setShowForm(true);
  }

  function openEdit(a: Announcement) {
    setEditingId(a.id);
    setForm(formFromAnnouncement(a));
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingId(null);
  }

  function handleSave(asDraft: boolean) {
    if (!form.title.trim()) { toast.error("Le titre est obligatoire."); return; }
    if (!form.description.trim()) { toast.error("La description est obligatoire."); return; }
    if (form.channels.length === 0) { toast.error("Sélectionnez au moins un canal."); return; }

    const payload = {
      title: form.title,
      description: form.description,
      announcement_category: form.category,
      announcement_priority: form.priority,
      announcement_status: asDraft ? "draft" : "published",
      audience: form.audience,
      author_id: meId ?? "system",
      expires_at: form.expiresAt ? new Date(form.expiresAt).toISOString() : null,
      channel_names: form.channels as string[],
      role_names: form.selectedRoles as string[],
      direction_ids: form.selectedDirections,
    };

    if (editingId) {
      updateMut.mutate({ id: editingId, payload });
    } else {
      createMut.mutate(payload);
    }
  }

  function handleDelete(id: string) {
    deleteMut.mutate(id);
  }

  function handleClose(id: string) {
    closeMut.mutate(id);
  }

  function handlePublish(id: string) {
    publishMut.mutate(id);
  }

  const filtered = list.filter((a) => {
    if (filterStatus !== "all" && a.status !== filterStatus) return false;
    if (filterPriority !== "all" && a.priority !== filterPriority) return false;
    return true;
  });

  const preview = showPreview ? list.find((a) => a.id === showPreview) : null;

  const published = list.filter((a) => a.status !== "draft");
  const kpis = {
    total: list.length,
    published: list.filter((a) => a.status === "published").length,
    active_alerts: list.filter(
      (a) => a.status === "published" && (a.priority === "critical" || a.priority === "high")
    ).length,
    avg_consultation: published.length > 0
      ? Math.round(published.reduce((s, a) => s + a.metrics.consultationRate, 0) / published.length)
      : 0,
  };

  function handleSaveSettings() {
    saveSettingsMut.mutate({
      internal_notif_on: localSettings.channels.internal_notif,
      email_on: localSettings.channels.email,
      sms_on: localSettings.channels.sms,
      banner_on: localSettings.channels.banner,
      whatsapp_on: localSettings.channels.whatsapp,
      push_mobile_on: localSettings.channels.push_mobile,
      sender_email: localSettings.senderEmail,
      sender_sms: localSettings.senderSms,
      reply_to: localSettings.replyTo,
    });
  }

  return (
    <div className="p-4 md:p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center gap-3 justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-primary/10">
            <Megaphone className="h-5 w-5 text-primary" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">Centre de communication</h1>
            <p className="text-sm text-muted-foreground">Gérez les annonces et publications institutionnelles EDG</p>
          </div>
        </div>
        {tab === "list" && (
          <Button onClick={openCreate} className="gap-2">
            <Plus className="h-4 w-4" /> Nouvelle publication
          </Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-border/40">
        {(["list", "stats", "settings"] as const).map((t) => {
          const labels = { list: "Publications", stats: "Statistiques", settings: "Paramètres canaux" };
          const icons = { list: Megaphone, stats: BarChart3, settings: Settings2 };
          const Icon = icons[t];
          return (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                tab === t
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {labels[t]}
            </button>
          );
        })}
      </div>

      {/* TAB: Publications list */}
      {tab === "list" && (
        <div className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Select value={filterStatus} onValueChange={(v) => setFilterStatus(v as never)}>
              <SelectTrigger className="h-8 w-full text-sm sm:w-44">
                <SelectValue placeholder="Statut" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous statuts</SelectItem>
                {(Object.entries(announcementStatusLabels) as [AnnouncementStatus, string][]).map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filterPriority} onValueChange={(v) => setFilterPriority(v as never)}>
              <SelectTrigger className="h-8 w-full text-sm sm:w-44">
                <SelectValue placeholder="Priorité" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Toutes priorités</SelectItem>
                {PRIORITIES.map(([v, l]) => (
                  <SelectItem key={v} value={v}>{l}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {filtered.length === 0 && (
            <div className="text-center py-12 text-muted-foreground text-sm">Aucune publication correspondante.</div>
          )}

          <div className="space-y-3">
            {filtered.map((a) => (
              <div key={a.id} className="glass-card rounded-xl p-4 flex flex-col sm:flex-row sm:items-start gap-4">
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${PRIORITY_COLORS[a.priority]}`}>
                      {announcementPriorityLabels[a.priority]}
                    </span>
                    <span className={`text-xs font-medium ${STATUS_COLORS[a.status]}`}>
                      {announcementStatusLabels[a.status]}
                    </span>
                    <span className="text-xs text-muted-foreground">{announcementCategoryLabels[a.category]}</span>
                  </div>
                  <p className="font-medium text-sm leading-snug">{a.title}</p>
                  <p className="text-xs text-muted-foreground line-clamp-2">{a.description}</p>
                  <div className="flex flex-wrap gap-3 text-xs text-muted-foreground pt-1">
                    <span className="flex items-center gap-1"><Mail className="h-3 w-3" />{a.metrics.emailsSent}</span>
                    <span className="flex items-center gap-1"><Smartphone className="h-3 w-3" />{a.metrics.smsSent}</span>
                    <span className="flex items-center gap-1"><Bell className="h-3 w-3" />{a.metrics.notificationsSent}</span>
                    <span className="flex items-center gap-1"><Eye className="h-3 w-3" />{a.metrics.viewCount} vues</span>
                    <span className="flex items-center gap-1"><BarChart3 className="h-3 w-3" />{a.metrics.consultationRate}%</span>
                    <span className="flex items-center gap-1"><Clock className="h-3 w-3" />{new Date(a.publishedAt).toLocaleDateString("fr-FR")}</span>
                  </div>
                </div>
                <div className="flex sm:flex-col gap-1.5">
                  <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => setShowPreview(a.id)} title="Aperçu">
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                  {a.status !== "closed" && (
                    <Button size="icon" variant="ghost" className="h-7 w-7" onClick={() => openEdit(a)} title="Modifier"
                      disabled={updateMut.isPending}>
                      <Edit3 className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {a.status === "draft" && (
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-green-400" onClick={() => handlePublish(a.id)}
                      title="Publier" disabled={publishMut.isPending}>
                      <Send className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  {a.status === "published" && (
                    <Button size="icon" variant="ghost" className="h-7 w-7 text-orange-400" onClick={() => handleClose(a.id)}
                      title="Clôturer" disabled={closeMut.isPending}>
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  )}
                  <Button size="icon" variant="ghost" className="h-7 w-7 text-destructive" onClick={() => handleDelete(a.id)}
                    title="Supprimer" disabled={deleteMut.isPending}>
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB: Statistics */}
      {tab === "stats" && <StatsTab list={list} />}

      {/* TAB: Settings */}
      {tab === "settings" && (
        <SettingsTab
          settings={localSettings}
          onChange={setLocalSettings}
          onSave={handleSaveSettings}
          isSaving={saveSettingsMut.isPending}
        />
      )}

      {/* Form dialog */}
      {showForm && (
        <PublicationFormDialog
          form={form}
          onChange={setForm}
          onSave={handleSave}
          onClose={closeForm}
          isEdit={!!editingId}
          channelSettings={localSettings}
          isSaving={createMut.isPending || updateMut.isPending}
        />
      )}

      {/* Preview dialog */}
      {preview && (
        <PreviewDialog announcement={preview} onClose={() => setShowPreview(null)} />
      )}
    </div>
  );
}

/* ================================================================== */
/* Statistics tab                                                       */
/* ================================================================== */

function StatsTab({ list }: { list: Announcement[] }) {
  const byCategory = CATEGORIES.map(([k, label]) => {
    const items = list.filter((a) => a.category === k && a.status !== "draft");
    return {
      name: label.length > 16 ? label.slice(0, 14) + "…" : label,
      count: items.length,
      vues: items.reduce((s, a) => s + a.metrics.viewCount, 0),
    };
  }).filter((d) => d.count > 0);

  const byPriority = PRIORITIES.map(([k, label]) => ({
    name: label,
    value: list.filter((a) => a.priority === k).length,
  })).filter((d) => d.value > 0);

  const channelData = CHANNEL_META.map((c) => ({
    name: c.label,
    envois: list.filter((a) => a.channels.includes(c.key) && a.status !== "draft").length,
  }));

  const published = list.filter((a) => a.status !== "draft");
  const totalEmails = published.reduce((s, a) => s + a.metrics.emailsSent, 0);
  const totalSms = published.reduce((s, a) => s + a.metrics.smsSent, 0);
  const totalNotifs = published.reduce((s, a) => s + a.metrics.notificationsSent, 0);
  const totalViews = published.reduce((s, a) => s + a.metrics.viewCount, 0);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: "Emails envoyés", value: totalEmails, icon: Mail },
          { label: "SMS envoyés", value: totalSms, icon: Smartphone },
          { label: "Notifications", value: totalNotifs, icon: Bell },
          { label: "Consultations totales", value: totalViews, icon: Eye },
        ].map((k) => (
          <div key={k.label} className="glass-card rounded-xl p-4">
            <k.icon className="h-4 w-4 text-primary mb-1" />
            <p className="text-2xl font-bold">{k.value.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">{k.label}</p>
          </div>
        ))}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="glass-card rounded-xl p-4 space-y-3">
          <p className="font-medium text-sm">Publications par catégorie</p>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={byCategory} margin={{ left: -20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} angle={-30} textAnchor="end" interval={0} />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: "#1e1e2e", border: "1px solid #ffffff20", borderRadius: 8 }} />
              <Bar dataKey="count" name="Publications" fill="#6366f1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="vues" name="Vues" fill="#22d3ee" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="glass-card rounded-xl p-4 space-y-3">
          <p className="font-medium text-sm">Répartition par priorité</p>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={byPriority} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label>
                {byPriority.map((_, i) => (
                  <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ background: "#1e1e2e", border: "1px solid #ffffff20", borderRadius: 8 }} />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="glass-card rounded-xl p-4 space-y-3">
        <p className="font-medium text-sm">Utilisations des canaux</p>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={channelData} margin={{ left: -20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip contentStyle={{ background: "#1e1e2e", border: "1px solid #ffffff20", borderRadius: 8 }} />
            <Bar dataKey="envois" name="Publications via ce canal" fill="#10b981" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* ================================================================== */
/* Settings tab                                                         */
/* ================================================================== */

function SettingsTab({ settings, onChange, onSave, isSaving }: {
  settings: CommunicationSettings;
  onChange: (s: CommunicationSettings) => void;
  onSave: () => void;
  isSaving?: boolean;
}) {
  function toggleChannel(key: keyof CommunicationSettings["channels"]) {
    onChange({
      ...settings,
      channels: { ...settings.channels, [key]: !settings.channels[key] },
    });
  }

  const channelRows: { key: keyof CommunicationSettings["channels"]; label: string; icon: React.ElementType; comingSoon?: boolean }[] = [
    { key: "internal_notif", label: "Notifications internes", icon: Bell },
    { key: "email",          label: "Email",                  icon: Mail },
    { key: "sms",            label: "SMS (Orange Guinée)",    icon: Smartphone },
    { key: "banner",         label: "Bandeau d'alerte",       icon: AlertTriangle },
    { key: "whatsapp",       label: "WhatsApp",               icon: Send,    comingSoon: true },
    { key: "push_mobile",    label: "Push mobile",            icon: Bell,    comingSoon: true },
  ];

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="glass-card rounded-xl p-5 space-y-4">
        <p className="font-medium">Canaux de diffusion disponibles</p>
        <p className="text-sm text-muted-foreground">Les canaux désactivés ici ne seront pas proposés lors de la création d'une publication.</p>
        {channelRows.map((ch) => (
          <div key={ch.key} className="flex items-center gap-3">
            <ch.icon className="h-4 w-4 text-muted-foreground shrink-0" />
            <span className="flex-1 text-sm">
              {ch.label}
              {ch.comingSoon && (
                <span className="ml-2 text-xs text-muted-foreground border border-dashed border-border/60 px-1.5 py-0.5 rounded">
                  Bientôt disponible
                </span>
              )}
            </span>
            <Switch
              checked={settings.channels[ch.key]}
              onCheckedChange={() => !ch.comingSoon && toggleChannel(ch.key)}
              disabled={ch.comingSoon}
            />
          </div>
        ))}
      </div>

      <div className="glass-card rounded-xl p-5 space-y-4">
        <p className="font-medium">Paramètres d'expéditeur</p>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label>Email expéditeur</Label>
            <Input
              value={settings.senderEmail}
              onChange={(e) => onChange({ ...settings, senderEmail: e.target.value })}
              placeholder="noreply@edg.gn"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Nom SMS (11 car. max)</Label>
            <Input
              value={settings.senderSms}
              maxLength={11}
              onChange={(e) => onChange({ ...settings, senderSms: e.target.value })}
              placeholder="EDG"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Email de réponse</Label>
            <Input
              value={settings.replyTo}
              onChange={(e) => onChange({ ...settings, replyTo: e.target.value })}
              placeholder="support@edg.gn"
            />
          </div>
        </div>
        <Button onClick={onSave} size="sm" disabled={isSaving}>
          {isSaving ? "Sauvegarde…" : "Enregistrer"}
        </Button>
      </div>
    </div>
  );
}

/* ================================================================== */
/* Publication form dialog                                              */
/* ================================================================== */

function PublicationFormDialog({
  form,
  onChange,
  onSave,
  onClose,
  isEdit,
  channelSettings,
  isSaving,
}: {
  form: FormState;
  onChange: (f: FormState) => void;
  onSave: (asDraft: boolean) => void;
  onClose: () => void;
  isEdit: boolean;
  channelSettings: CommunicationSettings;
  isSaving?: boolean;
}) {
  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => onChange({ ...form, [k]: v });

  function toggleRole(r: Role) {
    const has = form.selectedRoles.includes(r);
    set("selectedRoles", has ? form.selectedRoles.filter((x) => x !== r) : [...form.selectedRoles, r]);
  }

  function toggleChannel(c: AnnouncementChannel) {
    const has = form.channels.includes(c);
    set("channels", has ? form.channels.filter((x) => x !== c) : [...form.channels, c]);
  }

  const availableChannels = CHANNEL_META.filter((ch) => {
    if (ch.key === "sms") return channelSettings.channels.sms;
    if (ch.key === "internal_notif") return channelSettings.channels.internal_notif;
    if (ch.key === "email") return channelSettings.channels.email;
    if (ch.key === "dashboard") return true;
    if (ch.key === "homepage") return channelSettings.channels.banner;
    return true;
  });

  const isAlert = form.priority === "critical" || form.priority === "high";

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 backdrop-blur-sm overflow-y-auto py-8 px-4">
      <div className="w-full max-w-2xl rounded-2xl border border-border/40 bg-background/95 backdrop-blur shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-border/40">
          <h2 className="font-semibold">{isEdit ? "Modifier la publication" : "Nouvelle publication"}</h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {isAlert && (
            <div className="flex items-center gap-2 rounded-lg bg-red-500/10 border border-red-500/30 p-3 text-sm text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" />
              Priorité critique — un bandeau d'alerte sera affiché jusqu'à clôture de cette publication.
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Titre *</Label>
            <Input value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Titre de la publication" />
          </div>

          <div className="space-y-1.5">
            <Label>Description *</Label>
            <Textarea value={form.description} onChange={(e) => set("description", e.target.value)} rows={4} placeholder="Contenu de l'annonce…" />
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Catégorie</Label>
              <Select value={form.category} onValueChange={(v) => set("category", v as AnnouncementCategory)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Priorité</Label>
              <Select value={form.priority} onValueChange={(v) => set("priority", v as AnnouncementPriority)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {PRIORITIES.map(([v, l]) => <SelectItem key={v} value={v}>{l}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Date de publication</Label>
              <Input type="datetime-local" value={form.publishedAt} onChange={(e) => set("publishedAt", e.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>Date d'expiration (optionnel)</Label>
              <Input type="datetime-local" value={form.expiresAt} onChange={(e) => set("expiresAt", e.target.value)} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label>Audience cible</Label>
            <Select value={form.audience} onValueChange={(v) => set("audience", v as AnnouncementAudience)}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="all">Tous (interne + externe)</SelectItem>
                <SelectItem value="internal">Interne uniquement</SelectItem>
                <SelectItem value="external">Externe uniquement (citoyens)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {form.audience !== "external" && (
            <div className="space-y-1.5">
              <Label className="flex items-center gap-2"><Users className="h-4 w-4" /> Rôles destinataires</Label>
              <div className="flex flex-wrap gap-2">
                {ROLES_LIST.map((r) => {
                  const active = form.selectedRoles.includes(r.value);
                  return (
                    <button
                      key={r.value}
                      onClick={() => toggleRole(r.value)}
                      className={`px-3 py-1 rounded-lg text-xs border transition-colors ${
                        active ? "bg-primary/20 border-primary/50 text-primary" : "border-border/50 text-muted-foreground hover:bg-muted/40"
                      }`}
                    >
                      {r.label}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>Canaux de diffusion *</Label>
            <div className="flex flex-wrap gap-2">
              {availableChannels.map((ch) => {
                const active = form.channels.includes(ch.key);
                const Icon = ch.icon;
                return (
                  <button
                    key={ch.key}
                    onClick={() => toggleChannel(ch.key)}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                      active ? "bg-primary/20 border-primary/50 text-primary" : "border-border/50 text-muted-foreground hover:bg-muted/40"
                    }`}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    {ch.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="flex gap-2 justify-end p-5 border-t border-border/40">
          <Button variant="ghost" onClick={onClose} disabled={isSaving}>Annuler</Button>
          <Button variant="outline" onClick={() => onSave(true)} disabled={isSaving}>
            <FileText className="h-4 w-4 mr-1.5" /> Enregistrer brouillon
          </Button>
          <Button onClick={() => onSave(false)} disabled={isSaving}>
            <Send className="h-4 w-4 mr-1.5" /> {isSaving ? "Publication…" : "Publier"}
          </Button>
        </div>
      </div>
    </div>
  );
}

/* ================================================================== */
/* Preview dialog                                                        */
/* ================================================================== */

function PreviewDialog({ announcement: a, onClose }: { announcement: Announcement; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="w-full max-w-xl rounded-2xl border border-border/40 bg-background/95 backdrop-blur shadow-2xl">
        <div className="flex items-center justify-between p-5 border-b border-border/40">
          <h2 className="font-semibold text-sm">Aperçu</h2>
          <button onClick={onClose}><X className="h-4 w-4 text-muted-foreground" /></button>
        </div>
        <div className="p-5 space-y-3">
          <div className="flex flex-wrap gap-2">
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${PRIORITY_COLORS[a.priority]}`}>
              {announcementPriorityLabels[a.priority]}
            </span>
            <span className="text-xs text-muted-foreground">{announcementCategoryLabels[a.category]}</span>
          </div>
          <h3 className="font-semibold">{a.title}</h3>
          <p className="text-sm text-muted-foreground leading-relaxed">{a.description}</p>
          <div className="flex flex-wrap gap-3 text-xs text-muted-foreground pt-2">
            <span>Publié le {new Date(a.publishedAt).toLocaleDateString("fr-FR")}</span>
            {a.expiresAt && <span>Expire le {new Date(a.expiresAt).toLocaleDateString("fr-FR")}</span>}
            <span>Par {a.authorName}</span>
          </div>
          <div className="flex flex-wrap gap-2 pt-1">
            {a.channels.map((ch) => {
              const meta = CHANNEL_META.find((c) => c.key === ch);
              if (!meta) return null;
              const Icon = meta.icon;
              return (
                <span key={ch} className="flex items-center gap-1.5 text-xs text-muted-foreground border border-border/40 rounded px-2 py-0.5">
                  <Icon className="h-3 w-3" />{meta.label}
                </span>
              );
            })}
          </div>
          <div className="grid grid-cols-3 gap-3 pt-2">
            {[
              { label: "Emails", value: a.metrics.emailsSent, icon: Mail },
              { label: "SMS", value: a.metrics.smsSent, icon: Smartphone },
              { label: "Vues", value: a.metrics.viewCount, icon: Eye },
            ].map((m) => (
              <div key={m.label} className="rounded-lg bg-muted/20 p-3 text-center">
                <m.icon className="h-4 w-4 mx-auto mb-1 text-muted-foreground" />
                <p className="text-lg font-bold">{m.value}</p>
                <p className="text-xs text-muted-foreground">{m.label}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
