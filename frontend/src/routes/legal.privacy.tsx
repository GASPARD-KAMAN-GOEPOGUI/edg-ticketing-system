import { createFileRoute, Link } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Logo } from "@/components/logo";

export const Route = createFileRoute("/legal/privacy")({
  head: () => ({ meta: [{ title: "Politique de confidentialité — EDG Support" }] }),
  component: PrivacyPage,
});

function PrivacyPage() {
  return (
    <div className="min-h-dvh px-4 py-10">
      <div className="mx-auto max-w-2xl">
        <div className="mb-8 flex flex-col items-center gap-3">
          <Link to="/" aria-label="Retour à l'accueil">
            <Logo size="lg" showText={false} />
          </Link>
        </div>

        <GlassCard strong className="p-8">
          <h1 className="text-2xl font-bold tracking-tight">Politique de confidentialité</h1>
          <p className="mt-1 text-sm text-muted-foreground">EDG Support — version 1.0</p>

          <div className="mt-6 space-y-4 text-sm leading-relaxed text-muted-foreground">
            <div className="rounded-xl border border-amber-500/25 bg-amber-500/8 px-4 py-3 text-amber-700 dark:text-amber-400">
              Page provisoire — le texte définitif de la politique de
              confidentialité d'EDG Support n'a pas encore été rédigé. Ce
              placeholder décrit les données réellement traitées en attendant
              la version officielle.
            </div>
            <p>
              <span className="font-medium text-foreground">Informations utilisées :</span>{" "}
              identité (nom, prénom), adresse email, numéro de téléphone,
              identifiant central, ainsi que les informations nécessaires au
              fonctionnement de votre compte (rôle, affectation, préférences de
              notification).
            </p>
            <p>
              <span className="font-medium text-foreground">Source :</span> votre
              identité, votre email et votre téléphone proviennent de la
              plateforme centrale d'authentification EDG. EDG Support conserve
              un miroir local minimal de ces informations, nécessaire pour
              afficher votre profil et déterminer votre espace de travail.
            </p>
            <p>
              <span className="font-medium text-foreground">Finalité :</span> ces
              données servent exclusivement au fonctionnement du service de
              gestion des requêtes (attribution, notifications, historique,
              statistiques internes) — elles ne sont pas partagées avec des
              tiers en dehors d'Électricité de Guinée.
            </p>
            <p>
              <span className="font-medium text-foreground">Conservation :</span>{" "}
              vos données sont conservées tant que votre compte est actif.
              Contactez un administrateur pour toute demande relative à vos
              données personnelles.
            </p>
          </div>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/" className="hover:underline">← Retour au portail public</Link>
        </p>
      </div>
    </div>
  );
}
