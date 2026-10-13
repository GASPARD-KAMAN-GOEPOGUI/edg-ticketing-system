import { beforeEach, describe, expect, it } from "vitest";
import { consumePostLoginTarget, rememberPostLoginTarget, safeAppPath } from "./post-login-redirect";

function memoryStorage(): Storage {
  const data = new Map<string, string>();
  return {
    get length() { return data.size; },
    clear: () => data.clear(),
    getItem: (k) => data.get(k) ?? null,
    key: (i) => [...data.keys()][i] ?? null,
    removeItem: (k) => { data.delete(k); },
    setItem: (k, v) => { data.set(k, String(v)); },
  };
}

describe("destination après connexion (boutons des e-mails)", () => {
  beforeEach(() => {
    Object.defineProperty(globalThis, "sessionStorage", { value: memoryStorage(), configurable: true });
  });

  it("accepte les chemins internes /app", () => {
    for (const path of ["/app", "/app/queue", "/app/requests/42", "/app/queue?tab=qualify", "/app#x"]) {
      expect(safeAppPath(path)).toBe(path);
    }
  });

  it("refuse tout ce qui pourrait sortir de l'application", () => {
    for (const path of ["https://evil.example/app", "//evil.example/app", "/application", "/login",
      "/app\\..\\x", "app/queue", "", null, 42]) {
      expect(safeAppPath(path)).toBeNull();
    }
  });

  it("retient puis rend la destination une seule fois", () => {
    rememberPostLoginTarget("/app/requests/42");
    expect(consumePostLoginTarget()).toBe("/app/requests/42");
    expect(consumePostLoginTarget()).toBeNull();
  });

  it("ignore une destination non sûre", () => {
    rememberPostLoginTarget("https://evil.example");
    expect(consumePostLoginTarget()).toBeNull();
  });
});
