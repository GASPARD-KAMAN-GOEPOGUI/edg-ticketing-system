// Fallback automatique oklch()/oklab() → rgb pour les navigateurs qui ne
// supportent pas les fonctions de couleur CSS Color Level 4 (ex. Edge < 111,
// Safari < 15.4). S'applique à TOUT le CSS généré, y compris les variables
// custom (styles.css) et les classes de palette Tailwind natives (bg-red-500,
// text-blue-600, etc.) qui compilent en oklch() par défaut sous Tailwind v4.
//
// preserve: true → émet la valeur rgb calculée AVANT la valeur oklch d'origine.
// Un navigateur qui ne comprend pas oklch() ignore cette déclaration invalide
// et garde le rgb précédent ; un navigateur qui la comprend applique oklch
// (dernière déclaration valide gagne en cascade CSS).
export default {
  plugins: {
    "@csstools/postcss-oklab-function": { preserve: true },
  },
};
