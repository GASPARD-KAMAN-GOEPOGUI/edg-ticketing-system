import { useMemo, useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function usePagination<T>(items: T[], defaultPageSize = 10) {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(defaultPageSize);
  const totalPages = Math.max(1, Math.ceil(items.length / pageSize));

  useEffect(() => {
    if (page > totalPages) setPage(1);
  }, [totalPages, page]);

  const paged = useMemo(
    () => items.slice((page - 1) * pageSize, page * pageSize),
    [items, page, pageSize],
  );

  const changePageSize = (n: number) => {
    setPageSize(n);
    setPage(1);
  };

  return {
    page,
    setPage,
    totalPages,
    paged,
    total: items.length,
    pageSize,
    setPageSize: changePageSize,
  };
}

type Props = {
  page: number;
  totalPages: number;
  total: number;
  pageSize: number;
  onChange: (p: number) => void;
  onPageSizeChange?: (n: number) => void;
  pageSizeOptions?: number[];
  className?: string;
};

export function PaginationBar({
  page,
  totalPages,
  total,
  pageSize,
  onChange,
  onPageSizeChange,
  pageSizeOptions = [10, 20, 50],
  className,
}: Props) {
  // Masquer si aucun élément ou tout tient sur une seule page
  if (total === 0 || total <= pageSize) return null;
  // S'assurer que la valeur courante figure toujours dans la liste d'options
  const effectiveOptions = [...new Set([pageSize, ...pageSizeOptions])].sort((a, b) => a - b);
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(total, page * pageSize);

  const pages: (number | "...")[] = [];
  for (let i = 1; i <= totalPages; i++) {
    if (i === 1 || i === totalPages || (i >= page - 1 && i <= page + 1)) {
      pages.push(i);
    } else if (pages[pages.length - 1] !== "...") {
      pages.push("...");
    }
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 pt-2",
        className,
      )}
    >
      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <span>
          {from}–{to} sur {total}
        </span>
        {onPageSizeChange && (
          <div className="flex items-center gap-2">
            <span className="hidden sm:inline">Afficher</span>
            <Select
              value={String(pageSize)}
              onValueChange={(v) => onPageSizeChange(Number(v))}
            >
              <SelectTrigger className="h-8 w-[72px] rounded-full text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {effectiveOptions.map((n) => (
                  <SelectItem key={n} value={String(n)}>
                    {n}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <span className="hidden sm:inline">par page</span>
          </div>
        )}
      </div>
      {totalPages > 1 && (
        <div className="flex items-center gap-1">
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 rounded-full"
            disabled={page <= 1}
            onClick={() => onChange(page - 1)}
            aria-label="Page précédente"
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {pages.map((p, i) =>
            p === "..." ? (
              <span key={`e${i}`} className="px-2 text-xs text-muted-foreground">
                …
              </span>
            ) : (
              <Button
                key={p}
                size="sm"
                variant={p === page ? "default" : "ghost"}
                className={cn(
                  "h-8 min-w-8 rounded-full px-3 text-xs",
                  p === page && "gradient-primary text-primary-foreground",
                )}
                onClick={() => onChange(p)}
              >
                {p}
              </Button>
            ),
          )}
          <Button
            size="icon"
            variant="ghost"
            className="h-8 w-8 rounded-full"
            disabled={page >= totalPages}
            onClick={() => onChange(page + 1)}
            aria-label="Page suivante"
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      )}
    </div>
  );
}
