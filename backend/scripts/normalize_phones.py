"""
Normalise tous les numéros de téléphone existants en base vers le format +224XXXXXXXXX.
Usage : pipenv run python scripts/normalize_phones.py
"""
import asyncio
import sys
import os
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_GUINEA_CODE = "224"


def _normalize(raw: str | None) -> str | None:
    if not raw:
        return raw
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return raw
    prefix_00 = "00" + _GUINEA_CODE
    prefix_cc = _GUINEA_CODE
    if digits.startswith(prefix_00):
        local = digits[len(prefix_00):]
    elif digits.startswith(prefix_cc) and len(digits) > 9:
        local = digits[len(prefix_cc):]
    else:
        local = digits
    return f"+{_GUINEA_CODE}{local}"


async def main() -> None:
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text

    async with AsyncSession(engine) as session:
        rows = await session.execute(
            text("SELECT id, phone FROM account WHERE phone IS NOT NULL AND phone != ''")
        )
        accounts = rows.fetchall()

        updated = 0
        skipped = 0
        errors = 0

        for row in accounts:
            account_id, phone = row.id, row.phone
            normalized = _normalize(phone)
            if normalized == phone:
                skipped += 1
                continue
            try:
                await session.execute(
                    text("UPDATE account SET phone = :phone WHERE id = :id"),
                    {"phone": normalized, "id": account_id},
                )
                print(f"  ✓ id={account_id}  {phone!r} → {normalized!r}")
                updated += 1
            except Exception as exc:
                print(f"  ✗ id={account_id}  {phone!r} — erreur : {exc}")
                errors += 1

        await session.commit()
        print(f"\n=== Terminé — {updated} mis à jour, {skipped} déjà OK, {errors} erreur(s) ===")


asyncio.run(main())
