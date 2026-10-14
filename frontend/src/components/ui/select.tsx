"use client";

/**
 * Liste déroulante AVEC RECHERCHE (« combobox ») — décision du 2026-10-14 :
 * toutes les listes de l'application permettent de taper pour filtrer, puis de
 * choisir au clavier (flèches + Entrée) ou à la souris.
 *
 * Même interface que l'ancien composant Radix Select (Select, SelectTrigger,
 * SelectValue, SelectContent, SelectItem, SelectGroup, SelectLabel,
 * SelectSeparator) : les écrans existants n'ont pas à changer. Seule une valeur
 * de la liste peut être choisie — jamais un texte libre.
 *
 * Construit sur Popover (Radix, `modal` pour fonctionner dans les fenêtres
 * modales) + cmdk (liste filtrée au clavier).
 */
import * as React from "react";
import * as PopoverPrimitive from "@radix-ui/react-popover";
import { Command as CommandPrimitive } from "cmdk";
import { Check, ChevronDown, Search } from "lucide-react";

import { cn } from "@/lib/utils";
import { collectItems, matchesSearch, type CollectedItem } from "@/lib/select-utils";

type SelectContextValue = {
  value: string | undefined;
  select: (value: string) => void;
  open: boolean;
  setOpen: (open: boolean) => void;
  disabled?: boolean;
  items: Map<string, CollectedItem>;
  search: string;
  setSearch: (search: string) => void;
};

const SelectContext = React.createContext<SelectContextValue | null>(null);

function useSelectContext(component: string): SelectContextValue {
  const ctx = React.useContext(SelectContext);
  if (!ctx) throw new Error(`<${component}> doit être placé dans un <Select>.`);
  return ctx;
}

type SelectProps = {
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  disabled?: boolean;
  name?: string;
  required?: boolean;
  children?: React.ReactNode;
};

function Select({
  value: valueProp,
  defaultValue,
  onValueChange,
  open: openProp,
  defaultOpen = false,
  onOpenChange,
  disabled,
  name,
  required,
  children,
}: SelectProps) {
  const [innerValue, setInnerValue] = React.useState(defaultValue);
  const [innerOpen, setInnerOpen] = React.useState(defaultOpen);
  const [search, setSearch] = React.useState("");
  const value = valueProp !== undefined ? valueProp : innerValue;
  const open = openProp !== undefined ? openProp : innerOpen;

  const setOpen = React.useCallback(
    (next: boolean) => {
      if (disabled && next) return;
      if (openProp === undefined) setInnerOpen(next);
      if (!next) setSearch("");
      onOpenChange?.(next);
    },
    [disabled, openProp, onOpenChange],
  );

  const select = React.useCallback(
    (next: string) => {
      if (valueProp === undefined) setInnerValue(next);
      if (next !== value) onValueChange?.(next);
      setOpen(false);
    },
    [valueProp, value, onValueChange, setOpen],
  );

  // Choix connus même liste fermée : le libellé du choix courant s'affiche dans
  // le champ sans que la liste ait été ouverte.
  const items = React.useMemo(() => collectItems(children, SelectItem), [children]);

  return (
    <SelectContext.Provider value={{ value, select, open, setOpen, disabled, items, search, setSearch }}>
      <PopoverPrimitive.Root open={open} onOpenChange={setOpen} modal>
        {children}
      </PopoverPrimitive.Root>
      {name && <input type="hidden" name={name} value={value ?? ""} required={required} />}
    </SelectContext.Provider>
  );
}

const SelectGroup = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => <div ref={ref} role="group" className={className} {...props} />,
);
SelectGroup.displayName = "SelectGroup";

function SelectValue({ placeholder, className }: { placeholder?: React.ReactNode; className?: string }) {
  const { value, items } = useSelectContext("SelectValue");
  const item = value !== undefined && value !== "" ? items.get(value) : undefined;
  if (!item) {
    return (
      <span className={cn("truncate", value ? undefined : "text-muted-foreground", className)}>
        {value && !item ? value : placeholder}
      </span>
    );
  }
  return <span className={cn("truncate", className)}>{item.label}</span>;
}

const SelectTrigger = React.forwardRef<HTMLButtonElement, React.ButtonHTMLAttributes<HTMLButtonElement>>(
  ({ className, children, onKeyDown, disabled: disabledProp, ...props }, ref) => {
    const { open, setOpen, value, disabled, setSearch } = useSelectContext("SelectTrigger");
    const isDisabled = disabled || disabledProp;
    return (
      <PopoverPrimitive.Trigger asChild>
        <button
          ref={ref}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-haspopup="listbox"
          disabled={isDisabled}
          data-placeholder={value ? undefined : ""}
          className={cn(
            "flex h-9 w-full items-center justify-between gap-2 whitespace-nowrap rounded-md border border-input bg-transparent px-3 py-2 text-left text-sm shadow-sm ring-offset-background cursor-pointer data-[placeholder]:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 [&>span]:line-clamp-1",
            className,
          )}
          onKeyDown={(event) => {
            onKeyDown?.(event);
            if (event.defaultPrevented || isDisabled) return;
            // Taper une lettre sur le champ fermé ouvre la liste et commence la recherche.
            if (!open && event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
              event.preventDefault();
              setSearch(event.key);
              setOpen(true);
            } else if (!open && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
              event.preventDefault();
              setOpen(true);
            }
          }}
          {...props}
        >
          {children}
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </button>
      </PopoverPrimitive.Trigger>
    );
  },
);
SelectTrigger.displayName = "SelectTrigger";

type SelectContentProps = {
  className?: string;
  children?: React.ReactNode;
  /** Conservés pour compatibilité avec l'ancienne interface Radix Select. */
  position?: "popper" | "item-aligned";
  align?: "start" | "center" | "end";
  searchPlaceholder?: string;
};

const SelectContent = React.forwardRef<HTMLDivElement, SelectContentProps>(
  ({ className, children, align = "start", searchPlaceholder = "Rechercher…" }, ref) => {
    const { search, setSearch, items } = useSelectContext("SelectContent");
    const hasMatch = [...items.values()].some((item) => matchesSearch(item.text, search));
    return (
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          ref={ref}
          align={align}
          sideOffset={4}
          className="z-50 w-(--radix-popover-trigger-width) min-w-[12rem] overflow-hidden rounded-md border bg-popover p-0 text-popover-foreground shadow-md outline-none data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95"
          onOpenAutoFocus={(event) => {
            // Le focus va au champ de recherche (cmdk), pas au conteneur.
            event.preventDefault();
            (event.currentTarget as HTMLElement).querySelector<HTMLInputElement>("[cmdk-input]")?.focus();
          }}
        >
          <CommandPrimitive shouldFilter={false} loop className="flex flex-col">
            <div className="flex items-center gap-2 border-b px-3" cmdk-input-wrapper="">
              <Search className="h-4 w-4 shrink-0 opacity-50" />
              <CommandPrimitive.Input
                value={search}
                onValueChange={setSearch}
                placeholder={searchPlaceholder}
                className="flex h-9 w-full bg-transparent py-2 text-sm outline-none placeholder:text-muted-foreground"
              />
            </div>
            <CommandPrimitive.List className={cn("max-h-72 overflow-y-auto overflow-x-hidden p-1", className)}>
              {!hasMatch && (
                <div className="py-4 text-center text-sm text-muted-foreground">Aucun résultat.</div>
              )}
              {children}
            </CommandPrimitive.List>
          </CommandPrimitive>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    );
  },
);
SelectContent.displayName = "SelectContent";

const SelectLabel = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn("px-2 py-1.5 text-sm font-semibold", className)} {...props} />
  ),
);
SelectLabel.displayName = "SelectLabel";

type SelectItemProps = {
  value: string;
  disabled?: boolean;
  className?: string;
  children?: React.ReactNode;
};

function SelectItem({ value, disabled, className, children }: SelectItemProps) {
  const { value: current, select, search, items } = useSelectContext("SelectItem");
  const text = items.get(String(value))?.text ?? "";
  if (!matchesSearch(text, search)) return null;
  const selected = current === value;
  return (
    <CommandPrimitive.Item
      value={`${text}\u0000${value}`}
      disabled={disabled}
      onSelect={() => select(value)}
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-2 pr-8 text-sm outline-none data-[selected=true]:bg-accent data-[selected=true]:text-accent-foreground data-[disabled=true]:pointer-events-none data-[disabled=true]:opacity-50",
        className,
      )}
    >
      <span className="absolute right-2 flex h-3.5 w-3.5 items-center justify-center">
        {selected && <Check className="h-4 w-4" />}
      </span>
      <span className="truncate">{children}</span>
    </CommandPrimitive.Item>
  );
}
SelectItem.displayName = "SelectItem";

const SelectSeparator = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => {
    const { search } = useSelectContext("SelectSeparator");
    // Pendant une recherche, les séparateurs n'ont plus de sens (liste filtrée).
    if (search.trim()) return null;
    return <div ref={ref} role="separator" className={cn("-mx-1 my-1 h-px bg-muted", className)} {...props} />;
  },
);
SelectSeparator.displayName = "SelectSeparator";

/** Conservés pour compatibilité d'import : plus de défilement par boutons. */
const SelectScrollUpButton = () => null;
const SelectScrollDownButton = () => null;

export {
  Select,
  SelectGroup,
  SelectValue,
  SelectTrigger,
  SelectContent,
  SelectLabel,
  SelectItem,
  SelectSeparator,
  SelectScrollUpButton,
  SelectScrollDownButton,
};
