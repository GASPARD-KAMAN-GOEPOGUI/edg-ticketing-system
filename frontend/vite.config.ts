// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, nitro (build-only using cloudflare as a default target),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
// You can pass additional config via defineConfig({ vite: { ... }, etc... }) if needed.
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

export default defineConfig({
  tanstackStart: {
    // Redirect TanStack Start's bundled server entry to src/server.ts (our SSR error wrapper).
    // nitro/vite builds from this
    server: { entry: "server" },
    // SPA statique pour cPanel : le build prérend uniquement la coquille
    // dist/client/index.html (pas de serveur Node en production).
    // Nitro reste désactivé : son preset écrit dans .output/ et casse ce prérendu.
    spa: { enabled: true, prerender: { outputPath: "/index.html" } },
  },
  vite: {
    server: {
      port: 3000,
      strictPort: true, // échoue si le port 3000 est déjà occupé
    },
  },
});
