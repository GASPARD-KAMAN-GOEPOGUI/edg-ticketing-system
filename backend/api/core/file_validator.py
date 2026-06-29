"""
Validation des fichiers par signature binaire (magic bytes).

Garantit que le contenu réel du fichier correspond à son type déclaré,
indépendamment du Content-Type HTTP fourni par le client.

Formats autorisés : image/jpeg · image/png · image/webp · application/pdf
"""
from __future__ import annotations

from fastapi import HTTPException

# ── Signatures binaires ───────────────────────────────────────────────────────

_SIGNATURES: dict[bytes, str] = {
    b"\xFF\xD8\xFF":                             "image/jpeg",   # JFIF / EXIF
    b"\x89\x50\x4E\x47\x0D\x0A\x1A\x0A":        "image/png",    # PNG
    b"%PDF-":                                     "application/pdf",
}

_WEBP_RIFF   = b"RIFF"
_WEBP_MARKER = b"WEBP"

_ALLOWED_MIME = frozenset(_SIGNATURES.values()) | {"image/webp"}

_LABELS = {
    "image/jpeg":       "JPEG",
    "image/png":        "PNG",
    "image/webp":       "WebP",
    "application/pdf":  "PDF",
}


def _detect_mime(data: bytes) -> str | None:
    """
    Retourne le MIME réel détecté depuis les magic bytes,
    ou None si le format est inconnu / non supporté.
    """
    if len(data) < 4:
        return None

    # WebP: RIFF????WEBP
    if data[:4] == _WEBP_RIFF and len(data) >= 12 and data[8:12] == _WEBP_MARKER:
        return "image/webp"

    # Signature fixe (JPEG, PNG, PDF)
    for sig, mime in _SIGNATURES.items():
        if data[: len(sig)] == sig:
            return mime

    return None


def validate_file_magic_bytes(data: bytes, declared_mime: str) -> str:
    """
    Valide le fichier par ses magic bytes et retourne le MIME réel détecté.

    - Lève HTTP 422 si le fichier est vide / trop court.
    - Lève HTTP 422 si le format réel n'est pas dans la liste autorisée.
    - Lève HTTP 422 si le MIME déclaré ne correspond pas au format réel
      (tentative de spoofing Content-Type).

    Retourne le MIME réel (à utiliser à la place du Content-Type client).
    """
    if len(data) < 8:
        raise HTTPException(
            status_code=422,
            detail="Fichier vide ou tronqué — impossible de déterminer le type.",
        )

    real_mime = _detect_mime(data)

    if real_mime is None:
        allowed = ", ".join(sorted(_LABELS.values()))
        raise HTTPException(
            status_code=422,
            detail=(
                f"Format de fichier non reconnu. "
                f"Formats autorisés : {allowed}."
            ),
        )

    if real_mime != declared_mime:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Incohérence de type : le fichier est un {_LABELS[real_mime]} "
                f"mais Content-Type indique « {declared_mime} ». "
                "Requête rejetée."
            ),
        )

    return real_mime
