"""
ServiceBiometric — Reconnaissance faciale via InsightFace (ArcFace / ONNX).

Modèle : buffalo_l (ArcFace ResNet50 + détection SCRFD-10G)
• Compatible Python 3.14 — pas de TensorFlow requis (ONNX Runtime)
• Modèles téléchargés automatiquement (~360 Mo) au premier appel
  dans ~/.insightface/models/buffalo_l/

Score de confiance : confidence = max(0, cosine_similarity * 100)
  • même personne (bonnes conditions)    : ≈ 60–90 %
  • même personne (conditions difficiles): ≈ 40–65 %
  • personnes différentes                : ≈ 0–35 %

Variable d'environnement BIOMETRIC_THRESHOLD (défaut : 40.0)
  • 50 % → haute sécurité  (similarity cosinus ≥ 0.50)
  • 40 % → standard        (similarity cosinus ≥ 0.40)
  • 30 % → tolérant        (similarity cosinus ≥ 0.30)

Anti-usurpation : analyse de texture (variance Laplacienne).
  Si l'image semble trop nette/plate (photo imprimée ou écran),
  BIOMETRIC_ANTI_SPOOFING=true bloque la vérification.
  Ce filtre heuristique complète l'analyse ArcFace — une vérification
  ML anti-spoofing complète (MiniFASNet) peut être ajoutée ultérieurement.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
import threading
from typing import Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────

BIOMETRIC_THRESHOLD: float = float(os.getenv("BIOMETRIC_THRESHOLD", "40.0"))
BIOMETRIC_ANTI_SPOOFING: bool = os.getenv("BIOMETRIC_ANTI_SPOOFING", "true").lower() == "true"

# ── InsightFace lazy init (thread-safe) ───────────────────────────────────────

_face_app = None
_app_lock = threading.Lock()


def _get_face_app():
    global _face_app
    if _face_app is not None:
        return _face_app
    with _app_lock:
        if _face_app is not None:
            return _face_app
        try:
            from insightface.app import FaceAnalysis
        except ImportError as exc:
            raise RuntimeError(
                "insightface non installé. Exécutez : pip install insightface onnxruntime opencv-python-headless"
            ) from exc
        logger.info("InsightFace : chargement du modèle buffalo_l (premier appel)…")
        app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        _face_app = app
        logger.info("InsightFace : modèle chargé avec succès")
    return _face_app


# ── Helpers ───────────────────────────────────────────────────────────────────

class SpoofDetectedError(Exception):
    """Levée quand l'image ne passe pas le contrôle anti-usurpation."""


def _b64_to_bgr(b64_str: str) -> np.ndarray:
    """Décode un base64 pur (sans préfixe data:) en image BGR numpy."""
    raw = base64.b64decode(b64_str)
    buf = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Impossible de décoder l'image (format invalide)")
    return img


def _confidence_from_similarity(similarity: float) -> float:
    """Convertit la similarité cosinus ArcFace [-1, 1] en score 0-100 %."""
    return round(max(0.0, similarity * 100.0), 1)


def _check_spoof_heuristic(img_bgr: np.ndarray) -> None:
    """
    Heuristique anti-spoofing basée sur la variance Laplacienne.
    Une image capturée en direct d'une vraie personne présente une variance
    naturelle ; une photo imprimée ou affichée sur écran tend à avoir
    des zones très nettes ou une texture caractéristique de scan.

    Note : ce filtre peut lever un faux positif si la caméra est très basse
    résolution. Désactiver avec BIOMETRIC_ANTI_SPOOFING=false si nécessaire.
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Seuil bas → image trop floue (webcam très mauvaise qualité) → laisser passer
    # Seuil haut → l'image est parfaitement nette → suspect (photo/écran)
    # Valeurs empiriques; à calibrer selon la caméra
    SPOOF_UPPER = float(os.getenv("BIOMETRIC_SPOOF_LAPLACIAN_UPPER", "3000"))
    if laplacian_var > SPOOF_UPPER:
        logger.warning(
            "Anti-spoofing heuristique : variance Laplacienne=%.1f > seuil=%.1f"
            " — image suspecte (possible photo ou écran)",
            laplacian_var,
            SPOOF_UPPER,
        )
        raise SpoofDetectedError(
            f"Image suspecte détectée (variance={laplacian_var:.0f}) — "
            "veuillez utiliser une caméra en direct"
        )


def load_reference_image(avatar_url: str) -> str | None:
    """
    Charge la photo de référence (avatar) et la retourne en base64 pur.
    Accepte : chemin local, chemin /api/v1/..., URL http(s)://...
    """
    import urllib.request

    try:
        if not avatar_url:
            return None

        if avatar_url.startswith("data:"):
            return avatar_url.split(",", 1)[1] if "," in avatar_url else None

        if avatar_url.startswith(("http://", "https://")):
            with urllib.request.urlopen(avatar_url, timeout=5) as resp:  # noqa: S310
                return base64.b64encode(resp.read()).decode()

        # Chemin local — résolution depuis la racine du backend
        backend_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        rel = avatar_url.lstrip("/")
        for prefix in ("api/v1/", "api/"):
            if rel.startswith(prefix):
                rel = rel[len(prefix):]
                break
        file_path = os.path.join(backend_root, rel)

        if not os.path.isfile(file_path):
            logger.warning(
                "Avatar introuvable : %s (résolu : %s)", avatar_url, file_path
            )
            return None

        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    except Exception as exc:
        logger.warning("Impossible de charger l'avatar (%s) : %s", avatar_url, exc)
        return None


# ── Vérification synchrone (dans le thread pool) ─────────────────────────────

def _run_verification(live_b64: str, ref_b64: str) -> Tuple[bool, float]:
    app = _get_face_app()

    # Décodage
    live_img = _b64_to_bgr(live_b64)
    ref_img = _b64_to_bgr(ref_b64)

    # Contrôle anti-usurpation heuristique sur l'image en direct
    if BIOMETRIC_ANTI_SPOOFING:
        _check_spoof_heuristic(live_img)

    # Détection des visages
    live_faces = app.get(live_img)
    ref_faces = app.get(ref_img)

    if not live_faces:
        raise ValueError("Aucun visage détecté dans l'image en direct")
    if not ref_faces:
        raise ValueError("Aucun visage détecté dans la photo de référence")

    # Utilise le visage avec le meilleur score de détection
    live_face = max(live_faces, key=lambda f: f.det_score)
    ref_face = max(ref_faces, key=lambda f: f.det_score)

    # Similarité cosinus — embeddings déjà normalisés L2 par ArcFace
    similarity = float(np.dot(live_face.normed_embedding, ref_face.normed_embedding))
    confidence = _confidence_from_similarity(similarity)
    match = confidence >= BIOMETRIC_THRESHOLD

    logger.info(
        "Biometric | similarity=%.4f confidence=%.1f%% threshold=%.1f%% "
        "det_live=%.3f det_ref=%.3f => %s",
        similarity,
        confidence,
        BIOMETRIC_THRESHOLD,
        live_face.det_score,
        ref_face.det_score,
        "MATCH" if match else "NO_MATCH",
    )

    return match, confidence


# ── Interface publique asynchrone ─────────────────────────────────────────────

async def verify_faces(live_b64: str, ref_b64: str) -> Tuple[bool, float]:
    """
    Compare un visage capturé (base64 pur) avec la photo de référence.
    Retourne (match: bool, confidence: float 0-100).
    S'exécute dans le thread pool pour ne pas bloquer la boucle asyncio.
    """
    return await asyncio.to_thread(_run_verification, live_b64, ref_b64)
