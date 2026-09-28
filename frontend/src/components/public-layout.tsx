import { Link, useRouter, useRouterState } from "@tanstack/react-router";
import { ArrowLeft, ArrowUp, Menu, Moon, Sun, X, Phone, Mail, MapPin } from "lucide-react";
import { useState, useEffect, type ReactNode } from "react";
import { Logo } from "./logo";
import { Button } from "./ui/button";
import { cn } from "@/lib/utils";
import { useTheme } from "@/lib/use-theme";

const navLinks = [
  { to: "/", label: "Accueil" },
  { to: "/track", label: "Suivre mon ticket" },
];

export function PublicLayout({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const router = useRouter();
  const [dark, toggleDark, mounted] = useTheme();
  const canGoBack = pathname !== "/";
  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.history.back();
      return;
    }
    router.navigate({ to: "/", replace: true });
  };

  const [showScrollTop, setShowScrollTop] = useState(false);
  useEffect(() => {
    const onScroll = () => {
      const scrollable = document.documentElement.scrollHeight - window.innerHeight;
      setShowScrollTop(scrollable > 0 && window.scrollY >= scrollable / 2);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="flex min-h-dvh w-full max-w-[100vw] flex-col">
      <header className="sticky top-0 z-40 border-b border-border/40 bg-background/70 backdrop-blur-lg">
        <div className="mx-auto flex h-16 max-w-screen-2xl items-center px-4 sm:px-8 lg:px-12">

          {/* Bloc logo */}
          <div className="flex shrink-0 items-center gap-2">
            {canGoBack && (
              <button
                onClick={handleBack}
                className="flex items-center gap-1 rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
                aria-label="Retour"
              >
                <ArrowLeft className="h-4 w-4" />
              </button>
            )}
            <Link to="/" className="shrink-0">
              <Logo />
            </Link>
          </div>

          {/* Nav centrée — desktop */}
          <nav className="hidden flex-1 items-center justify-center gap-1 lg:flex">
            {navLinks.map((l) => {
              const active = l.to === "/" ? pathname === l.to : pathname.startsWith(l.to);
              return (
                <Link
                  key={l.to}
                  to={l.to}
                  className={cn(
                    "relative rounded-full px-4 py-2 text-sm font-medium transition-colors",
                    active
                      ? "text-primary"
                      : "text-foreground/65 hover:bg-foreground/5 hover:text-foreground",
                  )}
                >
                  {l.label}
                  {active && (
                    <span className="absolute bottom-0.5 left-1/2 h-0.5 w-4 -translate-x-1/2 rounded-full bg-primary" />
                  )}
                </Link>
              );
            })}
          </nav>

          {/* Actions droite — flex-1 pousse le contenu au bord droit sur mobile */}
          <div className="flex flex-1 items-center justify-end gap-1.5 sm:gap-2">
            <div className="hidden items-center gap-1 lg:flex">
              <button
                onClick={toggleDark}
                className="rounded-full p-2 text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
                aria-label="Thème"
              >
                <span suppressHydrationWarning>
                  {mounted
                    ? dark
                      ? <Sun className="h-4 w-4" />
                      : <Moon className="h-4 w-4" />
                    : <Moon className="h-4 w-4 opacity-0" />}
                </span>
              </button>

              {/* Séparateur vertical */}
              <span className="mx-1 h-5 w-px bg-border/60" />

              <Button asChild variant="ghost" size="sm" className="rounded-full px-4">
                <Link to="/login">Connexion</Link>
              </Button>
              <Button
                asChild
                size="sm"
                className="rounded-full gradient-primary px-4 text-background shadow-md shadow-primary/20"
              >
                <Link to="/register">S'inscrire</Link>
              </Button>
            </div>

            {/* Hamburger — mobile */}
            <button
              className="rounded-full p-2 text-foreground/70 hover:bg-foreground/5 hover:text-foreground lg:hidden"
              onClick={() => setOpen((v) => !v)}
              aria-label="Menu"
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Menu mobile déroulant */}
        {open && (
          <div className="border-t border-border/40 bg-background/95 backdrop-blur-lg lg:hidden">
            <nav className="mx-auto flex max-w-screen-2xl flex-col gap-0.5 px-3 py-3">
              {navLinks.map((l) => {
                const active = l.to === "/" ? pathname === l.to : pathname.startsWith(l.to);
                return (
                  <Link
                    key={l.to}
                    to={l.to}
                    onClick={() => setOpen(false)}
                    className={cn(
                      "flex items-center rounded-xl px-4 py-3 text-sm font-medium transition-colors",
                      active
                        ? "text-primary"
                        : "text-foreground/75 hover:bg-foreground/5 hover:text-foreground",
                    )}
                  >
                    {active && (
                      <span className="mr-2.5 h-1.5 w-1.5 rounded-full bg-primary" />
                    )}
                    {l.label}
                  </Link>
                );
              })}

              {/* Séparateur */}
              <div className="mx-1 my-2 border-t border-border/50" />

              {/* Actions */}
              <div className="flex items-center justify-between px-1 pb-1">
                <button
                  onClick={() => { toggleDark(); }}
                  className="flex items-center gap-2 rounded-xl px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:bg-foreground/5 hover:text-foreground"
                >
                  <span suppressHydrationWarning>
                    {mounted
                      ? dark
                        ? <Sun className="h-4 w-4" />
                        : <Moon className="h-4 w-4" />
                      : <Moon className="h-4 w-4 opacity-0" />}
                  </span>
                  <span>{dark ? "Mode clair" : "Mode sombre"}</span>
                </button>
              </div>

              <div className="grid grid-cols-2 gap-2 px-1 pb-1">
                <Button asChild variant="outline" className="h-11 rounded-full">
                  <Link to="/login" onClick={() => setOpen(false)}>Connexion</Link>
                </Button>
                <Button
                  asChild
                  className="h-11 rounded-full gradient-primary text-background"
                >
                  <Link to="/register" onClick={() => setOpen(false)}>S'inscrire</Link>
                </Button>
              </div>
            </nav>
          </div>
        )}
      </header>

      <main className="w-full flex-1 overflow-x-hidden">{children}</main>

      <footer className="border-t border-border/40 bg-card">
        {/* Corps principal du footer */}
        <div className="mx-auto max-w-screen-2xl px-4 py-10 sm:py-14 sm:px-8 lg:px-12">
          <div className="grid gap-8 lg:grid-cols-[2fr_1fr_1fr_1fr_1.6fr] lg:gap-10">

            {/* Colonne marque — pleine largeur sur mobile, 1re colonne sur lg */}
            <div className="flex flex-col gap-3">
              <Logo />
              <p className="max-w-[280px] text-sm leading-relaxed text-muted-foreground">
                La plateforme officielle de gestion des tickets de la Direction des Systèmes d'Information d'Électricité de Guinée.
              </p>
            </div>

            {/* Les 4 colonnes de liens :
                mobile  → 2×2 (Services | Plateforme sur row1, Liens | Contact sur row2)
                md      → 4 colonnes en une seule rangée
                lg      → "contents" : les enfants rejoignent directement le grid parent 5 cols */}
            <div className="grid grid-cols-2 gap-6 md:grid-cols-4 lg:contents">

              {/* Services */}
              <div>
                <h3 className="mb-3 text-xs font-semibold tracking-wider text-foreground uppercase">
                  Services
                </h3>
                <ul className="space-y-2">
                  {[
                    { label: "Espace employé", to: "/login" },
                    { label: "Suivre un ticket", to: "/track" },
                  ].map((l) => (
                    <li key={l.to}>
                      <Link
                        to={l.to}
                        className="text-sm text-muted-foreground transition-colors hover:text-primary"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Plateforme */}
              <div>
                <h3 className="mb-3 text-xs font-semibold tracking-wider text-foreground uppercase">
                  Plateforme
                </h3>
                <ul className="space-y-2">
                  {[
                    { label: "Connexion", to: "/login" },
                    { label: "Notifications", to: "/login" },
                    { label: "Tickets", to: "/login" },
                  ].map((l) => (
                    <li key={l.label}>
                      <Link
                        to={l.to}
                        className="text-sm text-muted-foreground transition-colors hover:text-primary"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Liens utiles */}
              <div>
                <h3 className="mb-3 text-xs font-semibold tracking-wider text-foreground uppercase">
                  Liens utiles
                </h3>
                <ul className="space-y-2">
                  {[
                    { label: "Conditions", to: "/" },
                    { label: "Confidentialité", to: "/" },
                  ].map((l) => (
                    <li key={l.label}>
                      <Link
                        to={l.to}
                        className="text-sm text-muted-foreground transition-colors hover:text-primary"
                      >
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Contact */}
              <div>
                <h3 className="mb-3 text-xs font-semibold tracking-wider text-foreground uppercase">
                  Contact
                </h3>
                <ul className="space-y-2.5">
                  <li className="flex items-start gap-2.5">
                    <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                    <a
                      href="tel:+22462611111"
                      className="text-sm text-muted-foreground transition-colors hover:text-primary"
                    >
                      +224 626 11 11 11
                    </a>
                  </li>
                  <li className="flex items-start gap-2.5">
                    <Mail className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                    <a
                      href="mailto:infos@edg.com.gn"
                      className="text-sm text-muted-foreground transition-colors hover:text-primary"
                    >
                      infos@edg.com.gn
                    </a>
                  </li>
                  <li className="flex items-start gap-2.5">
                    <MapPin className="mt-0.5 h-3.5 w-3.5 shrink-0 text-primary" />
                    <span className="text-sm text-muted-foreground leading-relaxed">
                      Immeuble Sankaran,<br />
                      Carrefour Chinois,<br />
                      Minière Dixinn
                    </span>
                  </li>
                </ul>
              </div>

            </div>
          </div>
        </div>

        {/* Barre de bas de page */}
        <div className="border-t border-border/40">
          <div className="mx-auto flex max-w-screen-2xl flex-col items-center justify-between gap-3 px-4 py-4 sm:flex-row sm:px-8 lg:px-12">
            <p className="text-xs text-muted-foreground">
              {new Date().getFullYear()} © Développé par EDG-SA.
            </p>
            <nav className="flex items-center gap-4">
              {["Termes", "Confidentialité", "Cookies"].map((item) => (
                <Link
                  key={item}
                  to="/"
                  className="text-xs text-muted-foreground transition-colors hover:text-primary"
                >
                  {item}
                </Link>
              ))}
            </nav>
          </div>
        </div>
      </footer>

      {/* Bouton retour en haut */}
      <button
        onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
        aria-label="Retour en haut"
        className={cn(
          "fixed bottom-6 right-6 z-50 grid h-11 w-11 place-items-center rounded-full bg-primary text-background shadow-lg shadow-primary/30 transition-all duration-300",
          showScrollTop
            ? "translate-y-0 opacity-100 pointer-events-auto"
            : "translate-y-4 opacity-0 pointer-events-none",
        )}
      >
        <ArrowUp className="h-5 w-5" />
      </button>
    </div>
  );
}
