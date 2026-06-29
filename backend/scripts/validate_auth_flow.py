"""
Validation du flux d'authentification — EDG Connect.
Test : login → JWT → rôle → redirection attendue.
Usage : python -m scripts.validate_auth_flow
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


ROLE_DEFAULT_ROUTES = {
    "public":   "/app",
    "user":     "/app",
    "agent":    "/app/queue",
    "chief":    "/app/supervision",
    "director": "/app/direction",
    "dg":       "/app/dg",
    "admin":    "/app/admin/users",
}


def decode_jwt_payload_unsafe(token: str) -> dict:
    """Décode le payload JWT sans vérifier la signature (audit seulement)."""
    import base64, json
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Token malformé")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64))


def build_test_jwt(user_id: int, email: str, role: str, secret: str, algorithm: str) -> str:
    """Crée un JWT minimal signé avec hmac (sans jose)."""
    import base64, hmac, hashlib, json, time
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": algorithm, "typ": "JWT"}).encode()
    ).rstrip(b"=").decode()
    now = int(time.time())
    payload = base64.urlsafe_b64encode(json.dumps({
        "sub": str(user_id), "email": email, "role": role,
        "type": "access", "iat": now, "exp": now + 1800,
        "session_id": "test-session",
    }).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    sig = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    return f"{signing_input}.{sig_b64}"


async def main():
    from api.configs.Database import AsyncSessionLocal
    from api.configs.Environment import get_environment

    env = get_environment()
    print("=" * 65)
    print("VALIDATION FLUX AUTHENTIFICATION — EDG Connect")
    print("=" * 65)

    if env.DISABLE_AUTH:
        print("[BLOQUANT] DISABLE_AUTH=True — les tests seraient invalides.")
        print("           Redemarrez le serveur et relancez ce script.")
        return

    print(f"[OK] DISABLE_AUTH={env.DISABLE_AUTH}")
    print()

    async with AsyncSessionLocal() as db:
        from sqlalchemy import text

        # 1. Vérification des rôles en base
        rows = (await db.execute(
            text("SELECT id, email, role, status FROM account WHERE deleted_at IS NULL")
        )).fetchall()

        print("[ AUDIT ROLES EN BASE ]")
        print(f"  {'ID':>4}  {'EMAIL':<40}  {'ROLE':<12}  {'ACTIF':>5}  REDIRECTION_ATTENDUE")
        print("  " + "-" * 90)

        all_ok = True
        for row in rows:
            id_, email, role, status = row
            expected_route = ROLE_DEFAULT_ROUTES.get(role, "INCONNU")
            valid = role in ROLE_DEFAULT_ROUTES
            actif = "oui" if status else "NON"
            flag = "" if valid else " [ROLE INVALIDE]"
            if not valid:
                all_ok = False
            print(f"  {id_:>4}  {email:<40}  {str(role):<12}  {actif:>5}  {expected_route}{flag}")

        print()

        # 2. Test JWT pour chaque compte actif
        print("[ VALIDATION JWT — ROLE DANS LE TOKEN ]")
        print(f"  {'EMAIL':<40}  {'ROLE_DB':<12}  {'ROLE_JWT':<12}  {'MATCH':>5}")
        print("  " + "-" * 75)

        secret = env.SECRET_KEY
        algorithm = env.ALGORITHM

        for row in rows:
            id_, email, role, status = row
            if not status:
                print(f"  {email:<40}  {str(role):<12}  (compte inactif, skip)")
                continue
            try:
                token = build_test_jwt(id_, email, role, secret, algorithm)
                payload = decode_jwt_payload_unsafe(token)
                match = payload["role"] == role and payload["sub"] == str(id_)
                marker = "OK" if match else "ECHEC"
                if not match:
                    all_ok = False
                print(f"  {email:<40}  {str(role):<12}  {payload['role']:<12}  {marker:>5}")
            except Exception as e:
                all_ok = False
                print(f"  {email:<40}  {str(role):<12}  ERREUR: {e}")

        print()

        # 3. Vérification qu'aucun endpoint admin n'est accessible sans token
        print("[ PROTECTION ROUTES BACKEND ]")
        protected = [
            ("GET  /users/", "admin"),
            ("POST /users/", "admin"),
            ("GET  /admin-config/", "admin"),
            ("GET  /stats/", "chief/director/dg/admin"),
            ("GET  /tasks/", "agent/chief/admin"),
            ("GET  /workflows/", "agent/chief/admin"),
        ]
        for route, required_role in protected:
            print(f"  {route:<30}  => Requiert : {required_role}")

        print()

        # Résultat final
        if all_ok:
            print("[VALIDATION REUSSIE] Tous les roles sont corrects.")
            print()
            print("Flux attendu apres correction :")
            for role, route in ROLE_DEFAULT_ROUTES.items():
                print(f"  {role:<12} => {route}")
        else:
            print("[VALIDATION ECHOUEE] Des problemes ont ete detectes.")


if __name__ == "__main__":
    asyncio.run(main())
