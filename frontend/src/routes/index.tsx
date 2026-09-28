import { createFileRoute, Link } from "@tanstack/react-router";
import { PublicLayout } from "@/components/public-layout";
import { Button } from "@/components/ui/button";
import { GlassCard } from "@/components/glass-card";
import { motion, Reveal, Floating, fadeUp, stagger } from "@/components/motion-primitives";
import { DEFAULT_CONFIG } from "@/lib/homepage-config";
import type { SectionConfig } from "@/lib/homepage-config";
// Décâblage 2026-09-22 : fetchHomepageConfig / fetchSlides ne sont plus appelés
// depuis cette page (voir le commentaire dans Home()). Les fonctions restent
// disponibles dans @/lib/api/homepage pour un recâblage ultérieur.
import type { HomepageSlide } from "@/lib/api/homepage";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bolt,
  CheckCircle2,
  Clock,
  FilePlus,
  FileText,
  HeartHandshake,
  Search,
  ShieldCheck,
  Users,
  AlertTriangle,
  Megaphone,
  ChevronLeft,
  ChevronRight,
  Wrench,
  Shield,
  BookOpen,
  Zap,
  Bell,
  Info,
  History,
} from "lucide-react";
import { useState, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { fetchActiveDirectionsCount } from "@/lib/api/directions-units";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "EDG Support — Espace employé EDG" },
      {
        name: "description",
        content:
          "Plateforme interne de gestion des tickets pour les employés d'Électricité de Guinée. Soumettez, suivez et résolvez vos incidents.",
      },
      { property: "og:title", content: "EDG Support" },
      {
        property: "og:description",
        content: "L'espace numérique des employés EDG — tickets, suivi, support, en un seul endroit.",
      },
    ],
  }),
  component: Home,
});

// ══════════════════════════════════════════════════════════════════════════════
// Sections extraites — chacune est un composant autonome et statique
// ══════════════════════════════════════════════════════════════════════════════

function MissionBand({ text }: { text: string }) {
  return (
    <section className="mx-auto mt-8 max-w-3xl px-4 text-center sm:mt-14 sm:px-6">
      <Reveal>
        <div className="space-y-4">
          {/* <div className="inline-flex items-center gap-2 rounded-full border border-primary/25 bg-primary/8 px-3 py-1 text-xs font-medium text-primary">
            <Sparkles className="h-3.5 w-3.5" />
            Notre mission
          </div> */}
          <p className="text-base leading-relaxed text-muted-foreground sm:text-lg">
            {text}
          </p>
          <div className="flex items-center justify-center gap-3 pt-2" aria-hidden>
            <div className="h-px w-16 bg-gradient-to-r from-transparent to-border/60" />
            <div className="h-1.5 w-1.5 rounded-full bg-primary/40" />
            <div className="h-px w-24 bg-border/40" />
            <div className="h-1.5 w-1.5 rounded-full bg-accent/50" />
            <div className="h-px w-16 bg-gradient-to-l from-transparent to-border/60" />
          </div>
        </div>
      </Reveal>
    </section>
  );
}

function ServicesSection() {
  return (
    <section className="mx-auto mt-10 max-w-screen-2xl px-4 sm:mt-16 sm:px-8 lg:mt-20 lg:px-12">
      <Reveal className="mb-8 text-center sm:mb-10">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl lg:text-4xl">
          Tout ce dont vous avez besoin
        </h2>
        <p className="mt-3 text-sm text-muted-foreground sm:text-base">
          Un outil unique pour gérer tous vos tickets internes, de la soumission à la résolution.
        </p>
      </Reveal>

      <motion.div
        className="grid gap-5 sm:grid-cols-2 md:grid-cols-3"
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-80px" }}
        variants={stagger}
      >
        {[
          {
            icon: Bolt,
            title: "Créer un ticket en quelques clics",
            desc: "Décrivez votre besoin avec un titre, une description et des pièces jointes. Une référence de suivi est générée immédiatement.",
            cta: "Créer un ticket",
            to: "/login",
          },
          {
            icon: Bell,
            title: "Suivi en temps réel",
            desc: "Recevez une notification à chaque étape clé : prise en charge, transmission, résolution, fermeture.",
            cta: "Se connecter",
            to: "/login",
          },
          {
            icon: History,
            title: "Historique et traçabilité",
            desc: "Consultez à tout moment l'historique complet de votre ticket et l'intervenant actuellement en charge.",
            cta: "Suivre un ticket",
            to: "/track",
          },
        ].map((s) => (
          <motion.div
            key={s.title}
            variants={fadeUp}
            whileHover={{ y: -8, scale: 1.02 }}
            transition={{ type: "spring", stiffness: 280, damping: 22 }}
            className="h-full"
          >
              <GlassCard className="group flex h-full flex-col gap-4 transition-shadow duration-300 hover:shadow-2xl">
                <motion.div
                  className="flex h-12 w-12 items-center justify-center rounded-2xl gradient-accent text-white shadow-lg shadow-accent/30"
                  whileHover={{ rotate: 8, scale: 1.1 }}
                  transition={{ type: "spring", stiffness: 300 }}
                >
                  <s.icon className="h-5 w-5" />
                </motion.div>
                <div>
                  <h3 className="text-lg font-semibold">{s.title}</h3>
                  <p className="mt-1.5 text-sm text-muted-foreground">{s.desc}</p>
                </div>
                <Button
                  asChild
                  variant="ghost"
                  className="mt-auto justify-start rounded-full px-3 text-primary hover:bg-primary/10"
                >
                  <Link to={s.to}>
                    {s.cta}
                    <ArrowRight className="ml-1 h-4 w-4 transition-transform group-hover:translate-x-1" />
                  </Link>
                </Button>
              </GlassCard>
            </motion.div>
        ))}
      </motion.div>
    </section>
  );
}

function HowSection() {
  const steps = [
    {
      n: "01",
      icon: FilePlus,
      title: "Création",
      desc: "Connectez-vous avec votre compte EDG et décrivez votre besoin. Une référence de suivi est générée et votre ticket rejoint la file d'attente.",
    },
    {
      n: "02",
      icon: Users,
      title: "Prise en charge",
      desc: "Un chef de service prend le ticket depuis la file d'attente et le traite ; il peut le transmettre à un autre intervenant si nécessaire.",
    },
    {
      n: "03",
      icon: CheckCircle2,
      title: "Résolution & validation",
      desc: "Une fois la solution apportée, vous confirmez que la résolution répond bien à votre besoin.",
    },
    {
      n: "04",
      icon: ShieldCheck,
      title: "Fermeture ou réouverture",
      desc: "Le ticket est officiellement clôturé. Si le besoin persiste, vous pouvez le rouvrir pour relancer le traitement.",
    },
  ] as const;

  return (
    <section className="mx-auto mt-10 max-w-screen-2xl px-4 sm:mt-16 sm:px-8 lg:mt-20 lg:px-12">
      <Reveal className="mb-10 text-center sm:mb-12">
        <h2 className="text-2xl font-bold tracking-tight sm:text-3xl lg:text-4xl">
          Comment ça marche
        </h2>
        <p className="mt-3 text-sm text-muted-foreground sm:text-base">
          En quatre étapes, votre ticket est pris en charge et résolu par le bon service.
        </p>
      </Reveal>

      <div className="relative">
        <div
          aria-hidden
          className="pointer-events-none absolute top-[2.35rem] left-[calc(12.5%+2rem)] right-[calc(12.5%+2rem)] hidden h-px bg-gradient-to-r from-primary/20 via-border/60 to-primary/20 lg:block"
        />
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <Reveal key={step.n} delay={i * 0.07}>
              <GlassCard className="group relative flex h-full flex-col gap-4 overflow-hidden transition-all duration-300 hover:-translate-y-1 hover:shadow-xl">
                <span
                  aria-hidden
                  className="pointer-events-none absolute right-4 top-3 select-none text-5xl font-black text-primary/8 dark:text-primary/10"
                >
                  {step.n}
                </span>
                <div className="relative z-10 flex h-12 w-12 items-center justify-center rounded-2xl gradient-primary text-background shadow-md shadow-primary/25 ring-4 ring-background">
                  <step.icon className="h-5 w-5" />
                </div>
                <div className="flex flex-col gap-1.5">
                  <span className="text-[11px] font-semibold uppercase tracking-widest text-primary/70">
                    Étape {step.n}
                  </span>
                  <h3 className="text-base font-semibold leading-snug">{step.title}</h3>
                  <p className="text-sm text-muted-foreground">{step.desc}</p>
                </div>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

function TrustSection() {
  const features = [
    { icon: ShieldCheck,    t: "Sécurisé",    d: "Contrôle d'accès strict (RBAC), authentification JWT et biométrie optionnelle." },
    { icon: Clock,          t: "Temps réel",  d: "Notifications instantanées à chaque changement de statut de votre ticket." },
    { icon: CheckCircle2,   t: "Traçable",    d: "Historique complet et journal d'audit inviolable sur chaque ticket." },
    { icon: HeartHandshake, t: "Collaboratif", d: "Un intervenant dédié pour chaque dossier, du dépôt à la clôture." },
  ] as const;

  return (
    <section className="mx-auto mt-10 max-w-screen-2xl px-4 sm:mt-16 sm:px-8 lg:mt-20 lg:px-12 pb-12 sm:pb-16 lg:pb-20">
      <Reveal>
        <GlassCard strong className="grid gap-8 p-8 sm:p-12 lg:grid-cols-2 lg:gap-12">
          <div>
            <h2 className="text-3xl font-bold tracking-tight">
              Une plateforme conçue pour la{" "}
              <span className="text-gradient">confiance</span>.
            </h2>
            <p className="mt-3 text-muted-foreground">
              EDG Support centralise le traitement des tickets internes, avec une
              traçabilité complète et un suivi en temps réel à chaque étape.
              Chaque employé sait à tout moment où en est son dossier — et qui en a la charge.
            </p>
            <motion.div
              whileHover={{ scale: 1.04 }}
              whileTap={{ scale: 0.97 }}
              className="mt-6 inline-block"
            >
              <Button asChild className="rounded-full gradient-primary shadow-lg shadow-primary/30">
                <Link to="/login">
                  Ouvrir un ticket <ArrowRight className="ml-2 h-4 w-4" />
                </Link>
              </Button>
            </motion.div>
          </div>
          <motion.ul
            className="grid gap-4 sm:grid-cols-2"
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, margin: "-60px" }}
            variants={stagger}
          >
            {features.map((f) => (
              <motion.li
                key={f.t}
                variants={fadeUp}
                whileHover={{ x: 4 }}
                className="flex gap-3 rounded-2xl border border-border/40 bg-background/50 p-4"
              >
                <f.icon className="h-5 w-5 shrink-0 text-primary" />
                <div>
                  <div className="font-medium">{f.t}</div>
                  <div className="text-sm text-muted-foreground">{f.d}</div>
                </div>
              </motion.li>
            ))}
          </motion.ul>
        </GlassCard>
      </Reveal>
    </section>
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// Map section ID → composant de rendu
// ══════════════════════════════════════════════════════════════════════════════

function SlidesCarousel({ slides }: { slides: HomepageSlide[] }) {
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const prefersReduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (prefersReduced || paused || slides.length <= 1) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % slides.length), 6000);
    return () => clearInterval(t);
  }, [paused, prefersReduced, slides.length]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "ArrowLeft")
        setIdx((i) => (i - 1 + slides.length) % slides.length);
      if (e.key === "ArrowRight")
        setIdx((i) => (i + 1) % slides.length);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [slides.length]);

  const slide = slides[idx];
  if (!slide) return null;

  return (
    <section
      aria-label="Carrousel d'accueil"
      className="mx-auto mt-10 max-w-screen-2xl px-4 sm:mt-14 sm:px-8 lg:px-12"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <div className="relative overflow-hidden rounded-2xl">
        <AnimatePresence mode="wait">
          <motion.div
            key={slide.id}
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -40 }}
            transition={{ duration: 0.4, ease: "easeOut" }}
            className={`rounded-2xl border border-border/40 bg-gradient-to-br from-primary/8 via-card/80 to-accent/5 backdrop-blur-md${slide.image_url ? " grid grid-cols-1 lg:grid-cols-[1fr_380px]" : ""}`}
          >
            <div className="flex flex-col justify-center gap-4 p-8 sm:p-10 lg:p-12">
              {slide.title && (
                <h2 className="text-2xl font-bold leading-tight tracking-tight sm:text-3xl lg:text-4xl">
                  {slide.title}
                </h2>
              )}
              {slide.message && (
                <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground sm:text-base">
                  {slide.message}
                </p>
              )}
              {slide.cta_label && slide.cta_url && (
                <div className="mt-2">
                  <a
                    href={slide.cta_url}
                    className="inline-flex items-center gap-2 rounded-xl bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground shadow transition-opacity hover:opacity-90"
                    target={slide.cta_url.startsWith("http") ? "_blank" : undefined}
                    rel={slide.cta_url.startsWith("http") ? "noopener noreferrer" : undefined}
                  >
                    {slide.cta_label}
                    <ArrowRight className="h-4 w-4" />
                  </a>
                </div>
              )}
            </div>
            {slide.image_url && (
              <div className="hidden lg:flex items-center justify-center overflow-hidden rounded-r-2xl bg-background/20">
                <img
                  src={slide.image_url}
                  alt=""
                  aria-hidden
                  className="h-full w-full object-cover"
                />
              </div>
            )}
          </motion.div>
        </AnimatePresence>

        {/* Arrows */}
        {slides.length > 1 && (
          <>
            <button
              onClick={() => setIdx((i) => (i - 1 + slides.length) % slides.length)}
              className="absolute left-3 top-1/2 -translate-y-1/2 rounded-xl border border-border/40 bg-card/70 p-2 backdrop-blur-sm transition-colors hover:bg-card"
              aria-label="Slide précédent"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <button
              onClick={() => setIdx((i) => (i + 1) % slides.length)}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-xl border border-border/40 bg-card/70 p-2 backdrop-blur-sm transition-colors hover:bg-card"
              aria-label="Slide suivant"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {/* Dots */}
      {slides.length > 1 && (
        <div className="mt-4 flex justify-center gap-2" role="tablist" aria-label="Slides">
          {slides.map((s, i) => (
            <button
              key={s.id}
              role="tab"
              aria-selected={i === idx}
              aria-label={`Slide ${i + 1}`}
              onClick={() => setIdx(i)}
              className={`h-2 rounded-full transition-all ${
                i === idx
                  ? "w-6 bg-primary"
                  : "w-2 bg-border/60 hover:bg-border"
              }`}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function CustomSection({ id, title, content }: { id: string; title: string; content?: string }) {
  return (
    <section className="mx-auto mt-16 max-w-screen-lg px-4 sm:px-8" key={id}>
      <GlassCard className="p-6 sm:p-8 text-center space-y-4">
        <h2 className="text-2xl font-bold tracking-tight">{title}</h2>
        {content && (
          <p className="text-muted-foreground leading-relaxed whitespace-pre-line">{content}</p>
        )}
      </GlassCard>
    </section>
  );
}

function renderSection(section: SectionConfig, missionText: string) {
  switch (section.id) {
    case "mission":  return <MissionBand key="mission" text={missionText} />;
    case "services": return <ServicesSection key="services" />;
    case "how":      return <HowSection key="how" />;
    case "for-who":  return null;
    case "trust":    return <TrustSection key="trust" />;
    default:         return (
      <CustomSection
        key={section.id}
        id={section.id}
        title={section.title ?? section.label}
        content={section.content}
      />
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════
// Page principale
// ══════════════════════════════════════════════════════════════════════════════

function Home() {
  // ── Appels décâblés de la page d'accueil publique (2026-09-22) ─────────────
  // Trois requêtes ont été retirées d'ici car elles échouaient systématiquement
  // et polluaient la console sans rien apporter à l'affichage :
  //
  //  1. GET /homepage-config/   → 404 : les tables du module "page d'accueil
  //     personnalisable" n'existent pas en base. La fonction retombait déjà sur
  //     DEFAULT_CONFIG, qui est donc utilisé directement ici.
  //  2. GET /homepage/slides/   → 404 : même module inachevé. Repli sur [].
  //
  // Les fonctions du client API (fetchHomepageConfig / fetchSlides) sont
  // conservées : elles restent utilisées par l'espace connecté et
  // l'administration, et permettront de recâbler ici lorsque le module page
  // d'accueil sera terminé.
  const config = DEFAULT_CONFIG;
  const slides: HomepageSlide[] = [];

  const { data: activeDirectionsCount, isLoading: dirCountLoading } = useQuery({
    queryKey: ["public-directions-count"],
    queryFn: fetchActiveDirectionsCount,
    staleTime: 10 * 60_000,
    retry: 1,
  });

  const visibleSections = [...config.sections]
    .sort((a, b) => a.order - b.order)
    .filter((s) => s.visible);

  return (
    <PublicLayout>

      {/* ── Fond animé ambiant ── */}
      <motion.div
        aria-hidden
        className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1.2 }}
      >
        <motion.div
          className="absolute -top-32 -left-32 h-[480px] w-[480px] rounded-full bg-primary/15 blur-3xl"
          animate={{ x: [0, 60, 0], y: [0, 40, 0] }}
          transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute -bottom-32 -right-32 h-[520px] w-[520px] rounded-full bg-accent/15 blur-3xl"
          animate={{ x: [0, -50, 0], y: [0, -30, 0] }}
          transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
        />
      </motion.div>

      {/* ══════ HERO — toujours affiché ══════ */}
      <section className="relative px-4 pt-8 sm:px-8 sm:pt-16 lg:px-12 lg:pt-24">
        <div className="mx-auto max-w-screen-2xl">
          <div className="grid items-center gap-10 md:gap-14 lg:grid-cols-2">
            <motion.div initial="hidden" animate="show" variants={stagger}>
              <motion.h1
                variants={fadeUp}
                className="text-3xl font-bold tracking-tight sm:text-4xl lg:text-5xl xl:text-6xl"
              >
                La gestion collaborative de vos tickets{" "}
                <span className="text-gradient">de bout en bout</span>.
              </motion.h1>

              <motion.p
                variants={fadeUp}
                className="mt-5 max-w-xl text-sm text-muted-foreground sm:text-base lg:text-lg"
              >
                Créez un ticket, suivez chaque étape de son traitement et
                collaborez avec les équipes de la Direction des Systèmes
                d'Information. Une traçabilité complète, de la création à la clôture.
              </motion.p>

              <motion.div variants={fadeUp} className="mt-8 flex flex-row flex-wrap gap-3">
                <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                  <Button
                    asChild
                    size="lg"
                    className="rounded-full gradient-primary shadow-xl shadow-primary/30 h-11 px-5 sm:h-12 sm:px-7 text-sm sm:text-base"
                  >
                    <Link to="/login">
                      Ouvrir un ticket <ArrowRight className="ml-2 h-4 w-4" />
                    </Link>
                  </Button>
                </motion.div>
                <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.97 }}>
                  <Button
                    asChild
                    size="lg"
                    variant="outline"
                    className="h-11 rounded-full px-5 sm:h-12 sm:px-7 backdrop-blur-xl bg-background/60 text-sm sm:text-base"
                  >
                    <Link to="/track">
                      <Search className="mr-2 h-4 w-4" />
                      Suivre un ticket
                    </Link>
                  </Button>
                </motion.div>
              </motion.div>

              <motion.div variants={stagger} className="mt-10 grid grid-cols-3 gap-3 sm:gap-8">
                {[
                  { v: "Temps réel", l: "Notifications" },
                  { v: "Traçable", l: "Historique complet" },
                  { v: dirCountLoading ? "…" : activeDirectionsCount != null ? String(activeDirectionsCount) : "—", l: "Directions actives" },
                ].map((s) => (
                  <motion.div key={s.l} variants={fadeUp}>
                    <div className="text-2xl font-bold sm:text-3xl">{s.v}</div>
                    <div className="text-[11px] sm:text-xs text-muted-foreground">{s.l}</div>
                  </motion.div>
                ))}
              </motion.div>
            </motion.div>

            {/* Maquette flottante — masquée sur mobile pour éviter un héro trop long */}
            <motion.div
              className="relative hidden lg:block"
              initial={{ opacity: 0, scale: 0.92, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1], delay: 0.2 }}
            >
              <motion.div
                aria-hidden
                className="pointer-events-none absolute -inset-6 sm:-inset-10 bg-gradient-to-br from-primary/30 via-accent/20 to-success/20 blur-3xl rounded-full"
                animate={{ scale: [1, 1.08, 1], opacity: [0.6, 0.9, 0.6] }}
                transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
              />
              <Floating>
                <motion.div whileHover={{ y: -4 }} transition={{ type: "spring", stiffness: 300 }}>
                  <GlassCard strong className="relative space-y-4">
                    {/* En-tête ticket */}
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">Ticket</div>
                        <div className="font-mono text-sm font-semibold">EDG-2025-0178</div>
                      </div>
                      <span className="shrink-0 rounded-full bg-success/15 px-3 py-1 text-xs font-semibold text-success ring-1 ring-success/30">
                        Résolu
                      </span>
                    </div>

                    {/* Carte ticket */}
                    <div className="rounded-2xl border border-border/40 p-3.5 glass-subtle">
                      <div className="text-sm font-semibold leading-snug">Compteur défectueux — Ratoma</div>
                      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        <span className="rounded-full bg-muted/60 px-2 py-0.5 text-[10px] text-muted-foreground">Dir. Commerciale</span>
                        <span className="rounded-full bg-orange-500/10 px-2 py-0.5 text-[10px] font-medium text-orange-500">Haute priorité</span>
                      </div>
                    </div>

                    {/* Historique */}
                    <div className="space-y-2.5">
                      {[
                        { t: "Ticket créé",        d: "08 jan. 2025 · 09h14", done: true },
                        { t: "Prise en charge",         d: "08 jan. 2025 · 10h02", done: true },
                        { t: "Ticket en traitement",      d: "08 jan. 2025 · 14h30", done: true },
                        { t: "Ticket clôturé", d: "09 jan. 2025 · 11h20", done: true },
                      ].map((step, i) => (
                        <motion.div key={i} variants={fadeUp} className="flex items-start gap-3">
                          <div className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full bg-success ring-4 ring-success/20" />
                          <div className="flex-1 min-w-0">
                            <div className="text-xs font-medium">{step.t}</div>
                            <div className="text-[10px] text-muted-foreground">{step.d}</div>
                          </div>
                        </motion.div>
                      ))}
                    </div>

                    {/* Note satisfaction */}
                    <div className="flex items-center justify-between rounded-xl border border-success/20 bg-success/5 px-3 py-2">
                      <span className="text-[11px] text-muted-foreground">Satisfaction utilisateur</span>
                      <div className="flex gap-0.5">
                        {[1,2,3,4,5].map((s) => (
                          <span key={s} className={s <= 4 ? "text-amber-400 text-xs" : "text-muted-foreground/30 text-xs"}>★</span>
                        ))}
                      </div>
                    </div>
                  </GlassCard>
                </motion.div>
              </Floating>
            </motion.div>
          </div>
        </div>
      </section>

      {/* ══════ CARROUSEL D'ACCUEIL — slides personnalisables par l'admin ══════ */}
      {slides.length > 0 && <SlidesCarousel slides={slides} />}

      {/* ══════ SECTIONS DYNAMIQUES — ordre et visibilité décidés par l'admin ══════ */}
      {visibleSections.map((s) => renderSection(s, config.missionText))}

    </PublicLayout>
  );
}
