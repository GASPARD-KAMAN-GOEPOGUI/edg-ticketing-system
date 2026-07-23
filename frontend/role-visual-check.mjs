import { spawn } from "node:child_process";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const APP_BASE = "http://127.0.0.1:3000";
const API_BASE = "http://127.0.0.1:8000/api/v1";
const CHROME = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const DEBUG_PORT = Number(process.env.CDP_PORT ?? 9224);
const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CODEX_RUNTIME_DIR = path.join(PROJECT_ROOT, ".codex");
const OUT_DIR = path.join(CODEX_RUNTIME_DIR, "visual-tests");
const PROFILE_DIR = path.join(CODEX_RUNTIME_DIR, "browser-profiles", `chrome-${DEBUG_PORT}`);
const PASSWORD = "Edg@2024!";
const APP_RENDER_TIMEOUT_MS = 12_000;
const DETAIL_TEXT_TIMEOUT_MS = 12_000;

const BACK_TEXT_BY_PATH = {
  "/app/my-tickets": "Retour à mes tickets",
  "/app/queue": "Retour à la file d'attente",
  "/app/supervision": "Retour à la supervision",
  "/app/chief-inbox": "Retour à la boîte de traitement",
  "/app/direction": "Retour à la vue direction",
  "/app/dg": "Retour à la vue globale",
  "/app/admin/users": "Retour à l'administration",
};

const roles = [
  {
    role: "agent",
    email: "fatoumata@gmail.com",
    checks: [
      { label: "Mes tickets", path: "/app/my-tickets", detailPrefix: "/app/my-tickets/tickets/", expectedBack: "/app/my-tickets" },
      { label: "File d'attente", path: "/app/queue", detailPrefix: "/app/queue/tickets/", expectedBack: "/app/queue" },
    ],
  },
  {
    role: "chief",
    email: "chef.dsi@edg.gn",
    checks: [
      { label: "Supervision", path: "/app/supervision", detailPrefix: "/app/supervision/tickets/", expectedBack: "/app/supervision" },
      { label: "Boite chef", path: "/app/chief-inbox", detailPrefix: "/app/chief-inbox/tickets/", expectedBack: "/app/chief-inbox" },
    ],
  },
  {
    role: "director",
    email: "diaby@gmail.com",
    checks: [
      { label: "Supervision", path: "/app/supervision", detailPrefix: "/app/supervision/tickets/", expectedBack: "/app/supervision" },
      { label: "Vue direction", path: "/app/direction", detailPrefix: "/app/direction/tickets/", expectedBack: "/app/direction" },
    ],
  },
  {
    role: "dg",
    email: "gasparndkamangoepogui502@gmail.com",
    checks: [
      { label: "Vue DG", path: "/app/dg", detailPrefix: "/app/dg/tickets/", expectedBack: "/app/dg" },
    ],
  },
  {
    role: "admin",
    email: "gaspardKamangoepogui@gmail.com",
    checks: [
      { label: "Administration", path: "/app/admin/users", detailPrefix: null, expectedBack: "/app/admin/users" },
    ],
  },
];

const requestedRoles = new Set(process.argv.slice(2).map((r) => r.toLowerCase()));
const rolesToRun = requestedRoles.size
  ? roles.filter((r) => requestedRoles.has(r.role))
  : roles;

class Cdp {
  constructor(wsUrl) {
    this.wsUrl = wsUrl;
    this.nextId = 1;
    this.pending = new Map();
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl);
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("CDP websocket timeout")), 10_000);
      this.ws.addEventListener("open", () => {
        clearTimeout(timer);
        resolve();
      }, { once: true });
      this.ws.addEventListener("error", reject, { once: true });
    });
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (!msg.id) return;
      const pending = this.pending.get(msg.id);
      if (!pending) return;
      this.pending.delete(msg.id);
      if (msg.error) pending.reject(new Error(`${pending.method}: ${JSON.stringify(msg.error)}`));
      else pending.resolve(msg.result);
    });
  }

  send(method, params = {}, sessionId) {
    const id = this.nextId++;
    const payload = { id, method, params };
    if (sessionId) payload.sessionId = sessionId;
    this.ws.send(JSON.stringify(payload));
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject, method });
      setTimeout(() => {
        if (!this.pending.has(id)) return;
        this.pending.delete(id);
        reject(new Error(`${method}: timeout`));
      }, 20_000);
    });
  }

  close() {
    this.ws?.close();
  }
}

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitJson(url, timeout = 20_000) {
  const started = Date.now();
  while (Date.now() - started < timeout) {
    try {
      const res = await fetch(url);
      if (res.ok) return await res.json();
    } catch {
      // server still starting
    }
    await sleep(300);
  }
  throw new Error(`Timeout waiting for ${url}`);
}

async function login(email) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ identifier: email, password: PASSWORD }),
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(`Login failed for ${email}: ${res.status} ${JSON.stringify(body)}`);
  }
  return body.data ?? body;
}

async function apiFetch(pathname, token) {
  const res = await fetch(`${API_BASE}${pathname}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) return null;
  return body.data ?? body;
}

function normalizeUser(rawUser) {
  return {
    id: String(rawUser.id),
    name: rawUser.name ?? rawUser.email,
    firstname: rawUser.firstname ?? undefined,
    email: rawUser.email,
    role: rawUser.role,
    phone: rawUser.phone ?? undefined,
    avatar: rawUser.avatar ?? undefined,
    direction_id: rawUser.direction_id != null ? String(rawUser.direction_id) : undefined,
    unit_id: rawUser.unit_id != null ? String(rawUser.unit_id) : undefined,
  };
}

function sessionScript(auth) {
  const user = normalizeUser(auth.user);
  return `
    localStorage.clear();
    localStorage.setItem("edg.auth.access_token", ${JSON.stringify(auth.access_token)});
    localStorage.setItem("edg.auth.refresh_token", ${JSON.stringify(auth.refresh_token)});
    localStorage.setItem("edg.auth.expires_at", String(Date.now() + ${Number(auth.expires_in ?? 3600)} * 1000));
    localStorage.setItem("edg.session.user", ${JSON.stringify(JSON.stringify(user))});
  `;
}

async function createChromeTarget() {
  const url = `http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent("about:blank")}`;
  let res = await fetch(url, { method: "PUT" });
  if (!res.ok) res = await fetch(url);
  if (!res.ok) throw new Error(`Cannot create Chrome target: ${res.status}`);
  return res.json();
}

async function createPage(auth) {
  const target = await createChromeTarget();
  const cdp = new Cdp(target.webSocketDebuggerUrl);
  await cdp.connect();
  const sessionId = undefined;
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 1440,
    height: 900,
    deviceScaleFactor: 1,
    mobile: false,
  });
  await cdp.send("Page.addScriptToEvaluateOnNewDocument", { source: sessionScript(auth) });
  return { targetId: target.id, sessionId, cdp };
}

async function evalJs(cdp, sessionId, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  }, sessionId);
  if (result.exceptionDetails) {
    throw new Error(JSON.stringify(result.exceptionDetails));
  }
  return result.result?.value;
}

async function navigate(cdp, sessionId, url) {
  await cdp.send("Page.navigate", { url }, sessionId);
  const started = Date.now();
  while (Date.now() - started < 20_000) {
    try {
      const current = await evalJs(cdp, sessionId, "location.href");
      const ready = await evalJs(cdp, sessionId, "document.readyState");
      if ((ready === "complete" || ready === "interactive") && current.startsWith(url)) break;
    } catch {
      // context not ready yet
    }
    await sleep(250);
  }
  await waitForAppRender(cdp, sessionId);
}

async function waitForAppRender(cdp, sessionId) {
  const started = Date.now();
  while (Date.now() - started < APP_RENDER_TIMEOUT_MS) {
    try {
      const state = await evalJs(cdp, sessionId, `
        ({
          text: document.body.innerText || "",
          title: document.title || "",
          hasRoot: !!document.querySelector("#root, [data-reactroot], main, aside"),
          url: location.href
        })
      `);
      const text = (state?.text ?? "").trim();
      const stillInitialLoader = text.length < 10 && state?.url?.includes("/app");
      const stillLoading = /Chargement/i.test(text);
      if (!stillInitialLoader && !stillLoading && text.length > 20) return;
    } catch {
      // context not ready yet
    }
    await sleep(500);
  }
  await sleep(1000);
}

async function bodyText(cdp, sessionId) {
  return evalJs(cdp, sessionId, "document.body.innerText || ''");
}

async function waitForBodyIncludes(cdp, sessionId, expected) {
  if (!expected) return;
  const started = Date.now();
  while (Date.now() - started < DETAIL_TEXT_TIMEOUT_MS) {
    const text = await bodyText(cdp, sessionId).catch(() => "");
    if (text.includes(expected) || text.includes("Demande introuvable")) return;
    await sleep(500);
  }
}

async function detailContentOk(cdp, sessionId, expectedBack) {
  const text = await bodyText(cdp, sessionId).catch(() => "");
  const expected = BACK_TEXT_BY_PATH[expectedBack];
  return Boolean(expected && text.includes(expected) && !text.includes("Demande introuvable"));
}

async function screenshot(cdp, sessionId, name) {
  const shot = await cdp.send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
    fromSurface: true,
  }, sessionId);
  const file = path.join(OUT_DIR, `${name}.png`);
  await fs.writeFile(file, Buffer.from(shot.data, "base64"));
  return file;
}

async function currentUrl(cdp, sessionId) {
  return evalJs(cdp, sessionId, "location.href");
}

async function wrongRequestDetailLinks(cdp, sessionId) {
  return evalJs(cdp, sessionId, `
    [...document.querySelectorAll("a[href]")]
      .map((a) => a.href)
      .filter((href) => href.includes("/app/requests/"))
      .filter((href) => !href.includes("/app/requests/history"))
      .filter((href) => !href.endsWith("/app/requests/"))
      .slice(0, 10)
  `);
}

async function firstDetailHref(cdp, sessionId, detailPrefix) {
  const selector = `a[href*="${detailPrefix}"]`;
  return evalJs(cdp, sessionId, `
    ([...document.querySelectorAll(${JSON.stringify(selector)})].map((a) => a.href)[0] || null)
  `);
}

async function hasBackLink(cdp, sessionId, expectedBack) {
  return evalJs(cdp, sessionId, `
    [...document.querySelectorAll("a[href], button")]
      .some((el) => {
        const href = el.getAttribute("href") || "";
        const text = el.textContent || "";
        return href === ${JSON.stringify(expectedBack)} || text.includes(${JSON.stringify(BACK_TEXT_BY_PATH[expectedBack] ?? "Retour")});
      })
  `);
}

async function firstAccessibleRequestId(auth) {
  const first = await apiFetch("/requests?limit=1", auth.access_token);
  return first?.items?.[0]?.id ?? first?.items?.[0]?.uuid ?? null;
}

async function closePage(page) {
  await page.cdp.send("Page.close").catch(() => {});
  page.cdp.close();
}

async function verifyDetailRoute(auth, role, check, index, detailUrl, suffix) {
  const detailPage = await createPage(auth);
  const detailCdp = detailPage.cdp;
  try {
    await navigate(detailCdp, detailPage.sessionId, detailUrl);
    await waitForBodyIncludes(detailCdp, detailPage.sessionId, BACK_TEXT_BY_PATH[check.expectedBack]);
    const finalDetailUrl = await currentUrl(detailCdp, detailPage.sessionId);
    const wrongLinks = await wrongRequestDetailLinks(detailCdp, detailPage.sessionId);
    return {
      finalDetailUrl,
      detailOpened: finalDetailUrl.includes(check.detailPrefix),
      detailContentOk: await detailContentOk(detailCdp, detailPage.sessionId, check.expectedBack),
      detailScreenshot: await screenshot(detailCdp, detailPage.sessionId, `${role}-${index}-detail-${suffix}`),
      backLinkOk: await hasBackLink(detailCdp, detailPage.sessionId, check.expectedBack),
      wrongRequestDetailLinks: wrongLinks,
    };
  } finally {
    await closePage(detailPage);
  }
}

async function checkModule(cdp, page, role, check, index, auth) {
  const result = {
    module: check.label,
    listPath: check.path,
    listLoaded: false,
    detailOpened: null,
    detailContentOk: null,
    wrongRequestDetailLinks: [],
    backLinkOk: null,
    screenshot: null,
    detailScreenshot: null,
    note: "",
  };

  await navigate(cdp, page.sessionId, `${APP_BASE}${check.path}`);
  result.finalListUrl = await currentUrl(cdp, page.sessionId);
  result.listLoaded = result.finalListUrl.includes(check.path);
  result.screenshot = await screenshot(cdp, page.sessionId, `${role}-${index}-list`);
  result.wrongRequestDetailLinks = await wrongRequestDetailLinks(cdp, page.sessionId);

  if (!check.detailPrefix) {
    result.note = "Module sans liste ticket directe; route admin detail testee separement.";
    return result;
  }

  const href = await firstDetailHref(cdp, page.sessionId, check.detailPrefix);
  let detailUrl = href;
  if (!href) {
    const fallbackId = await firstAccessibleRequestId(auth);
    if (!fallbackId) {
      result.note = "Aucun ticket visible dans cette vue et aucun ticket accessible via /requests?limit=1.";
      return result;
    }
    result.note = "Aucun ticket visible dans cette vue; detail teste en acces direct avec le premier ticket accessible.";
    detailUrl = `${APP_BASE}${check.detailPrefix}${fallbackId}`;
  } else {
    result.note = "Lien metier trouve dans la liste; detail verifie dans son espace dedie.";
  }

  const detailResult = await verifyDetailRoute(auth, role, check, index, detailUrl, href ? "linked" : "direct");
  Object.assign(result, detailResult);
  result.wrongRequestDetailLinks = [
    ...result.wrongRequestDetailLinks,
    ...detailResult.wrongRequestDetailLinks,
  ];
  return result;
}

async function checkAdminDetail(auth) {
  const first = await apiFetch("/requests?limit=1", auth.access_token);
  const firstId = first?.items?.[0]?.id ?? first?.items?.[0]?.uuid;
  if (!firstId) {
    return { module: "Admin detail direct", detailOpened: false, note: "Aucun ticket retourne par /requests?limit=1" };
  }
  const check = {
    expectedBack: "/app/admin/users",
    detailPrefix: "/app/admin/tickets/",
  };
  const detail = await verifyDetailRoute(auth, "admin", check, "direct", `${APP_BASE}/app/admin/tickets/${firstId}`, "route");
  return {
    module: "Admin detail direct",
    ...detail,
  };
}

async function launchChrome() {
  await fs.mkdir(PROFILE_DIR, { recursive: true });
  const chrome = spawn(CHROME, [
    `--remote-debugging-port=${DEBUG_PORT}`,
    `--user-data-dir=${PROFILE_DIR}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--disable-extensions",
    "about:blank",
  ], { stdio: "ignore" });
  await waitJson(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
  return chrome;
}

function closeChrome(chrome) {
  try { chrome.kill(); } catch { /* ignore */ }
}

await fs.mkdir(OUT_DIR, { recursive: true });
const chrome = await launchChrome();

const summary = [];
try {
  for (const roleDef of rolesToRun) {
    const auth = await login(roleDef.email);
    const page = await createPage(auth);
    const cdp = page.cdp;
    const roleResult = {
      role: roleDef.role,
      email: roleDef.email,
      user: normalizeUser(auth.user),
      checks: [],
    };

    for (const [index, check] of roleDef.checks.entries()) {
      roleResult.checks.push(await checkModule(cdp, page, roleDef.role, check, index + 1, auth));
    }
    if (roleDef.role === "admin") {
      roleResult.checks.push(await checkAdminDetail(auth));
    }

    await closePage(page);
    summary.push(roleResult);
  }
} finally {
  closeChrome(chrome);
}

await fs.writeFile(path.join(OUT_DIR, "summary.json"), JSON.stringify(summary, null, 2), "utf8");

const lines = [];
for (const role of summary) {
  lines.push(`## ${role.role} (${role.email})`);
  for (const check of role.checks) {
    const status = check.detailOpened === true && check.detailContentOk === true
      ? "OK"
      : check.detailOpened === null && check.listLoaded
        ? "VIDE"
        : "ECHEC";
    lines.push(`- ${status} | ${check.module} | list=${check.finalListUrl ?? check.listPath} | detail=${check.finalDetailUrl ?? "-"} | back=${check.backLinkOk} | content=${check.detailContentOk}`);
    if (check.wrongRequestDetailLinks?.length) {
      lines.push(`  liens personnels suspects: ${[...new Set(check.wrongRequestDetailLinks)].join(", ")}`);
    }
    if (check.note) lines.push(`  note: ${check.note}`);
  }
}

console.log(lines.join("\n"));
