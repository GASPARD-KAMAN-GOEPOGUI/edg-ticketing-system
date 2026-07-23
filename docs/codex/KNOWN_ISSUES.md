# Known Issues

## KI-ROUTE-001

Identifiant: KI-ROUTE-001
Date: 2026-07-13
Symptome: confusion possible entre route detail personnelle `/app/requests/$id` et routes detail metier.
Resultat actuel: des corrections recentes ont introduit des routes detail dediees, mais les fichiers `app.*_.tickets.$id.tsx` doivent etre verifies si une URL detail ne correspond pas au contexte attendu.
Resultat attendu: un ticket ouvert depuis Supervision reste dans Supervision; depuis Traitement reste dans Traitement; depuis Administration reste dans Administration.
Module: MOD-SUPERVISION, MOD-AGENT, MOD-CHIEF, MOD-DIRECTION, MOD-DG, MOD-ADMIN.
Role concerne: tous les roles professionnels.
Regle metier: BR-NAV-001.
Chemins probables: `ticket-navigation.ts`, `app-layout.tsx`, `app.*_.tickets.$id.tsx`, `routeTree.gen.ts`.
Cause: a confirmer seulement si le symptome reapparait.
Correction: non applicable dans cette mission; ne pas modifier sans demande explicite.
Fichiers modifies: aucun.
Test: utiliser `frontend/role-visual-check.mjs`.
Statut: surveillance.

## KI-DOC-001

Identifiant: KI-DOC-001
Date: 2026-07-13
Symptome: cette base de connaissance est une premiere cartographie; certains endpoints secondaires restent resumes.
Resultat attendu: chaque prochaine intervention doit enrichir l'index concerne avec les details exacts decouverts.
Module: documentation.
Role concerne: Codex.
Regle metier: mise a jour automatique des index.
Chemins probables: `docs/codex/*.md`.
Cause: cartographie initiale volontairement synthetique pour rester exploitable.
Correction: completer au fil des corrections ciblees.
Fichiers modifies: `docs/codex/*`.
Test: verification presence docs.
Statut: ouvert.

## KI-TEMP-001

Identifiant: KI-TEMP-001
Date: 2026-07-13
Symptome: fichiers temporaires Codex visibles a la racine.
Resultat actuel: artefacts connus de type `.codex-build-*`, profils navigateur, `.codex-visual-tests`, `.codex-uvicorn*.log` ranges dans `.codex/`.
Resultat attendu: aucun fichier temporaire Codex a la racine.
Module: hygiene projet.
Role concerne: Codex.
Regle metier: fichiers temporaires dans `.codex/`.
Chemins probables: `.gitignore`, scripts de test visuel, commandes locales.
Cause: anciens scripts/outils ecrivaient a la racine.
Correction: `.gitignore` ignore `.codex/` et motifs `.codex-*`; `role-visual-check.mjs` ecrit sous `.codex/`.
Fichiers modifies: `.gitignore`, `frontend/role-visual-check.mjs`.
Test: listing racine cible.
Statut: corrige/surveillance.
