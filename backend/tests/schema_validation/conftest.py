"""
Fixtures communes pour la validation des schémas Pydantic.
"""
from __future__ import annotations

from datetime import datetime

import pytest


# ── Dates / IDs de référence ──────────────────────────────────────────────────

NOW = datetime(2026, 1, 15, 10, 30, 0)
FAKE_ID = "a" * 32  # 32-char hex UUID


# ── Payload BaseResponse minimal ─────────────────────────────────────────────

@pytest.fixture
def base_response_data() -> dict:
    return {
        "id": FAKE_ID,
        "status": True,
        "infos": None,
        "created_at": NOW,
        "updated_at": NOW,
        "deleted_at": None,
    }
