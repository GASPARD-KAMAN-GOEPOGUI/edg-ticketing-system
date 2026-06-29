"""
Service ClamAV — analyse antivirus des pièces jointes.

Protocole : INSTREAM via TCP socket asyncio (compatible clamd 0.99+).
Ne nécessite aucune dépendance tierce — utilise uniquement asyncio.

Statuts retournés :
  "clean"      — fichier sain
  "infected"   — menace détectée (threat_name fourni)
  "scan_error" — le daemon est inaccessible ou a retourné une erreur inattendue

EICAR test string (base64, pour les tests) :
  X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*
"""
from __future__ import annotations

import asyncio
import logging
import struct
from typing import Literal, NamedTuple

from api.configs.Environment import get_environment

_env = get_environment()
logger = logging.getLogger(__name__)

# EICAR test string — string standard de test antivirus (inoffensif)
EICAR_TEST_STRING = (
    b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
)

ScanStatus = Literal["clean", "infected", "scan_error"]

_CHUNK_SIZE = 4096  # octets par chunk INSTREAM


class ScanResult(NamedTuple):
    status: ScanStatus
    threat_name: str | None  # ex: "Win.Test.EICAR_HDB-1"


async def scan_bytes(data: bytes) -> ScanResult:
    """
    Envoie `data` au daemon clamd via le protocole INSTREAM et retourne le résultat.

    Si CLAMAV_ENABLED est False, retourne ("clean", None) sans connexion réseau
    afin que le code fonctionne en développement sans clamd installé.
    """
    if not _env.CLAMAV_ENABLED:
        return ScanResult(status="clean", threat_name=None)

    try:
        return await asyncio.wait_for(
            _scan_instream(data),
            timeout=float(_env.CLAMAV_TIMEOUT),
        )
    except asyncio.TimeoutError:
        logger.error(
            "ClamAV timeout après %d s — clamd injoignable ou trop lent.",
            _env.CLAMAV_TIMEOUT,
        )
        return ScanResult(status="scan_error", threat_name=None)
    except Exception as exc:
        logger.error("ClamAV erreur inattendue : %s", exc)
        return ScanResult(status="scan_error", threat_name=None)


async def _scan_instream(data: bytes) -> ScanResult:
    """
    Protocole INSTREAM :
      1. Ouvrir TCP vers clamd
      2. Envoyer  zINSTREAM\\0
      3. Envoyer les données en chunks : [uint32-be length][data]
      4. Terminer avec [uint32-be 0]
      5. Lire la réponse : "stream: OK\0" ou "stream: <threat> FOUND\0"
    """
    reader, writer = await asyncio.open_connection(
        _env.CLAMAV_HOST, _env.CLAMAV_PORT
    )
    try:
        # Commande initiale (zCOMMAND = nul-terminated)
        writer.write(b"zINSTREAM\0")

        # Envoi des données en chunks
        offset = 0
        while offset < len(data):
            chunk = data[offset : offset + _CHUNK_SIZE]
            writer.write(struct.pack(">I", len(chunk)))
            writer.write(chunk)
            offset += len(chunk)

        # Terminaison
        writer.write(struct.pack(">I", 0))
        await writer.drain()

        # Lecture de la réponse
        response = await reader.read(1024)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    return _parse_response(response.decode("utf-8", errors="replace").strip("\0").strip())


def _parse_response(response: str) -> ScanResult:
    """
    Exemple de réponses clamd :
      "stream: OK"
      "stream: Win.Test.EICAR_HDB-1 FOUND"
      "stream: ERROR — ..."
    """
    if response.endswith("OK"):
        return ScanResult(status="clean", threat_name=None)

    if response.endswith("FOUND"):
        # Format : "stream: <threat_name> FOUND"
        parts = response.split(": ", 1)
        threat = parts[1].removesuffix(" FOUND") if len(parts) == 2 else "unknown"
        return ScanResult(status="infected", threat_name=threat)

    logger.warning("ClamAV réponse inattendue : %r", response)
    return ScanResult(status="scan_error", threat_name=None)
