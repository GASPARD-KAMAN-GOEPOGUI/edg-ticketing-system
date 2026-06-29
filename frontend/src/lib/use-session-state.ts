import { useEffect, useState } from "react";

/**
 * Persists a small piece of state in sessionStorage so a list can restore
 * its filters/scroll after navigating to a detail page and coming back.
 */
export function useSessionState<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const [value, setValue] = useState<T>(() => {
    if (typeof window === "undefined") return initial;
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? (JSON.parse(raw) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      /* ignore quota */
    }
  }, [key, value]);

  return [value, setValue];
}

/** Save & restore window scrollY for a given route key. */
export function useScrollRestoration(key: string) {
  useEffect(() => {
    const stored = sessionStorage.getItem(`scroll:${key}`);
    if (stored) {
      const y = parseInt(stored, 10);
      requestAnimationFrame(() => window.scrollTo({ top: y, behavior: "instant" as ScrollBehavior }));
    }
    const save = () => sessionStorage.setItem(`scroll:${key}`, String(window.scrollY));
    window.addEventListener("scroll", save, { passive: true });
    return () => {
      save();
      window.removeEventListener("scroll", save);
    };
  }, [key]);
}
