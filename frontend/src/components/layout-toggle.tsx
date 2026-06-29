import { LayoutGrid, LayoutList } from "lucide-react";
import { cn } from "@/lib/utils";

export type LayoutMode = "list" | "grid";

interface Props {
  layout: LayoutMode;
  onChange: (l: LayoutMode) => void;
  className?: string;
}

export function LayoutToggle({ layout, onChange, className }: Props) {
  return (
    <div
      className={cn(
        "flex items-center gap-0.5 rounded-xl border border-border/40 bg-card/50 p-1 backdrop-blur-sm",
        className,
      )}
      role="group"
      aria-label="Disposition"
    >
      <button
        type="button"
        onClick={() => onChange("list")}
        title="Vue liste"
        aria-pressed={layout === "list"}
        className={cn(
          "rounded-lg p-1.5 transition-all",
          layout === "list"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <LayoutList className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => onChange("grid")}
        title="Vue grille"
        aria-pressed={layout === "grid"}
        className={cn(
          "rounded-lg p-1.5 transition-all",
          layout === "grid"
            ? "bg-background text-foreground shadow-sm"
            : "text-muted-foreground hover:text-foreground",
        )}
      >
        <LayoutGrid className="h-4 w-4" />
      </button>
    </div>
  );
}
