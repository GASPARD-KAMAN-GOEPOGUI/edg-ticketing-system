// Numéro mobile guinéen : +224 6XX XX XX XX, 224 6XX XX XX XX ou 6XX XX XX XX
// (espaces/tirets ignorés) — miroir de backend/api/core/phone.py::validate_guinea_phone.
const GUINEA_PHONE_RE = /^(?:\+?224)?6\d{8}$/;

export const PHONE_FORMAT_HINT = "+224 6XX XX XX XX, 224 6XX XX XX XX ou 6XX XX XX XX";

export function isValidGuineaPhone(raw: string): boolean {
  const cleaned = raw.trim().replace(/[\s.\-()]/g, "");
  return GUINEA_PHONE_RE.test(cleaned);
}
