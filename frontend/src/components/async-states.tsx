import { AnimatePresence, motion } from "framer-motion";
import { Loader2, Inbox, AlertTriangle, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { GlassCard } from "@/components/glass-card";

type State = "loading" | "empty" | "error" | "ready";

const swap = {
  initial: { opacity: 0, y: 10, filter: "blur(8px)" },
  animate: { opacity: 1, y: 0, filter: "blur(0px)" },
  exit: { opacity: 0, y: -8, filter: "blur(8px)" },
  transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] as const },
};

export function AsyncSwap({
  state,
  loading,
  empty,
  error,
  children,
}: {
  state: State;
  loading?: ReactNode;
  empty?: ReactNode;
  error?: ReactNode;
  children: ReactNode;
}) {
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div key={state} {...swap}>
        {state === "loading" && (loading ?? <LoadingState />)}
        {state === "empty" && (empty ?? <EmptyState />)}
        {state === "error" && (error ?? <ErrorState />)}
        {state === "ready" && children}
      </motion.div>
    </AnimatePresence>
  );
}

export function LoadingState({
  rows = 4,
  label = "Chargement…",
}: {
  rows?: number;
  label?: string;
}) {
  return (
    <div className="space-y-3" role="status" aria-live="polite" aria-busy="true">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
          className="inline-flex"
        >
          <Loader2 className="h-4 w-4" />
        </motion.span>
        <span>{label}</span>
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <motion.div
          key={i}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: i * 0.06, duration: 0.4 }}
        >
          <GlassCard className="p-4">
            <div className="flex items-center justify-between gap-3">
              <Skeleton className="h-3 w-20" />
              <Skeleton className="h-5 w-16 rounded-full" />
            </div>
            <Skeleton className="mt-3 h-4 w-3/4" />
            <Skeleton className="mt-2 h-3 w-1/2" />
          </GlassCard>
        </motion.div>
      ))}
    </div>
  );
}

export function EmptyState({
  title = "Aucun élément",
  description = "Il n'y a rien à afficher pour l'instant.",
  icon: Icon = Inbox,
  action,
}: {
  title?: string;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  action?: ReactNode;
}) {
  return (
    <GlassCard className="py-16 text-center">
      <motion.div
        className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-muted"
        initial={{ scale: 0.6, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 18 }}
      >
        <Icon className="h-6 w-6 text-muted-foreground" />
      </motion.div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </GlassCard>
  );
}

export function ErrorState({
  title = "Une erreur est survenue",
  description = "Réessayez dans un instant.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: () => void;
}) {
  return (
    <GlassCard className="py-12 text-center">
      <motion.div
        className="mx-auto mb-3 grid h-14 w-14 place-items-center rounded-2xl bg-destructive/10 text-destructive"
        initial={{ x: -10 }}
        animate={{ x: [0, -6, 6, -4, 4, 0] }}
        transition={{ duration: 0.5 }}
      >
        <AlertTriangle className="h-6 w-6" />
      </motion.div>
      <h3 className="font-semibold">{title}</h3>
      <p className="mx-auto mt-1 max-w-sm text-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <Button
          onClick={onRetry}
          variant="outline"
          className="mt-5 rounded-full"
        >
          <RefreshCw className="mr-1.5 h-4 w-4" /> Réessayer
        </Button>
      )}
    </GlassCard>
  );
}
