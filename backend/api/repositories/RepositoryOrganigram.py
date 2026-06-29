from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelOrganigram import Organigram
from api.repositories.base_repository import BaseRepository


class OrganigramRepository(BaseRepository[Organigram]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Organigram, session)

    async def find_by_unity(self, unity_id: int) -> Organigram | None:
        return await self.get_one({"unity_id": unity_id})

    async def list_roots(self) -> list[Organigram]:
        """Retourne les nœuds racines (sans parent)."""
        items, _ = await self.list(
            filters={"parent_id": None},
            only_active=True,
            order_by="id",
            page=1,
            limit=500,
        )
        return items

    async def list_children(self, parent_id: int) -> list[Organigram]:
        """Retourne les enfants directs d'un nœud."""
        items, _ = await self.list(
            filters={"parent_id": parent_id},
            only_active=True,
            order_by="id",
            page=1,
            limit=500,
        )
        return items

    async def get_ancestors(self, organigram_id: int) -> list[dict]:
        sql = text("""
            WITH RECURSIVE ancestors AS (
                SELECT o.id, o.unity_id, o.parent_id, 0 AS level
                FROM organigram o
                WHERE o.id = :oid AND o.deleted_at IS NULL

                UNION ALL

                SELECT o.id, o.unity_id, o.parent_id, a.level + 1
                FROM organigram o
                JOIN ancestors a ON o.id = a.parent_id
                WHERE o.deleted_at IS NULL
            )
            SELECT id, unity_id, parent_id, level
            FROM ancestors
            WHERE level > 0
            ORDER BY level
        """)
        result = await self.session.execute(sql, {"oid": organigram_id})
        return [dict(r) for r in result.mappings().all()]

    async def get_descendants(self, organigram_id: int) -> list[dict]:
        sql = text("""
            WITH RECURSIVE subtree AS (
                SELECT o.id, o.unity_id, o.parent_id, 0 AS level
                FROM organigram o
                WHERE o.parent_id = :oid AND o.deleted_at IS NULL

                UNION ALL

                SELECT o.id, o.unity_id, o.parent_id, s.level + 1
                FROM organigram o
                JOIN subtree s ON o.parent_id = s.id
                WHERE o.deleted_at IS NULL
            )
            SELECT id, unity_id, parent_id, level
            FROM subtree
            ORDER BY level, id
        """)
        result = await self.session.execute(sql, {"oid": organigram_id})
        return [dict(r) for r in result.mappings().all()]

    async def get_tree_json(self, root_id: int) -> dict:
        sql = text("""
            WITH RECURSIVE tree AS (
                SELECT o.id, o.unity_id, o.parent_id, 0 AS level
                FROM organigram o
                WHERE o.id = :root_id AND o.deleted_at IS NULL

                UNION ALL

                SELECT o.id, o.unity_id, o.parent_id, t.level + 1
                FROM organigram o
                JOIN tree t ON o.parent_id = t.id
                WHERE o.deleted_at IS NULL
            )
            SELECT id, unity_id, parent_id, level
            FROM tree
            ORDER BY level, id
        """)
        result = await self.session.execute(sql, {"root_id": root_id})
        rows = result.mappings().all()

        nodes: dict = {r["id"]: {**dict(r), "children": []} for r in rows}
        root = None
        for r in rows:
            node = nodes[r["id"]]
            pid = r["parent_id"]
            if r["id"] == root_id:
                root = node
            elif pid in nodes:
                nodes[pid]["children"].append(node)

        return {"root_id": root_id, "tree": root}
