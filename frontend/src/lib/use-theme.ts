import { useEffect, useState } from "react";

const KEY = "edg.theme";

function getInitialDark() {
  if (typeof document === "undefined") return false;
  return document.documentElement.classList.contains("dark");
}

function applyDark(next: boolean) {
  const root = document.documentElement;
  root.classList.toggle("dark", next);
  root.style.colorScheme = next ? "dark" : "light";
}

export function useTheme() {
  const [dark, setDark] = useState<boolean>(getInitialDark);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const isDark = document.documentElement.classList.contains("dark");
    if (isDark !== dark) setDark(isDark);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    applyDark(next);
    try {
      localStorage.setItem(KEY, next ? "dark" : "light");
    } catch {}
  };
  return [dark, toggle, mounted] as const;
}
