import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  Outlet,
  Link,
  createRootRouteWithContext,
  useRouter,
  HeadContent,
  Scripts,
} from "@tanstack/react-router";
import { useEffect, type ReactNode } from "react";

import appCss from "../styles.css?url";
import edgFavicon from "../assets/edg_logo.png?url";
import { reportLovableError } from "../lib/lovable-error-reporting";
import { Toaster } from "@/components/ui/sonner";
import { RouteTransition } from "@/components/route-transition";
import { Logo } from "@/components/logo";

function NotFoundComponent() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <Link to="/" className="mb-8" aria-label="Retour à l'accueil">
        <Logo size="xl" showText={false} />
      </Link>
      <div className="max-w-md text-center">
        <p className="text-8xl font-black text-primary/20 select-none">404</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">
          Page introuvable
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Cette page n'existe pas ou a été déplacée.
        </p>
        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <Link
            to="/"
            className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Retour à l'accueil
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center justify-center rounded-full border border-border px-6 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-foreground/5"
          >
            Se connecter
          </Link>
        </div>
      </div>
    </div>
  );
}

function ErrorComponent({ error, reset }: { error: Error; reset: () => void }) {
  console.error(error);
  const router = useRouter();
  useEffect(() => {
    reportLovableError(error, { boundary: "tanstack_root_error_component" });
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4">
      <Link to="/" className="mb-8" aria-label="Retour à l'accueil">
        <Logo size="xl" showText={false} />
      </Link>
      <div className="max-w-md text-center">
        <h1 className="text-2xl font-bold tracking-tight text-foreground">
          Une erreur est survenue
        </h1>
        <p className="mt-3 text-sm text-muted-foreground">
          Une erreur inattendue s'est produite. Vous pouvez réessayer ou retourner à l'accueil.
        </p>
        <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={() => {
              router.invalidate();
              reset();
            }}
            className="inline-flex items-center justify-center rounded-full bg-primary px-6 py-2.5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Réessayer
          </button>
          <a
            href="/"
            className="inline-flex items-center justify-center rounded-full border border-border px-6 py-2.5 text-sm font-medium text-foreground transition-colors hover:bg-foreground/5"
          >
            Retour à l'accueil
          </a>
        </div>
      </div>
    </div>
  );
}

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "EDG Connect" },
      { name: "description", content: "EDG Support is a responsive web application for managing service requests and incidents for Électricité de Guinée." },
      { name: "author", content: "EDG" },
      { property: "og:title", content: "EDG Connect" },
      { property: "og:description", content: "EDG Support is a responsive web application for managing service requests and incidents for Électricité de Guinée." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary" },
      { name: "twitter:site", content: "@EDGConnect" },
      { name: "twitter:title", content: "EDG Connect" },
      { name: "twitter:description", content: "EDG Support is a responsive web application for managing service requests and incidents for Électricité de Guinée." },
      { property: "og:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/f78eb3a1-8355-4f98-b686-165ca100fbbb/id-preview-e8674085--8dde013b-9e47-41d8-a10f-f5e141d00ed2.lovable.app-1780653035506.png" },
      { name: "twitter:image", content: "https://pub-bb2e103a32db4e198524a2e9ed8f35b4.r2.dev/f78eb3a1-8355-4f98-b686-165ca100fbbb/id-preview-e8674085--8dde013b-9e47-41d8-a10f-f5e141d00ed2.lovable.app-1780653035506.png" },
    ],
    links: [
      { rel: "stylesheet", href: appCss },
      { rel: "icon", type: "image/png", href: edgFavicon },
      { rel: "apple-touch-icon", href: edgFavicon },
    ],
  }),
  shellComponent: RootShell,
  component: RootComponent,
  notFoundComponent: NotFoundComponent,
  errorComponent: ErrorComponent,
});

const themeInitScript = `(function(){try{var k='edg.theme';var s=localStorage.getItem(k);var d=s==='dark';var c=document.documentElement.classList;if(d)c.add('dark');else c.remove('dark');document.documentElement.style.colorScheme=d?'dark':'light';}catch(e){document.documentElement.classList.remove('dark');}})();`;

function RootShell({ children }: { children: ReactNode }) {
  return (
    <html lang="fr">

      <head>
        <HeadContent />
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        {children}
        <Scripts />
      </body>
    </html>
  );
}

function RootComponent() {
  const { queryClient } = Route.useRouteContext();

  return (
    <QueryClientProvider client={queryClient}>
      <RouteTransition>
        <Outlet />
      </RouteTransition>
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  );
}
