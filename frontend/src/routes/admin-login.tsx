import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { GlassCard } from "@/components/glass-card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Logo } from "@/components/logo";
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Eye, EyeOff, Loader2, ShieldCheck, ShieldAlert,
  TerminalSquare, Camera, CameraOff, AlertTriangle,
  CheckCircle2, XCircle, Fingerprint,
} from "lucide-react";
import { loginUser } from "@/lib/api/auth";
import { verifyBiometric, reportSecurityIncident } from "@/lib/api/biometric";
import { ApiError } from "@/lib/api/client";
import { setUser, setTokens, clearSession, isAuthenticated, getRole } from "@/lib/session";
import { motion, AnimatePresence } from "framer-motion";
import type { Role } from "@/lib/mock-data";
import { redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/admin-login")({
  head: () => ({ meta: [{ title: "Console Administrateur — EDG" }] }),
  beforeLoad: () => {
    if (isAuthenticated()) {
      // Admin déjà connecté → son espace admin
      if (getRole() === "admin") throw redirect({ to: "/app/admin/users" });
      // Autre rôle déjà connecté → son espace
      throw redirect({ to: "/app" });
    }
  },
  component: AdminLogin,
});

type BioPhase =
  | "idle"
  | "requesting"
  | "countdown"
  | "capturing"
  | "analyzing"
  | "match"
  | "no_match"
  | "denied"
  | "error";

// ── Security helpers ──────────────────────────────────────────────────────────

const FAIL_KEY = "edg.admin.fail_count";

function parseBrowser(ua: string): string {
  if (/Edg\//.test(ua)) return "Microsoft Edge";
  if (/OPR\/|Opera/.test(ua)) return "Opera";
  if (/Firefox\//.test(ua)) return "Firefox";
  if (/Chrome\//.test(ua)) return "Chrome";
  if (/Safari\//.test(ua)) return "Safari";
  return "Navigateur inconnu";
}

function parseOS(ua: string): string {
  if (/Windows NT 10/.test(ua)) return "Windows 10/11";
  if (/Windows NT 6\.3/.test(ua)) return "Windows 8.1";
  if (/Windows NT 6\.1/.test(ua)) return "Windows 7";
  if (/Mac OS X/.test(ua)) {
    const m = ua.match(/Mac OS X ([\d_]+)/);
    return m ? `macOS ${m[1].replace(/_/g, ".")}` : "macOS";
  }
  if (/Android/.test(ua)) {
    const m = ua.match(/Android ([\d.]+)/);
    return m ? `Android ${m[1]}` : "Android";
  }
  if (/iPhone OS|iPad/.test(ua)) {
    const m = ua.match(/OS ([\d_]+)/);
    return m ? `iOS ${m[1].replace(/_/g, ".")}` : "iOS";
  }
  if (/Linux/.test(ua)) return "Linux";
  return "OS inconnu";
}

function parseDevice(ua: string): string {
  if (/Mobi|Android(?!.*Tablet)|iPhone/.test(ua)) return "mobile";
  if (/iPad|Tablet|PlayBook/.test(ua)) return "tablet";
  return "desktop";
}

function getLocationApprox(): Promise<string | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) { resolve(null); return; }
    const timer = setTimeout(() => resolve(null), 3000);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        clearTimeout(timer);
        resolve(`${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`);
      },
      () => { clearTimeout(timer); resolve(null); },
      { timeout: 3000, maximumAge: 60000 },
    );
  });
}

// ── Main component ────────────────────────────────────────────────────────────

function AdminLogin() {
  const navigate = useNavigate();

  // Login form
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accessGranted, setAccessGranted] = useState(false);

  // Biometric
  const [bioPhase, setBioPhase] = useState<BioPhase>("idle");
  const [countdown, setCountdown] = useState(3);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [flash, setFlash] = useState(false);
  const [attemptedIdentifier, setAttemptedIdentifier] = useState("");

  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const capturedImageRef = useRef<string | null>(null);
  const securityMetaRef = useRef<{
    browser: string;
    os_info: string;
    device_type: string;
    location_approx: string | null;
    attempt_count: number;
  } | null>(null);

  // Callback ref: fires the instant React mounts the <video> element (even after
  // AnimatePresence delay). Attaches the stream immediately so readyState rises
  // before the countdown reaches 0.
  const setVideoRef = useCallback((el: HTMLVideoElement | null) => {
    videoRef.current = el;
    if (el && streamRef.current) {
      el.srcObject = streamRef.current;
      el.play().catch(() => {});
    }
  }, []);

  const canSubmit = identifier.trim().length > 0 && password.length > 0;
  const showBiometric = bioPhase !== "idle";

  // ── Camera helpers ──────────────────────────────────────────────────────

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
  }, []);

  const captureFrame = useCallback((): string | null => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState < 2) return null;
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.85);
  }, []);

  useEffect(() => () => stopCamera(), [stopCamera]);

  // ── Phase: requesting → open camera ─────────────────────────────────────
  // getUserMedia resolves before the <video> element is mounted (it only renders
  // in countdown/capturing phases). So we store the stream in the ref and switch
  // phase first; a dedicated effect attaches the stream once the DOM is ready.

  useEffect(() => {
    if (bioPhase !== "requesting") return;
    let cancelled = false;

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "user", width: 640, height: 480 } })
      .then((stream) => {
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        if (!cancelled) { setCountdown(3); setBioPhase("countdown"); }
      })
      .catch(() => { if (!cancelled) setBioPhase("denied"); });

    return () => { cancelled = true; };
  }, [bioPhase]);


  // ── Phase: countdown → tick every second ─────────────────────────────────

  useEffect(() => {
    if (bioPhase !== "countdown") return;
    if (countdown <= 0) { setBioPhase("capturing"); return; }
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [bioPhase, countdown]);

  // ── Phase: capturing → flash + grab frame ────────────────────────────────

  useEffect(() => {
    if (bioPhase !== "capturing") return;
    setFlash(true);
    const t = setTimeout(() => {
      const image = captureFrame();
      setFlash(false);
      if (!image) { setBioPhase("error"); return; }
      capturedImageRef.current = image;
      setCapturedImage(image);
      stopCamera();
      setBioPhase("analyzing");
    }, 350);
    return () => clearTimeout(t);
  }, [bioPhase, captureFrame, stopCamera]);

  // ── Phase: analyzing → API call ──────────────────────────────────────────

  useEffect(() => {
    if (bioPhase !== "analyzing") return;
    const image = capturedImageRef.current;
    if (!image) { setBioPhase("error"); return; }
    let cancelled = false;

    (async () => {
      try {
        const result = await verifyBiometric({ image, identifier: attemptedIdentifier });
        if (cancelled) return;

        if (result.match) {
          if (result.accessToken && result.user) {
            setTokens(result.accessToken, result.refreshToken!, result.expiresIn!);
            setUser({
              id: result.user.id,
              name: result.user.name,
              email: result.user.email,
              role: (result.user.role as Role) || "admin",
              phone: result.user.phone,
              avatar: result.user.avatar ?? undefined,
              direction_id: result.user.direction_id ?? undefined,
              unit_id: result.user.unit_id ?? undefined,
            });
          }
          sessionStorage.removeItem(FAIL_KEY);
          setBioPhase("match");
          setTimeout(() => { if (!cancelled) navigate({ to: "/app/admin/users" }); }, 1500);
        } else {
          try {
            const meta = securityMetaRef.current;
            await reportSecurityIncident({
              identifier: attemptedIdentifier,
              captured_image: image,
              timestamp: new Date().toISOString(),
              user_agent: navigator.userAgent,
              browser: meta?.browser,
              os_info: meta?.os_info,
              device_type: meta?.device_type,
              location_approx: meta?.location_approx ?? undefined,
              attempt_count: meta?.attempt_count ?? 1,
            });
          } catch { /* best-effort */ }
          if (!cancelled) setBioPhase("no_match");
        }
      } catch {
        try {
          const meta = securityMetaRef.current;
          await reportSecurityIncident({
            identifier: attemptedIdentifier,
            captured_image: image,
            timestamp: new Date().toISOString(),
            user_agent: navigator.userAgent,
            browser: meta?.browser,
            os_info: meta?.os_info,
            device_type: meta?.device_type,
            location_approx: meta?.location_approx ?? undefined,
            attempt_count: meta?.attempt_count ?? 1,
          });
        } catch { /* best-effort */ }
        if (!cancelled) setBioPhase("no_match");
      }
    })();

    return () => { cancelled = true; };
  }, [bioPhase, attemptedIdentifier, navigate]);

  // ── Login form submit ─────────────────────────────────────────────────────

  const handleSubmit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canSubmit || isLoading) return;

    setIsLoading(true);
    setError(null);
    const trimmedId = identifier.trim();
    const ua = navigator.userAgent;

    const triggerSecurity = (count: number) => {
      securityMetaRef.current = {
        browser: parseBrowser(ua),
        os_info: parseOS(ua),
        device_type: parseDevice(ua),
        location_approx: null,
        attempt_count: count,
      };
      // geolocation runs in background — fills in before countdown + capture completes
      getLocationApprox().then((loc) => {
        if (securityMetaRef.current) securityMetaRef.current.location_approx = loc;
      });
      setAttemptedIdentifier(trimmedId);
      setBioPhase("requesting");
    };

    try {
      const result = await loginUser({ identifier: trimmedId, password });

      if (result.user.role !== "admin") {
        clearSession();
        const count = parseInt(sessionStorage.getItem(FAIL_KEY) ?? "0", 10) + 1;
        sessionStorage.setItem(FAIL_KEY, String(count));
        if (count >= 2) {
          setError("Accès refusé — Ce compte ne dispose pas des privilèges administrateur. Vérification biométrique déclenchée.");
          triggerSecurity(count);
        } else {
          setError("Accès refusé — Ce compte ne dispose pas des privilèges administrateur système.");
          setAttemptedIdentifier(trimmedId);
        }
        return;
      }

      sessionStorage.removeItem(FAIL_KEY);
      setTokens(result.accessToken, result.refreshToken, result.expiresIn);
      setUser({
        id: result.user.id,
        name: result.user.name,
        email: result.user.email,
        role: (result.user.role as Role) || "admin",
        phone: result.user.phone,
        avatar: result.user.avatar,
        direction_id: result.user.direction_id ?? undefined,
        unit_id: result.user.unit_id ?? undefined,
      });

      setAccessGranted(true);
      setTimeout(() => navigate({ to: "/app/admin/users" }), 900);
    } catch (err) {
      setAttemptedIdentifier(trimmedId);

      if (err instanceof ApiError) {
        if (err.status === 401 && err.errorCode === "ACCOUNT_DISABLED") {
          setError("Ce compte administrateur est désactivé.");
        } else if (err.status === 401 || err.status === 422) {
          const count = parseInt(sessionStorage.getItem(FAIL_KEY) ?? "0", 10) + 1;
          sessionStorage.setItem(FAIL_KEY, String(count));
          if (count >= 2) {
            setError(
              err.status === 422
                ? "Identifiant invalide — Vérification biométrique déclenchée."
                : "Identifiant ou mot de passe incorrect — Vérification biométrique déclenchée.",
            );
            triggerSecurity(count);
          } else {
            setError(
              err.status === 422
                ? "Identifiant invalide. Vérifiez l'email saisi."
                : "Identifiant ou mot de passe incorrect.",
            );
          }
        } else {
          setError("Erreur de connexion. Vérifiez votre connexion réseau.");
        }
      } else {
        setError("Impossible de contacter le serveur. Vérifiez votre connexion.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-dvh grid place-items-center px-4 py-10">
      <canvas ref={canvasRef} className="hidden" />

      <div className="w-full max-w-md">
        {/* Header */}
        <div className="mb-8 flex flex-col items-center gap-3">
          <Link to="/" aria-label="Retour à l'accueil">
            <Logo size="xl" showText={false} />
          </Link>
          <div className="text-center">
            <p className="text-lg font-bold tracking-tight">
              EDG<span className="text-primary">-SUP</span>
            </p>
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground/70">
              EDG Support
            </p>
          </div>
        </div>

        <GlassCard strong className="p-8">
          <AnimatePresence mode="wait">
            {accessGranted ? (
              <motion.div
                key="granted"
                className="flex flex-col items-center gap-4 py-6"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ type: "spring", stiffness: 300, damping: 22 }}
              >
                <div className="flex h-16 w-16 items-center justify-center rounded-full bg-primary/10 ring-4 ring-primary/20 shadow-lg shadow-primary/20">
                  <ShieldCheck className="h-8 w-8 text-primary" strokeWidth={1.5} />
                </div>
                <div className="text-center">
                  <p className="text-base font-semibold tracking-tight">Accès autorisé</p>
                  <p className="mt-1 text-sm text-muted-foreground">Redirection vers la console…</p>
                </div>
                <div className="flex gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <motion.span
                      key={i}
                      className="h-1.5 w-1.5 rounded-full bg-primary"
                      animate={{ opacity: [0.3, 1, 0.3] }}
                      transition={{ duration: 1, delay: i * 0.2, repeat: Infinity }}
                    />
                  ))}
                </div>
              </motion.div>
            ) : (
              <motion.div key="form" initial={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="mb-6 flex items-start gap-3">
                  <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10">
                    <ShieldAlert className="h-5 w-5 text-primary" strokeWidth={1.5} />
                  </div>
                  <div>
                    <h1 className="text-2xl font-bold tracking-tight">Console Administrateur</h1>
                    <p className="mt-0.5 text-sm text-muted-foreground">
                      Accès réservé aux administrateurs système.
                    </p>
                  </div>
                </div>

                <div className="mb-5 flex items-start gap-2.5 rounded-xl border border-amber-500/20 bg-amber-500/8 px-3.5 py-2.5">
                  <TerminalSquare className="mt-0.5 h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400" />
                  <p className="text-xs leading-relaxed text-amber-700 dark:text-amber-400">
                    Zone d&apos;accès restreint — Toute tentative échouée déclenche automatiquement une vérification biométrique par caméra.
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <div>
                    <Label htmlFor="identifier">Adresse email administrateur</Label>
                    <Input
                      id="identifier"
                      type="email"
                      placeholder="admin@edg.gn"
                      value={identifier}
                      onChange={(e) => { setIdentifier(e.target.value); setError(null); }}
                      className="mt-1.5 h-12"
                      required
                      autoComplete="username"
                      inputMode="email"
                    />
                  </div>

                  <div>
                    <Label htmlFor="password">Mot de passe</Label>
                    <div className="relative mt-1.5">
                      <Input
                        id="password"
                        type={showPassword ? "text" : "password"}
                        placeholder="Votre mot de passe"
                        value={password}
                        onChange={(e) => { setPassword(e.target.value); setError(null); }}
                        className="h-12 pr-11"
                        required
                        autoComplete="current-password"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 text-muted-foreground transition-colors hover:text-foreground"
                        aria-label={showPassword ? "Masquer" : "Afficher"}
                      >
                        {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  <AnimatePresence>
                    {error && (
                      <motion.div
                        className="rounded-xl border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive"
                        initial={{ opacity: 0, y: -4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                      >
                        {error}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <Button
                    type="submit"
                    disabled={!canSubmit || isLoading || showBiometric}
                    className="h-12 w-full rounded-full gradient-primary shadow-lg shadow-primary/30"
                  >
                    {isLoading ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Vérification en cours…
                      </>
                    ) : (
                      <>
                        <ShieldCheck className="mr-2 h-4 w-4" />
                        Accéder à la console
                      </>
                    )}
                  </Button>
                </form>
              </motion.div>
            )}
          </AnimatePresence>
        </GlassCard>

        <p className="mt-4 text-center text-xs text-muted-foreground">
          <Link to="/login" className="hover:underline">← Connexion standard</Link>
          <span className="mx-2 opacity-40">·</span>
          <Link to="/" className="hover:underline">Portail public</Link>
        </p>
      </div>

      {/* ── Biometric overlay ── */}
      <AnimatePresence>
        {showBiometric && (
          <motion.div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-md"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
          >
            {/* Camera flash */}
            <AnimatePresence>
              {flash && (
                <motion.div
                  className="absolute inset-0 z-10 bg-white"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 0.9 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.12 }}
                />
              )}
            </AnimatePresence>

            <motion.div
              className="relative w-full max-w-sm"
              initial={{ scale: 0.85, opacity: 0, y: 24 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.85, opacity: 0, y: 24 }}
              transition={{ type: "spring", stiffness: 320, damping: 24 }}
            >
              <GlassCard strong className="overflow-hidden p-6">
                <BiometricPanel
                  phase={bioPhase}
                  countdown={countdown}
                  capturedImage={capturedImage}
                  videoRef={setVideoRef}
                  onRetry={() => {
                    capturedImageRef.current = null;
                    setCapturedImage(null);
                    setCountdown(3);
                    setBioPhase("requesting");
                  }}
                  onClose={() => setBioPhase("idle")}
                />
              </GlassCard>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ── Biometric panel ───────────────────────────────────────────────────────────

interface BiometricPanelProps {
  phase: BioPhase;
  countdown: number;
  capturedImage: string | null;
  videoRef: React.Ref<HTMLVideoElement>;
  onRetry: () => void;
  onClose: () => void;
}

const fadeScale = {
  initial: { opacity: 0, scale: 0.95 },
  animate: { opacity: 1, scale: 1 },
  exit: { opacity: 0, scale: 0.95 },
  transition: { duration: 0.18 },
};

function BiometricPanel({ phase, countdown, capturedImage, videoRef, onRetry, onClose }: BiometricPanelProps) {
  return (
    <div className="flex flex-col items-center gap-5">
      {/* Header */}
      <div className="flex w-full items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10">
          <Fingerprint className="h-5 w-5 text-primary" strokeWidth={1.5} />
        </div>
        <div>
          <p className="text-sm font-semibold leading-tight">Vérification biométrique</p>
          <p className="text-xs text-muted-foreground">Identification faciale automatique</p>
        </div>
      </div>

      <AnimatePresence mode="wait">

        {/* Requesting camera permission */}
        {phase === "requesting" && (
          <motion.div key="req" className="flex flex-col items-center gap-3 py-6" {...fadeScale}>
            <div className="relative flex h-16 w-16 items-center justify-center">
              <Camera className="h-8 w-8 text-primary" strokeWidth={1.5} />
              <motion.span
                className="absolute inset-0 rounded-full border-2 border-primary"
                animate={{ scale: [1, 1.4], opacity: [0.6, 0] }}
                transition={{ duration: 1, repeat: Infinity, ease: "easeOut" }}
              />
            </div>
            <p className="text-sm text-muted-foreground text-center">Activation de la caméra…</p>
            <p className="text-xs text-muted-foreground/60 text-center">
              Autorisez l&apos;accès à la caméra lorsque le navigateur le demande.
            </p>
          </motion.div>
        )}

        {/* Live camera + countdown */}
        {(phase === "countdown" || phase === "capturing") && (
          <motion.div key="cam" className="flex flex-col items-center gap-4 w-full" {...fadeScale}>
            <div className="relative aspect-square w-52 overflow-hidden rounded-full border-2 border-primary/50 shadow-lg shadow-primary/20">
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className="h-full w-full object-cover [transform:scaleX(-1)]"
              />

              {/* Scanning line */}
              {phase === "countdown" && (
                <motion.div
                  className="pointer-events-none absolute left-0 right-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent opacity-80"
                  animate={{ top: ["5%", "95%", "5%"] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "linear" }}
                />
              )}

              {/* Countdown number */}
              {phase === "countdown" && countdown > 0 && (
                <AnimatePresence mode="wait">
                  <motion.span
                    key={countdown}
                    className="absolute inset-0 flex items-center justify-center text-7xl font-black text-white drop-shadow-2xl"
                    initial={{ scale: 1.6, opacity: 0 }}
                    animate={{ scale: 1, opacity: 0.9 }}
                    exit={{ scale: 0.5, opacity: 0 }}
                    transition={{ duration: 0.3 }}
                  >
                    {countdown}
                  </motion.span>
                </AnimatePresence>
              )}

              {/* Corner brackets */}
              <div className="pointer-events-none absolute inset-4">
                <div className="absolute left-0 top-0 h-5 w-5 rounded-tl-sm border-l-2 border-t-2 border-primary" />
                <div className="absolute right-0 top-0 h-5 w-5 rounded-tr-sm border-r-2 border-t-2 border-primary" />
                <div className="absolute bottom-0 left-0 h-5 w-5 rounded-bl-sm border-b-2 border-l-2 border-primary" />
                <div className="absolute bottom-0 right-0 h-5 w-5 rounded-br-sm border-b-2 border-r-2 border-primary" />
              </div>
            </div>

            <p className="text-sm text-muted-foreground text-center">
              {phase === "capturing"
                ? "Capture en cours…"
                : "Regardez la caméra et restez immobile"}
            </p>
          </motion.div>
        )}

        {/* Analyzing */}
        {phase === "analyzing" && (
          <motion.div key="analyze" className="flex flex-col items-center gap-4 w-full" {...fadeScale}>
            {capturedImage && (
              <div className="relative aspect-square w-52 overflow-hidden rounded-full border-2 border-primary/30 shadow-lg shadow-primary/20">
                <img
                  src={capturedImage}
                  alt="Capture biométrique"
                  className="h-full w-full object-cover [transform:scaleX(-1)]"
                />
                <motion.div
                  className="absolute inset-0 bg-gradient-to-b from-primary/30 via-transparent to-primary/20"
                  animate={{ opacity: [0.4, 0.8, 0.4] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: "easeInOut" }}
                />
                {/* Scanning overlay */}
                <motion.div
                  className="pointer-events-none absolute left-0 right-0 h-1 bg-gradient-to-r from-transparent via-primary to-transparent opacity-90"
                  animate={{ top: ["0%", "100%"] }}
                  transition={{ duration: 1.2, repeat: Infinity, ease: "linear" }}
                />
              </div>
            )}
            <div className="flex flex-col items-center gap-2">
              <div className="flex gap-1.5">
                {[0, 1, 2, 3, 4].map((i) => (
                  <motion.span
                    key={i}
                    className="h-1.5 w-1.5 rounded-full bg-primary"
                    animate={{ opacity: [0.2, 1, 0.2], scale: [0.8, 1.2, 0.8] }}
                    transition={{ duration: 1, delay: i * 0.15, repeat: Infinity }}
                  />
                ))}
              </div>
              <p className="text-sm text-muted-foreground">Analyse biométrique en cours…</p>
            </div>
          </motion.div>
        )}

        {/* Match — access granted */}
        {phase === "match" && (
          <motion.div key="match" className="flex flex-col items-center gap-3 py-4" {...fadeScale}>
            <motion.div
              className="flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 ring-4 ring-emerald-500/20"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 18, delay: 0.1 }}
            >
              <CheckCircle2 className="h-9 w-9 text-emerald-500" />
            </motion.div>
            <div className="text-center">
              <p className="font-semibold text-emerald-600 dark:text-emerald-400">Identité confirmée</p>
              <p className="mt-0.5 text-sm text-muted-foreground">Accès accordé — Redirection vers la console…</p>
            </div>
            <div className="flex gap-1.5">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="h-1.5 w-1.5 rounded-full bg-emerald-500"
                  animate={{ opacity: [0.3, 1, 0.3] }}
                  transition={{ duration: 0.9, delay: i * 0.2, repeat: Infinity }}
                />
              ))}
            </div>
          </motion.div>
        )}

        {/* No match — alert sent */}
        {phase === "no_match" && (
          <motion.div key="nomatch" className="flex w-full flex-col items-center gap-4" {...fadeScale}>
            <motion.div
              className="flex h-16 w-16 items-center justify-center rounded-full bg-destructive/10 ring-4 ring-destructive/20"
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: "spring", stiffness: 300, damping: 18, delay: 0.1 }}
            >
              <XCircle className="h-9 w-9 text-destructive" />
            </motion.div>

            <div className="text-center space-y-1">
              <p className="font-semibold text-destructive">Identité non reconnue</p>
              <p className="text-sm text-muted-foreground">
                Une alerte de sécurité a été envoyée à l&apos;administrateur avec les coordonnées saisies et l&apos;image capturée.
              </p>
            </div>

            {capturedImage && (
              <div className="w-full rounded-xl border border-destructive/20 bg-destructive/5 p-3 text-center">
                <p className="mb-2 text-xs font-medium text-destructive/70">Image transmise à la sécurité</p>
                <img
                  src={capturedImage}
                  alt="Tentative capturée"
                  className="mx-auto h-16 w-16 rounded-full border border-destructive/30 object-cover [transform:scaleX(-1)]"
                />
              </div>
            )}

            <div className="flex w-full gap-2">
              <Button variant="outline" size="sm" className="flex-1" onClick={onClose}>
                Fermer
              </Button>
              <Button size="sm" className="flex-1 gradient-primary" onClick={onRetry}>
                Réessayer
              </Button>
            </div>
          </motion.div>
        )}

        {/* Camera denied */}
        {phase === "denied" && (
          <motion.div key="denied" className="flex flex-col items-center gap-3 py-4" {...fadeScale}>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-muted">
              <CameraOff className="h-7 w-7 text-muted-foreground" />
            </div>
            <div className="text-center space-y-1">
              <p className="font-semibold">Accès caméra refusé</p>
              <p className="text-sm text-muted-foreground">
                Autorisez la caméra dans les paramètres du navigateur pour activer la vérification biométrique.
              </p>
            </div>
            <Button variant="outline" className="w-full" onClick={onClose}>Fermer</Button>
          </motion.div>
        )}

        {/* Error */}
        {phase === "error" && (
          <motion.div key="err" className="flex flex-col items-center gap-3 py-4" {...fadeScale}>
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10">
              <AlertTriangle className="h-7 w-7 text-destructive" />
            </div>
            <div className="text-center space-y-1">
              <p className="font-semibold">Erreur de vérification</p>
              <p className="text-sm text-muted-foreground">
                La vérification biométrique a rencontré un problème inattendu.
              </p>
            </div>
            <div className="flex w-full gap-2">
              <Button variant="outline" className="flex-1" onClick={onClose}>Fermer</Button>
              <Button className="flex-1 gradient-primary" onClick={onRetry}>Réessayer</Button>
            </div>
          </motion.div>
        )}

      </AnimatePresence>
    </div>
  );
}
