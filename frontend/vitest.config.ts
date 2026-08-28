// Config Vitest autonome — volontairement séparée de vite.config.ts (qui est géré
// par @lovable.dev/vite-tanstack-config, cf. l'avertissement en tête de ce fichier :
// ne pas y ajouter de plugins manuellement). Les tests actuels ne couvrent que des
// fonctions pures en TypeScript (frontend/src/lib/phone.ts) — aucun plugin React/JSX
// n'est donc nécessaire ici.
import { defineConfig } from "vitest/config";
import path from "node:path";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
