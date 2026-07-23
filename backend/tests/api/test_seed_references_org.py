from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import select

from tests.conftest import _TestSession


@pytest.mark.asyncio
async def test_seed_references_respects_soft_deleted_unity_and_organigram(monkeypatch):
    from api import seed_references as seed_module
    from api.models.ModelOrganigram import Organigram
    from api.models.ModelUnity import Unity

    codename = "CODX-SEED-DEL"
    deleted_at = datetime.utcnow()

    async with _TestSession() as session:
        unity = Unity(
            label="Direction seed supprimee",
            codename=codename,
            aleas="CSD",
            status=True,
            deleted_at=deleted_at,
        )
        session.add(unity)
        await session.flush()

        org = Organigram(
            unity_id=unity.id,
            parent_id=None,
            status=True,
            deleted_at=deleted_at,
        )
        session.add(org)
        await session.commit()

        monkeypatch.setattr(
            seed_module,
            "_UNITIES",
            [{"codename": codename, "label": "Direction seed supprimee", "aleas": "CSD", "description": None}],
        )
        monkeypatch.setattr(seed_module, "_ORGANIGRAM_TREE", [(codename, None)])

        await seed_module.seed_references(session)

        stored_unity = (
            await session.execute(select(Unity).where(Unity.codename == codename))
        ).scalar_one()
        stored_org = (
            await session.execute(select(Organigram).where(Organigram.unity_id == stored_unity.id))
        ).scalar_one()

        assert stored_unity.deleted_at is not None
        assert stored_org.deleted_at is not None
