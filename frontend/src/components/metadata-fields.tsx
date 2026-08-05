import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Lock, Plus, X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Role } from "@/lib/mock-data";

// ── Sensitive key definitions ─────────────────────────────────────────────────

/** Keys that are always sensitive regardless of pattern match. */
const SENSITIVE_KEYS_EXPLICIT = new Set<string>([
  // IP / réseau
  "ip", "adresse_ip", "ip_country",
  // Identifiants utilisateur / session
  "user_id", "userId", "session_id",
  // Navigateur / client
  "user_agent", "userAgent",
  // Sécurité / forensique
  "fingerprint", "payload", "waf_rule",
]);

/** Returns true for any key that is considered sensitive. */
function isSensitiveKey(key: string): boolean {
  if (SENSITIVE_KEYS_EXPLICIT.has(key)) return true;
  // Identifiants internes en snake_case  (rule_id, article_id, …)
  if (/_id$/.test(key)) return true;
  // Identifiants internes en camelCase (userId, requestId, …)
  if (/[a-z]Id$/.test(key)) return true;
  return false;
}

/** Roles that may see sensitive metadata fields. */
function canViewSensitive(role: Role | undefined): boolean {
  return role === "admin";
}

// ── Key / value helpers ───────────────────────────────────────────────────────

const KEY_LABELS: Record<string, string> = {
  from: "De",
  to: "Vers",
  user_id: "Utilisateur",
  ref: "Référence ticket",
  ip: "Adresse IP",
  mfa: "Authentification MFA",
  attempts: "Tentatives échouées",
  blocked: "Bloqué",
  rule: "Règle déclenchée",
  level: "Niveau d'escalade",
  new_status: "Nouveau statut",
  previous_status: "Statut précédent",
  resolution_h: "Durée de résolution (h)",
  sla_breach_h: "Dépassement délai (h)",
  sla_ok: "Délai respecté",
  responseH: "Délai réponse (h)",
  resolutionH: "Délai résolution (h)",
  previous_responseH: "Délai réponse précédent (h)",
  previous_resolutionH: "Délai résolution précédent (h)",
  size_mb: "Taille (Mo)",
  duration_min: "Durée (min)",
  rule_id: "ID règle",
  article_id: "ID article",
  fingerprint: "Signature WAF",
  waf_rule: "Règle WAF",
  payload: "Charge détectée",
  assigned_to: "Assigné à (ID)",
  agent_name: "Agent",
  team: "Équipe",
  escalated_to: "Escaladé vers",
  approved_by: "Approuvé par",
  reason: "Raison",
  ip_country: "Pays IP",
  tables: "Tables sauvegardées",
  success: "Succès",
  compressed: "Compressé",
  session_id: "ID de session",
  lockout_min: "Blocage (min)",
  channel: "Canal",
  attachments: "Pièces jointes",
  affected_users: "Utilisateurs affectés",
  auto_recovered: "Récupération auto.",
  device: "Appareil",
  csat_rating: "Note CSAT",
  keywords: "Mots-clés",
  target_service: "Service cible",
  visible_to: "Visible par",
  tags: "Étiquettes",
};

const MONO_KEYS = new Set([
  "user_id", "ref", "ip", "rule_id", "article_id", "fingerprint",
  "waf_rule", "assigned_to", "payload", "session_id",
]);

const BOOL_KEYS = new Set([
  "mfa", "blocked", "success", "compressed", "sla_ok", "auto_recovered",
]);

function labelFor(key: string): string {
  if (KEY_LABELS[key]) return KEY_LABELS[key];
  return key
    .replace(/_/g, " ")
    .replace(/([A-Z])/g, " $1")
    .replace(/^./, (c) => c.toUpperCase())
    .trim();
}

function formatValue(key: string, value: unknown): { display: string; mono: boolean } {
  if (value === null || value === undefined) return { display: "—", mono: false };
  if (typeof value === "boolean" || BOOL_KEYS.has(key)) {
    return { display: value === true || value === 1 ? "Oui" : "Non", mono: false };
  }
  if (Array.isArray(value)) return { display: (value as unknown[]).join(", "), mono: false };
  if (typeof value === "object") return { display: JSON.stringify(value), mono: true };
  return { display: String(value), mono: MONO_KEYS.has(key) };
}

// ── Component ─────────────────────────────────────────────────────────────────

type Extra = { key: string; value: string };

type Props = {
  data: Record<string, unknown>;
  /** Rôle du visiteur — détermine quels champs sensibles sont visibles. */
  viewerRole?: Role;
  /** Active la section « Ajouter un champ » (admin uniquement). */
  isAdmin?: boolean;
};

export function MetadataFields({ data, viewerRole, isAdmin }: Props) {
  const [extras, setExtras] = useState<Extra[]>([]);
  const [newKey, setNewKey] = useState("");
  const [newVal, setNewVal] = useState("");

  const privileged = canViewSensitive(viewerRole);

  const baseEntries = Object.entries(data);
  // Filtrage des champs sensibles pour les rôles non-privilégiés
  const sensitiveWasRemoved =
    !privileged && baseEntries.some(([k]) => isSensitiveKey(k));
  const visibleBaseEntries = privileged
    ? baseEntries
    : baseEntries.filter(([k]) => !isSensitiveKey(k));

  const extraEntries = extras.map((e) => [e.key, e.value] as [string, string]);
  const allEntries: [string, unknown][] = [...visibleBaseEntries, ...extraEntries];

  function addField() {
    const k = newKey.trim();
    if (!k) return;
    setExtras((p) => [...p, { key: k, value: newVal.trim() }]);
    setNewKey("");
    setNewVal("");
  }

  function removeExtra(idx: number) {
    setExtras((p) => p.filter((_, i) => i !== idx));
  }

  if (allEntries.length === 0 && !isAdmin && !sensitiveWasRemoved) {
    return <p className="text-xs text-muted-foreground italic">Aucune métadonnée.</p>;
  }

  return (
    <div className="space-y-1.5">
      {allEntries.map(([key, value], i) => {
        const { display, mono } = formatValue(key, value);
        const isExtra = i >= visibleBaseEntries.length;
        const extraIdx = i - visibleBaseEntries.length;
        return (
          <div
            key={`${key}-${i}`}
            className="flex items-start gap-3 rounded-lg bg-card/40 px-3 py-2 text-xs"
          >
            <span className="w-2/5 shrink-0 text-muted-foreground leading-relaxed">
              {labelFor(key)}
            </span>
            <span
              className={cn(
                "flex-1 break-all text-right leading-relaxed",
                mono && "font-mono text-[11px]",
              )}
            >
              {display}
            </span>
            {isExtra && isAdmin && (
              <button
                onClick={() => removeExtra(extraIdx)}
                className="shrink-0 text-muted-foreground hover:text-destructive transition-colors"
                aria-label="Supprimer"
              >
                <X className="h-3 w-3" />
              </button>
            )}
          </div>
        );
      })}

      {allEntries.length === 0 && !sensitiveWasRemoved && (
        <p className="text-xs text-muted-foreground italic px-1">Aucune métadonnée.</p>
      )}

      {/* Mention discrète si des champs sensibles ont été masqués */}
      {sensitiveWasRemoved && (
        <div className="flex items-center gap-1.5 rounded-lg bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          <Lock className="h-3 w-3 shrink-0" />
          <span>Certaines métadonnées techniques sont réservées à l'administrateur.</span>
        </div>
      )}

      {/* Section « Ajouter un champ » — admin uniquement */}
      {isAdmin && (
        <div className="mt-3 space-y-2 border-t border-border/40 pt-3">
          <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground px-1">
            Ajouter un champ
          </p>
          <div className="flex gap-2">
            <Input
              value={newKey}
              onChange={(e) => setNewKey(e.target.value)}
              placeholder="Clé"
              className="h-8 text-xs rounded-lg"
            />
            <Input
              value={newVal}
              onChange={(e) => setNewVal(e.target.value)}
              placeholder="Valeur"
              className="h-8 text-xs rounded-lg flex-1"
              onKeyDown={(e) => e.key === "Enter" && addField()}
            />
            <Button
              size="icon"
              variant="outline"
              className="h-8 w-8 shrink-0 rounded-lg"
              onClick={addField}
              aria-label="Ajouter"
            >
              <Plus className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
