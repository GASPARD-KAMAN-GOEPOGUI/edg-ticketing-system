"""
Logger centralisé EDG Connect.

Fournit :
  - Niveau SUCCESS (25) entre INFO et WARNING
  - Formatter coloré avec icônes et noms de module
  - Fonction get_logger(name) à utiliser dans chaque service / repo
  - Fonction setup_logging() à appeler au démarrage de l'app

Usage dans un service :
    from api.core.logger import get_logger
    logger = get_logger(__name__)

    logger.info("Création d'un compte — email=test@edg.gn")
    logger.success("Compte créé — id=abc123")
    logger.warning("Direction inexistante — id=DIR-001")
    logger.error("Impossible de créer le compte")
"""
from __future__ import annotations

import logging
import sys
from typing import Optional

# ── Niveau SUCCESS ────────────────────────────────────────────────────────────

_SUCCESS_LEVEL = 25
logging.addLevelName(_SUCCESS_LEVEL, "SUCCESS")


def _success_method(self: logging.Logger, message: str, *args, **kwargs) -> None:
    """Méthode success() injectée dans logging.Logger."""
    if self.isEnabledFor(_SUCCESS_LEVEL):
        self._log(_SUCCESS_LEVEL, message, args, **kwargs)


logging.Logger.success = _success_method  # type: ignore[attr-defined]


# ── Couleurs ANSI ─────────────────────────────────────────────────────────────

class _C:
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    # Niveaux
    DEBUG   = "\033[36m"       # Cyan
    INFO    = "\033[34m"       # Bleu
    SUCCESS = "\033[32m"       # Vert
    WARNING = "\033[33m"       # Jaune orange
    ERROR   = "\033[31m"       # Rouge
    CRITICAL= "\033[35;1m"     # Magenta bold
    # Structure
    TIME    = "\033[90m"       # Gris foncé
    MODULE  = "\033[96m"       # Cyan clair
    SEP     = "\033[90m"       # Gris foncé


_LEVEL_MAP: dict[int, tuple[str, str]] = {
    logging.DEBUG:   (_C.DEBUG,    "DEBUG  "),
    logging.INFO:    (_C.INFO,     "INFO   "),
    _SUCCESS_LEVEL:  (_C.SUCCESS,  "SUCCESS"),
    logging.WARNING: (_C.WARNING,  "WARNING"),
    logging.ERROR:   (_C.ERROR,    "ERROR  "),
    logging.CRITICAL:(_C.CRITICAL, "CRITIC "),
}


# ── Formatter ────────────────────────────────────────────────────────────────

class _EDGFormatter(logging.Formatter):
    """
    Format de sortie :
      2026-06-08 21:30:00 INFO    │ [service.Account        ] Création d'un compte...
      2026-06-08 21:30:00 SUCCESS │ [service.Account        ] ✅ Compte créé — id=abc
      2026-06-08 21:30:00 WARNING │ [service.Account        ] ⚠️  Direction inexistante
      2026-06-08 21:30:00 ERROR   │ [exception_handlers     ] ❌ ACCOUNT_NOT_FOUND...
    """

    def format(self, record: logging.LogRecord) -> str:
        color, level_label = _LEVEL_MAP.get(record.levelno, (_C.RESET, f"{record.levelname:<7}"))
        dt = self.formatTime(record, "%Y-%m-%d %H:%M:%S")

        # Raccourcir le nom du logger pour l'affichage
        name = record.name
        if name.startswith("edg."):
            name = name[4:]
        name = name[-24:] if len(name) > 24 else name

        msg = record.getMessage()

        # Ajouter l'exception si présente (version condensée)
        if record.exc_info and record.exc_info[0] is not None:
            exc_type = record.exc_info[0].__name__
            exc_val  = str(record.exc_info[1])
            msg = f"{msg} [{exc_type}: {exc_val[:120]}]"

        return (
            f"{_C.TIME}{dt}{_C.RESET} "
            f"{color}{_C.BOLD}{level_label}{_C.RESET} "
            f"{_C.SEP}│{_C.RESET} "
            f"{_C.MODULE}[{name:<24}]{_C.RESET} "
            f"{color}{msg}{_C.RESET}"
        )


# ── API publique ──────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """
    Retourne un logger EDG configuré pour le module donné.
    Le nom est automatiquement préfixé par 'edg.' pour filtrage.

    Exemple :
        logger = get_logger("service.Account")
        # → edg.service.Account
    """
    full_name = f"edg.{name}" if not name.startswith("edg.") else name
    logger = logging.getLogger(full_name)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(_EDGFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    logger.setLevel(logging.DEBUG)
    return logger


def setup_logging(debug: bool = False) -> None:
    """
    Configure le logging global au démarrage de l'application.
    À appeler une seule fois dans main.py (lifespan ou module scope).

    - debug=True  → niveau DEBUG, logs SQLAlchemy visibles
    - debug=False → niveau INFO, SQLAlchemy silencieux
    """
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)

    # Supprimer les handlers existants pour éviter les doublons
    root.handlers.clear()
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(_EDGFormatter())
    root.addHandler(console)

    # Réduire le bruit des bibliothèques tierces
    _quiet = [
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "httpx",
        "httpcore",
        "uvicorn.access",
        "multipart",
        "passlib",
    ]
    for lib in _quiet:
        logging.getLogger(lib).setLevel(
            logging.DEBUG if debug else logging.WARNING
        )

    # Garder les logs importants d'uvicorn
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("fastapi").setLevel(logging.INFO)
