"""
Couche de stockage de fichiers — EDG Support.

Par défaut : stockage local dans uploads/.
Extension point MinIO : remplacer les méthodes par des appels boto3/aiobotocore.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from urllib.parse import quote

from api.configs.Environment import get_environment

_env = get_environment()

# Répertoire local de stockage (relatif au backend/)
_UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)


def save_file(data: bytes, filename: str, request_id: str) -> tuple[str, str]:
    """
    Sauvegarde le fichier et retourne (storage_path, public_url).

    storage_path : chemin logique stocké en DB (ex: "requests/abc123/photo.jpg")
    public_url   : URL téléchargeable par le frontend
    """
    # TODO MINIO: remplacer par client.put_object(Bucket=..., Key=storage_path, Body=data)
    safe = "".join(c if c.isalnum() or c in (".", "-", "_") else "_" for c in filename)
    unique = f"{uuid.uuid4().hex[:8]}_{safe}"
    storage_path = f"requests/{request_id}/{unique}"

    dest = _UPLOAD_DIR / "requests" / request_id
    dest.mkdir(parents=True, exist_ok=True)
    (dest / unique).write_bytes(data)

    public_url = f"/api/v1/requests/download/{quote(storage_path, safe='/')}"
    return storage_path, public_url


def delete_file(storage_path: str) -> None:
    """Supprime le fichier du stockage."""
    # TODO MINIO: client.delete_object(Bucket=..., Key=storage_path)
    full = _UPLOAD_DIR / storage_path
    if full.exists():
        full.unlink(missing_ok=True)


def presigned_url(storage_path: str, expires: int = 3600) -> str:
    """
    Retourne une URL pré-signée (ou équivalent local).
    En local : URL directe. En MinIO : URL temporaire S3.
    """
    # TODO MINIO: return client.presigned_get_object(Bucket=..., Key=storage_path, expires=expires)
    return f"/api/v1/requests/download/{quote(storage_path, safe='/')}"
