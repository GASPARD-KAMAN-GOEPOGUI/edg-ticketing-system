"""
Diagnostic complet des comptes admin.
Usage: pipenv run python scripts/diag_admin.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

EMAIL    = "gaspardKamangoepogui@gmail.com"
PASSWORD = "Admin@EDG2024!"

async def main():
    from api.configs.Database import engine
    from api.core.security import verify_password
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text

    async with AsyncSession(engine) as session:
        rows = await session.execute(text(
            "SELECT id, email, role, status, deleted_at, "
            "LEFT(password_hash,30) AS hash_prefix "
            "FROM account WHERE role='admin'"
        ))
        admins = rows.fetchall()
        print("=== Comptes admin ===")
        for r in admins:
            print(f"  id={r.id}  email={r.email}  status={r.status}  deleted_at={r.deleted_at}  hash={r.hash_prefix}...")

        # Test du mot de passe pour le premier admin
        full = await session.execute(text(
            "SELECT id, email, password_hash, status, deleted_at FROM account WHERE role='admin' LIMIT 1"
        ))
        target = full.fetchone()
        if target:
            ok = verify_password(PASSWORD, target.password_hash)
            print(f"\n=== Test password pour id={target.id} ({target.email}) ===")
            print(f"  verify_password('{PASSWORD}', hash) => {ok}")
            print(f"  status={target.status}  deleted_at={target.deleted_at}")
            if ok and target.status and target.deleted_at is None:
                print("  => DEVRAIT FONCTIONNER")
            elif not ok:
                print("  => ECHEC : mot de passe incorrect")
            elif not target.status:
                print("  => ECHEC : compte desactive (status=False)")
            elif target.deleted_at is not None:
                print("  => ECHEC : compte supprime (deleted_at set)")

asyncio.run(main())
