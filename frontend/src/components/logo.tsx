import { cn } from "@/lib/utils";
import edgLogo from "@/assets/edg_logo.png";

const SIZES = {
  sm:  "h-8 w-8",
  md:  "h-10 w-10",
  lg:  "h-14 w-14",
  xl:  "h-20 w-20",
} as const;

type LogoSize = keyof typeof SIZES;

export function Logo({
  className,
  showText = true,
  size = "md",
  onDark = false,
}: {
  className?: string;
  showText?: boolean;
  size?: LogoSize;
  onDark?: boolean;
}) {
  return (
    <div className={cn("flex items-center gap-3", className)}>
      {/* Conteneur carré — proportions conservées, jamais circulaire */}
      <div
        className={cn(
          "shrink-0 overflow-hidden rounded-none",
          SIZES[size],
        )}
      >
        <img
          src={edgLogo}
          alt="Électricité de Guinée"
          className="h-full w-full object-contain"
          draggable={false}
        />
      </div>

      {showText && (
        <div className="flex flex-col leading-none">
          <span className={cn("text-base font-bold tracking-tight", onDark ? "text-white" : "")}>
            EDG<span className={onDark ? "text-white/70" : "text-primary"}> Support</span>
          </span>
        </div>
      )}
    </div>
  );
}

/** Variante compacte icon-only — utile dans la sidebar réduite. */
export function LogoIcon({
  className,
  size = "md",
}: {
  className?: string;
  size?: LogoSize;
}) {
  return (
    <Logo className={className} showText={false} size={size} />
  );
}
