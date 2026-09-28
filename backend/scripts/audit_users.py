"""
Script d'audit des comptes — vérifie rôles, statuts, doublons.
Usage : python -m scripts.audit_users (depuis le dossier backend/)
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main():
    from api.configs.Database import AsyncSessionLocal
    from api.configs.Environment import get_environment

    env = get_environment()
    print("=" * 60)
    print("AUDIT COMPTES — EDG Connect")
    print("=" * 60)
    print(f"DISABLE_AUTH : {env.DISABLE_AUTH}")
    print(f"APP_ENV      : {env.APP_ENV}")
    print()

    if env.DISABLE_AUTH:
        print("[CRITIQUE] DISABLE_AUTH=True — tout get_current_user retourne l'admin !")
        print("           Relancez le serveur apres avoir mis DISABLE_AUTH=False dans .env")
        print()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        result = await db.execute(
            text("SELECT id, email, role, account_status, status, deleted_at, created_at FROM account ORDER BY id")
        )
        rows = result.fetchall()

        print(f"{'ID':>4}  {'EMAIL':<35}  {'ROLE':<12}  {'ACC_STATUS':<10}  {'ACTIF':>5}  {'SUPPRIME':>8}")
        print("-" * 90)

        issues = []
        valid_roles = {
            "public", "user", "chief-service", "chief-service", "chief-departement",
            "director", "admin",
        }

        for row in rows:
            id_, email, role, acc_status, status, deleted_at, created_at = row
            flag = ""
            if role not in valid_roles:
                flag = " [ROLE INVALIDE]"
                issues.append(f"id={id_} email={email} role invalide: {role!r}")
            if role is None:
                flag = " [ROLE NULL]"
                issues.append(f"id={id_} email={email} role NULL")
            if deleted_at is not None:
                flag += " [SUPPRIME]"

            supprime = "OUI" if deleted_at else "non"
            actif = "oui" if status else "NON"
            print(f"{id_:>4}  {email:<35}  {str(role):<12}  {str(acc_status):<10}  {actif:>5}  {supprime:>8}{flag}")

        print()
        if issues:
            print(f"[PROBLEMES DETECTES] {len(issues)}")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print("[OK] Aucun role invalide ou null detecte.")

        # Verifier sessions actives
        try:
            result2 = await db.execute(
                text("SELECT a.email, a.role, COUNT(s.id) as sessions FROM account a LEFT JOIN active_session s ON s.user_id = a.id AND s.revoked = 0 GROUP BY a.id, a.email, a.role ORDER BY a.id")
            )
            sessions = result2.fetchall()
            print()
            print("SESSIONS ACTIVES PAR COMPTE")
            print("-" * 50)
            for email, role, count in sessions:
                print(f"  {email:<35}  {str(role):<12}  {count} session(s)")
        except Exception as e:
            print(f"  (impossible de lire active_session: {e})")


if __name__ == "__main__":
    asyncio.run(main())
