import { Link, useRouter, useRouterState } from "@tanstack/react-router";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowUp,
  Bell,
  ChevronsUpDown,
  Inbox,
  LayoutDashboard,
  LogOut,
  Menu,
  Plus,
  Settings,
  BarChart3,
  Users2,
  Users,
  BookOpen,
  ListChecks,
  Building2,
  Sun,
  Moon,
  X,
  PanelLeftClose,
  PanelLeftOpen,
  Activity,
  History,
  Ticket,
  Timer,
  ShieldAlert,
  Megaphone,
  Database,
  Network,
  Layers,
  Library,
  Settings2,
  GitBranch,
  Flag,
  FolderTree,
  Compass,
  AlertTriangle,
  Send,
  Search,
} from "lucide-react";
import { useState, useRef, useCallback, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchNotifications } from "@/lib/api/notifications";
import { Logo } from "./logo";
import { NotificationPanel } from "./notification-panel";
import { cn } from "@/lib/utils";
import { useRole, useUser, getRefreshToken, clearSession, getInitials, roleLabels, AUTH_DISABLED } from "@/lib/session";
import { logoutUser } from "@/lib/api/auth";
import { buildAvatarUrl } from "@/lib/api/accounts";
import { useRealtimeStatus } from "@/providers/realtime-provider";
import { useTheme } from "@/lib/use-theme";
import type { Role } from "@/lib/mock-data";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "./ui/dropdown-menu";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

type NavItem = {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
  roles: Role[];
  group?: string;
  /** Paramètres de recherche optionnels — deep-link vers un filtre/onglet déjà existant sur la page cible. */
  search?: Record<string, string>;
  /** Item préparé mais pas encore fonctionnel (ex. "Tickets transmis") — affiché grisé, non cliquable. */
  disabled?: boolean;
};

const HEADER_ROLE_LABEL: Record<Role, string> = {
  public:              "PUBLIC",
  user:                "EMPLOYÉ",
  "agent-support":     "AGENT SUPPORT",
  "chief-service":     "CHEF DE SERVICE",
  "chief-departement": "CHEF DE DÉPARTEMENT",
  director:            "DIRECTION",
  admin:               "ADMINISTRATION",
};

function resolveBackFallback(pathname: string, role: Role): string {
  if (pathname.startsWith("/app/supervision/tickets/")) return "/app/supervision";
  if (pathname.startsWith("/app/queue/tickets/")) return "/app/queue";
  if (pathname.startsWith("/app/transmitted/tickets/")) return "/app/transmitted";
  if (pathname.startsWith("/app/history/tickets/")) return "/app/history";
  if (pathname.startsWith("/app/my-tickets/tickets/")) return "/app/my-tickets";
  if (pathname.startsWith("/app/chief-inbox/tickets/")) return "/app/chief-inbox";
  if (pathname.startsWith("/app/department-inbox/tickets/")) return "/app/department-inbox";
  if (pathname.startsWith("/app/direction/tickets/")) return "/app/direction";
  if (pathname.startsWith("/app/dg/tickets/")) return "/app/dg";
  if (pathname.startsWith("/app/sla-center/tickets/")) return "/app/sla-center";
  if (pathname.startsWith("/app/admin/tickets/")) return role === "admin" ? "/app/admin/users" : "/app";
  if (pathname.startsWith("/app/history")) return "/app/history";
  if (pathname.startsWith("/app/requests/")) return "/app/requests";
  if (pathname.startsWith("/app/requests")) return "/app";
  if (pathname.startsWith("/app/my-tickets")) return "/app";
  if (pathname.startsWith("/app/queue")) return "/app";
  if (pathname.startsWith("/app/transmitted")) return "/app";
  if (pathname.startsWith("/app/chief-inbox")) return "/app";
  if (pathname.startsWith("/app/department-inbox")) return "/app";
  if (pathname.startsWith("/app/direction")) return "/app";
  if (pathname.startsWith("/app/supervision")) return "/app";
  if (pathname.startsWith("/app/reports")) return "/app";
  if (pathname.startsWith("/app/dg")) return "/app";
  if (pathname.startsWith("/app/admin")) return role === "admin" ? "/app/admin/users" : "/app";
  return "/app";
}

const navItems: NavItem[] = [
  // ── Mon espace personnel (tous les rôles — chaque acteur garde son espace propre) ──
  { to: "/app",                  label: "Accueil",          icon: LayoutDashboard, roles: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Mon espace" },
  { to: "/app/requests",         label: "Mes tickets",      icon: Inbox,   roles: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Mon espace" },
  { to: "/app/history", label: "Historique",        icon: History, roles: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Mon espace" },

  // ── Mon travail — socle commun de traitement, identique pour tous les rôles
  //    opérationnels (le traitement n'est plus différenciateur, cf. philosophie
  //    du workflow collaboratif dynamique). "Ma boîte de traitement" pointe vers
  //    la page où CE rôle traite concrètement des tickets aujourd'hui — pour le
  //    directeur c'est déjà /app/direction (arbitrage/résolution), pas my-tickets.
  { to: "/app/my-tickets",  label: "Ma boîte de traitement", icon: Ticket,       roles: ["agent-support", "chief-service", "chief-departement", "admin"], group: "Mon travail" },
  { to: "/app/direction",   label: "Ma boîte de traitement", icon: Ticket,       roles: ["director"],                                                     group: "Mon travail" },
  { to: "/app/queue",       label: "File d'attente",         icon: ListChecks,   roles: ["agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Mon travail" },
  { to: "/app/transmitted", label: "Tickets transmis", icon: Send, roles: ["agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Mon travail" },

  // ── Pilotage — supervision/répartition, distinct du traitement personnel ──
  { to: "/app/supervision", label: "Supervision", icon: ShieldAlert, roles: ["chief-service", "chief-departement", "director"], group: "Pilotage" },
  { to: "/app/direction",        label: "Escalades", icon: AlertTriangle, roles: ["director"],          group: "Pilotage", search: { section: "escalades-l3" } },
  { to: "/app/strategic-dashboard", label: "Tableau de bord DSI", icon: Compass, roles: ["director"],   group: "Pilotage" },

  // ── Analyse — rapports/statistiques, séparé du pilotage opérationnel ──────
  // Onglet "Rapports" masqué sur demande (2026-08-16) pour les 3 rôles
  // (chief-departement, director, admin) — la route /app/reports et son
  // composant restent intacts, uniquement retirés de la navigation. Changement
  // réversible : réajouter les 3 entrées ci-dessous pour réactiver.
  // { to: "/app/reports", label: "Rapports Département", icon: BarChart3, roles: ["chief-departement"],  group: "Analyse" },
  // { to: "/app/reports", label: "Rapports Direction",   icon: BarChart3, roles: ["director"],           group: "Analyse" },
  // { to: "/app/reports", label: "Rapports",             icon: BarChart3, roles: ["admin"],               group: "Analyse" },

  // ── Admin — Utilisateurs ──────────────────────────────────────────────────
  { to: "/app/admin/users", label: "Utilisateurs & Rôles", icon: Users2, roles: ["admin"], group: "Utilisateurs" },

  // ── Admin — Organisation ──────────────────────────────────────────────────
  { to: "/app/admin/org",        label: "Organigramme",      icon: GitBranch, roles: ["admin"], group: "Organisation" },
  { to: "/app/admin/directions", label: "Directions",        icon: Network,   roles: ["admin"], group: "Organisation" },
  { to: "/app/admin/departments", label: "Départements",      icon: FolderTree, roles: ["admin"], group: "Organisation" },
  { to: "/app/admin/units",      label: "Services & Unités", icon: Layers,    roles: ["admin"], group: "Organisation" },

  // ── Admin — Gestion tickets ───────────────────────────────────────────────
  { to: "/app/admin/references", label: "Types de tickets", icon: Database,  roles: ["admin"], group: "Gestion tickets" },

  // ── Admin — SLA & Escalades ───────────────────────────────────────────────
  { to: "/app/admin/sla",        label: "SLA & Politiques",    icon: Timer, roles: ["admin"], group: "SLA & Escalades" },
  { to: "/app/admin/priorities", label: "Niveaux de priorité", icon: Flag,  roles: ["admin"], group: "SLA & Escalades" },

  // ── Admin — Audit & Traçabilité ───────────────────────────────────────────
  { to: "/app/admin/ticket-trace", label: "Traçabilité ticket", icon: Search, roles: ["admin"], group: "Audit & Traçabilité" },

  // ── Admin — Système ───────────────────────────────────────────────────────
  { to: "/app/admin/communication", label: "Communication",         icon: Megaphone, roles: ["admin"], group: "Système" },
  { to: "/app/admin/knowledge",     label: "Base de connaissances", icon: Library,   roles: ["admin"], group: "Système" },

  // ── Ressources (tous) ─────────────────────────────────────────────────────
  { to: "/app/knowledge",    label: "Base de connaissance", icon: BookOpen, roles: ["user", "agent-support", "chief-service", "chief-departement", "director"], group: "Ressources" },
  { to: "/app/notifications", label: "Notifications",       icon: Bell,     roles: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Ressources" },
  { to: "/app/profile",       label: "Profil",              icon: Settings, roles: ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"], group: "Ressources" },
];

export function AppLayout({ children }: { children: ReactNode }) {
  const [role, setRole] = useRole();
  const sessionUser = useUser();
  const displayName = sessionUser?.firstname
    ? `${sessionUser.firstname} ${sessionUser.name}`
    : sessionUser?.name;
  const realtimeStatus = useRealtimeStatus();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const currentSearch = useRouterState({ select: (s) => s.location.search }) as Record<string, unknown>;
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [dark, toggleDark, mounted] = useTheme();
  const [showScrollTop, setShowScrollTop] = useState(false);
  const mainRef = useRef<HTMLElement>(null);

  const handleMainScroll = useCallback(() => {
    const el = mainRef.current;
    if (!el) return;
    const scrollable = el.scrollHeight - el.clientHeight;
    setShowScrollTop(scrollable > 0 && el.scrollTop >= scrollable / 2);
  }, []);
  const [notifPanelOpen, setNotifPanelOpen] = useState(false);

  const { data: notifData } = useQuery({
    queryKey: ["notifications", sessionUser?.id],
    queryFn: () => fetchNotifications({ meId: sessionUser!.id, unread: true, limit: 1 }),
    enabled: !!sessionUser?.id,
    staleTime: 30_000,
    // Pas de refetchInterval : notification.created/read (SSE) invalident déjà
    // ["notifications"] en temps réel (voir invalidation-map.ts) — un polling
    // en parallèle double la charge réseau sans gagner en fraîcheur.
  });
  const unreadCount = notifData?.total ?? 0;

  const canGoBack = pathname !== "/app";
  const backFallback = resolveBackFallback(pathname, role);
  const handleBack = useCallback(() => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.history.back();
      return;
    }
    router.navigate({ to: backFallback as never, replace: true });
  }, [backFallback, router]);

  const items = navItems.filter((i) => i.roles.includes(role));
  const grouped = items.reduce<Record<string, NavItem[]>>((acc, i) => {
    const key = i.group ?? "Principal";
    (acc[key] = acc[key] || []).push(i);
    return acc;
  }, {});
  const groupKeys = Object.keys(grouped);

  // Sélectionne uniquement l'item le plus spécifique qui correspond au pathname
  // (évite que /app/requests soit actif en même temps que /app/requests/history).
  const bestTo = items.reduce<string | null>((best, item) => {
    const matches =
      pathname === item.to ||
      (item.to !== "/app" && pathname.startsWith(item.to + "/"));
    if (!matches) return best;
    return !best || item.to.length > best.length ? item.to : best;
  }, null);

  // Plusieurs items ("Escalades"…) pointent volontairement
  // vers la même route qu'un autre item (deep-link ?tab=/?status=/
  // ?section= vers un onglet/filtre déjà existant) — départager avec le pathname
  // seul allumerait tous les items partageant ce "to" en même temps. On ne
  // retient donc actif que celui dont les paramètres de recherche (s'il en a)
  // correspondent exactement à l'URL courante ; à défaut, l'item "par défaut"
  // (sans search) de cette route.
  const matchesSearch = (item: NavItem) =>
    !item.search || Object.entries(item.search).every(([k, v]) => String(currentSearch?.[k] ?? "") === v);
  const sameToItems = items.filter((i) => i.to === bestTo);
  const activeItem =
    sameToItems.find((i) => i.search && matchesSearch(i)) ??
    sameToItems.find((i) => !i.search) ??
    null;
  const activeNavKey = activeItem ? `${activeItem.to}-${activeItem.label}` : null;

  return (
    <TooltipProvider delayDuration={120}>
      <div className="h-dvh overflow-hidden">

        {/* ── Sidebar : icon-only on md–xl, expandable on xl+ ── */}
        <aside
          className={cn(
            "fixed left-0 top-0 z-30 hidden md:flex h-dvh flex-col border-r border-border/40 bg-sidebar transition-[width] duration-200",
            // md–xl : always 72 px (icon rail)
            "w-[72px]",
            // xl+ : 264 px when not collapsed
            !collapsed && "xl:w-[264px]",
          )}
        >
          {/* Logo + collapse toggle */}
          <div
            className={cn(
              "flex h-16 shrink-0 items-center border-b border-border/40 bg-sidebar/80 px-3",
              "justify-center",
              !collapsed && "xl:justify-between xl:px-4",
            )}
          >
            <Link
              to="/app"
              className={cn(
                "shrink-0 overflow-hidden",
                "max-w-[44px]",
                !collapsed && "xl:max-w-none",
              )}
            >
              <Logo showText={!collapsed} />
            </Link>

            {/* Close button — xl+ only */}
            {!collapsed && (
              <button
                onClick={() => setCollapsed(true)}
                className="hidden xl:flex rounded-lg p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                aria-label="Réduire"
              >
                <PanelLeftClose className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* Open button when collapsed — xl+ only */}
          {collapsed && (
            <div className="hidden xl:flex justify-center border-b border-border/40 bg-sidebar/80 py-2">
              <button
                onClick={() => setCollapsed(false)}
                className="rounded-lg p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                aria-label="Étendre"
              >
                <PanelLeftOpen className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Nav groups */}
          <nav className="flex-1 overflow-y-auto overscroll-y-none px-2 py-3">
            {groupKeys.map((group, groupIdx) => {
              const list = grouped[group];
              return (
                <div
                  key={group}
                  className={cn(groupIdx > 0 && "mt-1 border-t border-border/25 pt-3")}
                >
                  {/* Group label — visible on xl+ when expanded */}
                  {!collapsed && (
                    <div className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/50 hidden xl:block">
                      {group}
                    </div>
                  )}

                  <ul className="space-y-0.5">
                    {list.map((item) => {
                      const active = !item.disabled && activeNavKey === `${item.to}-${item.label}`;

                      const link = item.disabled ? (
                        <span
                          className={cn(
                            "group relative flex cursor-not-allowed items-center rounded-xl py-2.5 text-sm font-medium opacity-45",
                            "justify-center px-2",
                            !collapsed && "xl:justify-start xl:gap-3 xl:px-3",
                            "text-foreground/70",
                          )}
                        >
                          <item.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                          {!collapsed && (
                            <span className="hidden xl:block truncate">{item.label}</span>
                          )}
                        </span>
                      ) : (
                        <Link
                          to={item.to}
                          search={item.search}
                          className={cn(
                            "group relative flex items-center rounded-xl py-2.5 text-sm font-medium transition-colors",
                            // Default: icon-only centered (md always, xl when collapsed)
                            "justify-center px-2",
                            // xl+ expanded: icon + label
                            !collapsed && "xl:justify-start xl:gap-3 xl:px-3",
                            active
                              ? "bg-primary text-background font-bold"
                              : "text-foreground/70 hover:bg-foreground/5 hover:text-foreground",
                          )}
                        >
                          <item.icon
                            className={cn(
                              "h-4 w-4 shrink-0 transition-colors",
                              active ? "text-background" : "text-muted-foreground group-hover:text-foreground/80",
                            )}
                          />
                          {/* Label: only rendered when not collapsed; hidden on md–xl */}
                          {!collapsed && (
                            <span className="hidden xl:block truncate">{item.label}</span>
                          )}
                        </Link>
                      );

                      return (
                        <li key={`${item.to}-${item.label}`}>
                          <Tooltip>
                            <TooltipTrigger asChild>{link}</TooltipTrigger>
                            <TooltipContent side="right" className="text-xs">
                              {item.disabled ? `${item.label} — bientôt disponible` : item.label}
                            </TooltipContent>
                          </Tooltip>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              );
            })}
          </nav>

          {/* User info + role switcher */}
          <div className="shrink-0 border-t border-border/30 p-2 xl:p-3">
            <RoleSwitcher role={role} onChange={setRole} collapsed={collapsed} userName={displayName} userAvatar={sessionUser?.avatar} />
          </div>
        </aside>

        {/* ── Mobile drawer (< md only) ── */}
        {mobileOpen && (
          <div className="fixed inset-0 z-50 md:hidden">
            <div
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
            />
            <aside className="absolute left-0 top-0 flex h-full w-[82%] max-w-xs flex-col bg-sidebar">
              <div className="flex h-16 shrink-0 items-center justify-between border-b border-border/30 px-5">
                <Logo />
                <button
                  onClick={() => setMobileOpen(false)}
                  className="rounded-xl p-2 text-muted-foreground hover:bg-foreground/5"
                  aria-label="Fermer"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <nav className="flex-1 overflow-y-auto overscroll-y-none px-3 py-4">
                {groupKeys.map((group, groupIdx) => {
                  const list = grouped[group];
                  return (
                    <div
                      key={group}
                      className={cn(groupIdx > 0 && "mt-1 border-t border-border/25 pt-3")}
                    >
                      <div className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground/50">
                        {group}
                      </div>
                      <ul className="space-y-0.5">
                        {list.map((item) => {
                          const active = !item.disabled && activeNavKey === `${item.to}-${item.label}`;
                          return (
                            <li key={`${item.to}-${item.label}`}>
                              {item.disabled ? (
                                <span className="flex cursor-not-allowed items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium text-foreground/70 opacity-45">
                                  <item.icon className="h-4 w-4 shrink-0 text-muted-foreground" />
                                  {item.label}
                                </span>
                              ) : (
                                <Link
                                  to={item.to}
                                  search={item.search}
                                  onClick={() => setMobileOpen(false)}
                                  className={cn(
                                    "flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition-colors",
                                    active
                                      ? "bg-primary text-background font-bold"
                                      : "text-foreground/70 hover:bg-foreground/5 hover:text-foreground",
                                  )}
                                >
                                  <item.icon
                                    className={cn(
                                      "h-4 w-4 shrink-0",
                                      active ? "text-background" : "text-muted-foreground",
                                    )}
                                  />
                                  {item.label}
                                </Link>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  );
                })}
              </nav>

            </aside>
          </div>
        )}

        {/* ── Main content ── */}
        <div
          className={cn(
            "flex h-dvh min-w-0 flex-col overflow-x-hidden transition-[padding] duration-200",
            // Tablet (md–xl): 72 px sidebar always
            "md:pl-[72px]",
            // Desktop (xl+): 264 px when sidebar expanded
            !collapsed && "xl:pl-[264px]",
          )}
        >
          {/* Top header */}
          <header className="sticky top-0 z-20 flex h-16 shrink-0 items-center border-b border-border/60 bg-background/95">
            <div className="flex h-full w-full items-center justify-between px-3 md:px-5">

              {/* ── LEFT zone ── */}
              <div className="flex items-center gap-2">
                {/* Hamburger — mobile only (< md) */}
                <button
                  className="flex h-10 w-10 items-center justify-center rounded-xl text-muted-foreground transition-colors hover:bg-muted hover:text-foreground active:scale-95 md:hidden"
                  onClick={() => setMobileOpen(true)}
                  aria-label="Ouvrir le menu"
                >
                  <Menu className="h-[22px] w-[22px]" />
                </button>

                {/* Logo + brand — mobile */}
                <Link
                  to="/app"
                  className="flex items-center gap-2 md:hidden"
                  aria-label="Accueil"
                >
                  <Logo size="sm" showText={false} />
                  <div className="flex items-center gap-1.5">
                    <span className="text-sm font-bold tracking-tight text-foreground">EDG-SUP</span>
                  </div>
                </Link>

                {/* Desktop: bouton retour uniquement (la marque est déjà dans la sidebar) */}
                {canGoBack && (
                  <div className="hidden md:flex items-center gap-3">
                    <button
                      onClick={handleBack}
                      className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                      aria-label="Retour"
                    >
                      <ArrowLeft className="h-4 w-4" />
                      <span>Retour</span>
                    </button>
                  </div>
                )}
              </div>

              {/* ── RIGHT zone ── */}
              <div className="flex items-center gap-0.5 md:gap-1">
                {/* Theme toggle — tablet/desktop only */}
                <button
                  onClick={toggleDark}
                  className="hidden rounded-full p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground md:flex"
                  aria-label="Basculer le thème"
                >
                  <span suppressHydrationWarning>
                    {mounted
                      ? dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />
                      : <Moon className="h-4 w-4 opacity-0" />}
                  </span>
                </button>

                {/* Indicateur connexion temps réel */}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span
                      className={cn(
                        "hidden md:flex h-2 w-2 rounded-full transition-colors",
                        realtimeStatus === "connected"
                          ? "bg-emerald-400"
                          : realtimeStatus === "connecting"
                            ? "bg-amber-300 animate-pulse"
                            : "bg-muted-foreground/30",
                      )}
                      aria-label={
                        realtimeStatus === "connected"
                          ? "Temps réel actif"
                          : realtimeStatus === "connecting"
                            ? "Connexion en cours…"
                            : "Hors ligne"
                      }
                    />
                  </TooltipTrigger>
                  <TooltipContent side="bottom" className="text-xs">
                    {realtimeStatus === "connected"
                      ? "Mises à jour en temps réel actives"
                      : realtimeStatus === "connecting"
                        ? "Connexion temps réel en cours…"
                        : "Connexion temps réel inactive"}
                  </TooltipContent>
                </Tooltip>

                {/* Notifications */}
                <button
                  onClick={() => setNotifPanelOpen(true)}
                  className="relative flex h-10 w-10 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label={unreadCount > 0 ? `${unreadCount} notifications non lues` : "Notifications"}
                >
                  <Bell className="h-4 w-4" />
                  {unreadCount > 0 && (
                    unreadCount > 9 ? (
                      <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-destructive px-1 text-[9px] font-bold text-white ring-2 ring-background">
                        9+
                      </span>
                    ) : (
                      <span className="absolute -right-0.5 -top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-destructive text-[9px] font-bold text-white ring-2 ring-background">
                        {unreadCount}
                      </span>
                    )
                  )}
                </button>

                <span className="mx-0.5 h-5 w-px bg-border md:mx-1" />

                {/* Profile dropdown */}
                <DropdownMenu>
                  <DropdownMenuTrigger className="flex items-center gap-2 rounded-full py-1 pl-1 pr-1 transition-colors hover:bg-muted md:pr-3">
                    <div className="grid h-8 w-8 shrink-0 place-items-center rounded-full overflow-hidden bg-primary/10 text-[11px] font-bold text-primary ring-2 ring-primary/20">
                      {sessionUser?.avatar ? (
                        <img
                          src={buildAvatarUrl(sessionUser.avatar)}
                          alt={displayName ?? sessionUser.name}
                          className="h-full w-full object-cover"
                        />
                      ) : (
                        sessionUser ? getInitials(displayName ?? sessionUser.name) : "ED"
                      )}
                    </div>
                    <div className="hidden text-left md:block">
                      <div className="text-sm font-semibold leading-none text-foreground">
                        {displayName || "Utilisateur EDG"}
                      </div>
                    </div>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56">
                    <DropdownMenuLabel>
                      <div className="font-semibold">{displayName || "Mon compte"}</div>
                      {sessionUser?.email && (
                        <div className="text-[11px] font-normal text-muted-foreground truncate">{sessionUser.email}</div>
                      )}
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem asChild>
                      <Link to="/app/profile">Profil & Paramètres</Link>
                    </DropdownMenuItem>
                    <DropdownMenuItem asChild>
                      <Link to="/app/notifications">Notifications</Link>
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem
                      className="text-destructive focus:text-destructive cursor-pointer"
                      onClick={async () => {
                        const rt = getRefreshToken();
                        if (rt) {
                          try { await logoutUser(rt); } catch { /* best-effort */ }
                        }
                        clearSession();
                        router.navigate({ to: "/" });
                      }}
                    >
                      <LogOut className="mr-2 h-4 w-4" />
                      Déconnexion
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>

            </div>
          </header>

          {/* Page content */}
          <main
            ref={mainRef}
            onScroll={handleMainScroll}
            className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden overscroll-y-none"
          >
            <div className="mx-auto w-full max-w-7xl px-4 py-5 pb-[calc(8rem+env(safe-area-inset-bottom))] sm:px-6 sm:py-6 md:pb-8">
              {children}
            </div>

            {/* Bouton retour en haut */}
            <AnimatePresence>
              {showScrollTop && (
                <motion.button
                  className="fixed bottom-20 right-5 z-40 md:bottom-6 md:right-6 grid h-11 w-11 place-items-center rounded-full gradient-primary text-primary-foreground shadow-lg shadow-primary/40 hover:scale-110 transition-transform duration-150"
                  initial={{ opacity: 0, scale: 0.3, y: 24 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.3, y: 24 }}
                  transition={{ type: "spring", stiffness: 380, damping: 18 }}
                  onClick={() => mainRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
                  aria-label="Retour en haut"
                >
                  <ArrowUp className="h-5 w-5" />
                </motion.button>
              )}
            </AnimatePresence>
          </main>

          {/* ── Mobile bottom nav (< md only) ── */}
          <nav className="fixed bottom-[calc(0.75rem+env(safe-area-inset-bottom))] left-3 right-3 z-30 md:hidden">
            <div className="glass-strong flex items-center justify-around rounded-2xl px-2 py-2">
              {(role === "director"
                  ? [
                      { to: "/app",              icon: LayoutDashboard, label: "Accueil" },
                      { to: "/app/direction",    icon: Building2,       label: "Direction", primary: true },
                      { to: "/app/reports",      icon: BarChart3,       label: "Rapports" },
                      { to: "/app/notifications", icon: Bell,           label: "Alertes" },
                      { to: "/app/profile",      icon: Settings,        label: "Profil" },
                    ]
                  : role === "chief-service"
                    ? [
                        { to: "/app/queue",         icon: ListChecks,      label: "Tickets" },
                        { to: "/app/my-tickets",    icon: Ticket,          label: "Ma boîte", primary: true },
                        { to: "/app/notifications", icon: Bell,            label: "Alertes" },
                        { to: "/app/profile",       icon: Settings,        label: "Profil" },
                      ]
                    : role === "chief-departement"
                      ? [
                          { to: "/app/queue",              icon: ListChecks,      label: "File att." },
                          { to: "/app/supervision",       icon: ShieldAlert,     label: "Superviser" },
                          { to: "/app/my-tickets",        icon: Ticket,          label: "Ma boîte", primary: true },
                          { to: "/app/notifications",     icon: Bell,            label: "Alertes" },
                          { to: "/app/profile",           icon: Settings,        label: "Profil" },
                        ]
                    : role === "agent-support"
                      ? [
                          { to: "/app/queue",         icon: ListChecks,        label: "File att." },
                          { to: "/app/my-tickets",    icon: Ticket,            label: "Mes tickets", primary: true },
                          { to: "/app/notifications", icon: Bell,              label: "Alertes" },
                          { to: "/app/profile",       icon: Settings,          label: "Profil" },
                        ]
                      : role === "admin"
                        ? [
                            { to: "/app",                icon: LayoutDashboard, label: "Accueil" },
                            { to: "/app/admin/users",    icon: Users2,          label: "Utilisateurs", primary: true },
                            { to: "/app/admin/logs",     icon: Activity,        label: "Journaux" },
                            { to: "/app/notifications",  icon: Bell,            label: "Alertes" },
                            { to: "/app/profile",        icon: Settings,        label: "Profil" },
                          ]
                        : [
                            { to: "/app",              icon: LayoutDashboard, label: "Accueil" },
                            { to: "/app/requests",     icon: Inbox,           label: "Tickets" },
                            { to: "/app/new",          icon: Plus,            label: "Créer", primary: true },
                            { to: "/app/notifications", icon: Bell,           label: "Alertes" },
                            { to: "/app/profile",      icon: Settings,        label: "Profil" },
                          ]
              ).map((i) => {
                const active =
                  i.to === "/app" ? pathname === i.to : pathname.startsWith(i.to);
                return (
                  <Link
                    key={i.to}
                    to={i.to}
                    className={cn(
                      "flex min-w-0 flex-1 flex-col items-center gap-1 rounded-xl px-1 py-1.5 text-[10px] font-medium transition-colors",
                      i.primary ? "text-white" : active ? "text-primary" : "text-muted-foreground",
                    )}
                  >
                    <span
                      className={cn(
                        "relative grid place-items-center rounded-xl transition-all",
                        i.primary
                          ? "h-10 w-10 gradient-primary shadow-lg shadow-primary/40"
                          : active
                            ? "h-8 w-8 bg-primary/12"
                            : "h-8 w-8",
                      )}
                    >
                      <i.icon className={cn(i.primary ? "h-5 w-5" : "h-4 w-4")} />
                      {i.to === "/app/notifications" && unreadCount > 0 && (
                        <span className="absolute -right-1 -top-1 flex h-3.5 min-w-3.5 items-center justify-center rounded-full bg-destructive px-0.5 text-[8px] font-bold text-white ring-1 ring-background">
                          {unreadCount > 9 ? "9+" : unreadCount}
                        </span>
                      )}
                    </span>
                    <span className="truncate leading-none">{i.label}</span>
                  </Link>
                );
              })}
            </div>
          </nav>
        </div>
      </div>
      <NotificationPanel
        open={notifPanelOpen}
        onClose={() => setNotifPanelOpen(false)}
        meId={sessionUser?.id}
        role={role}
      />
    </TooltipProvider>
  );
}

function RoleSwitcher({
  role,
  onChange,
  collapsed,
  userName,
  userAvatar,
}: {
  role: Role;
  onChange: (r: Role) => void;
  collapsed: boolean;
  userName?: string;
  userAvatar?: string;
}) {
  const roles: Role[] = ["user", "agent-support", "chief-service", "chief-departement", "director", "admin"];
  const initials = userName ? getInitials(userName) : role.slice(0, 2).toUpperCase();

  const avatar = (
    <div className="grid h-7 w-7 shrink-0 place-items-center overflow-hidden rounded-lg bg-primary text-[11px] font-bold text-background">
      {userAvatar ? (
        <img src={buildAvatarUrl(userAvatar)} alt={userName} className="h-full w-full object-cover" />
      ) : initials}
    </div>
  );

  const label = !collapsed && (
    <div className="hidden xl:flex min-w-0 flex-1 items-center gap-1">
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium">{userName || "Utilisateur"}</div>
        <div className="truncate text-[11px] text-muted-foreground">{roleLabels[role]}</div>
      </div>
    </div>
  );

  // En production (auth réelle), le rôle vient du JWT — pas de switcher
  if (!AUTH_DISABLED) {
    return (
      <div
        className={cn(
          "flex w-full items-center rounded-xl bg-card/60 py-2.5",
          "justify-center px-2",
          !collapsed && "xl:justify-start xl:gap-2.5 xl:px-3",
        )}
      >
        {avatar}
        {label}
      </div>
    );
  }

  // Dev uniquement : dropdown de bascule de rôle
  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className={cn(
          "flex w-full items-center rounded-xl bg-card/60 py-2.5 text-left text-sm transition-colors hover:bg-card",
          "justify-center px-2",
          !collapsed && "xl:justify-start xl:gap-2.5 xl:px-3",
        )}
      >
        {avatar}
        {!collapsed && (
          <div className="hidden xl:flex min-w-0 flex-1 items-center gap-1">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{userName || "Utilisateur"}</div>
                  </div>
            <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground/60" />
          </div>
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" side="top" className="w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">
          Basculer de rôle (dev)
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        {roles.map((r) => (
          <DropdownMenuItem
            key={r}
            onClick={() => onChange(r)}
            className="justify-between"
          >
            {roleLabels[r]}
            {role === r && (
              <span className="h-1.5 w-1.5 rounded-full bg-primary" />
            )}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
