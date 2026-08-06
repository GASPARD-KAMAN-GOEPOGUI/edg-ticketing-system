from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.error_codes import ErrorCode
from api.core.phone import normalize_phone
from api.core.rbac import normalize_role
from api.core.ref_validation import check_ref_code
from api.core.security import hash_password, verify_password
from api.models.ModelOrganigram import Organigram
from api.models.ModelUnity import Unity
from api.repositories import AccountRepository, AccountStatusRepository
from api.services.base_service import BaseService


class AccountService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AccountRepository(session)

    # ── Helpers internes ──────────────────────────────────────────────────────

    def _auto_edg_employee(self, data: dict) -> dict:
        """
        Si la clé 'matricule' est présente dans data, positionne automatiquement
        is_edg_employee selon qu'un matricule non vide est fourni ou non.
        Sans override explicite de is_edg_employee dans data.
        """
        if "matricule" in data and "is_edg_employee" not in data:
            data["is_edg_employee"] = bool(data.get("matricule"))
        return data

    async def _check_phone_unique(self, phone: str, exclude_id: int | None = None) -> None:
        found = await self.repo.find_by_phone(phone)
        if found and (exclude_id is None or found.id != exclude_id):
            raise self.conflict(
                "Ce numéro de téléphone est déjà utilisé par un autre compte.",
                error_code=ErrorCode.PHONE_ALREADY_EXISTS,
                field="phone",
                value=phone,
                hint="Chaque numéro de téléphone doit être unique.",
            )

    async def _check_matricule_unique(self, matricule: str, exclude_id: int | None = None) -> None:
        found = await self.repo.find_by_matricule(matricule)
        if found and (exclude_id is None or found.id != exclude_id):
            raise self.conflict(
                "Ce matricule est déjà utilisé par un autre compte.",
                error_code=ErrorCode.MATRICULE_ALREADY_EXISTS,
                field="matricule",
                value=matricule,
                hint="Chaque matricule doit être unique. Vérifiez la valeur saisie.",
            )

    @staticmethod
    def _org_kind_from(unity: Unity, org: Organigram) -> str:
        infos = unity.infos if isinstance(unity.infos, dict) else {}
        raw_kind = str(infos.get("org_type") or "").strip().lower()
        if raw_kind in {"direction", "department", "unit"}:
            return raw_kind

        label = (unity.label or "").strip().lower()
        if label.startswith("direction"):
            return "direction"
        if label.startswith(("département", "departement")):
            return "department"
        if label.startswith(("service", "unité", "unite", "secrétariat", "secretariat", "cabinet")):
            return "unit"
        return "direction" if org.parent_id is None else "unit"

    async def _active_org_kind(self, unity_id: int) -> str:
        row = await self.session.execute(
            select(Organigram, Unity)
            .join(Unity, Organigram.unity_id == Unity.id)
            .where(
                Organigram.unity_id == unity_id,
                Organigram.deleted_at.is_(None),
                Unity.deleted_at.is_(None),
                Organigram.status.is_(True),
                Unity.status.is_(True),
            )
            .limit(1)
        )
        match = row.first()
        if not match:
            raise self.bad_request(
                "L'affectation organisationnelle sélectionnée est introuvable ou inactive.",
                error_code="INVALID_ORG_ASSIGNMENT",
                field="unity_id",
                hint="Sélectionnez une direction, un département ou une unité active.",
            )
        org, unity = match
        return self._org_kind_from(unity, org)

    async def _validate_role_org_assignment(
        self,
        *,
        role: str,
        unity_id: int | None,
    ) -> None:
        role = normalize_role(role)
        if role == "public":
            return

        if role == "director":
            allowed = {"direction"}
            message = "La direction est obligatoire pour ce rôle."
            hint = "Affectez ce compte à une direction active."
        elif role in {"chief-service", "chief-departement"}:
            allowed = {"department", "unit"}
            message = "Le chef doit être affecté à un département ou à un service actif."
            hint = "Sélectionnez Chef de département ou Chef de service dans le formulaire admin."
        elif role in {"user", "agent-support", "admin"}:
            allowed = {"unit"}
            message = "Le service ou l'unité est obligatoire pour ce rôle."
            hint = "Affectez ce compte à une unité active appartenant à un département."
        else:
            return

        if unity_id is None:
            raise self.bad_request(
                message,
                error_code="ORG_ASSIGNMENT_REQUIRED",
                field="unity_id",
                hint=hint,
            )

        kind = await self._active_org_kind(int(unity_id))
        if kind not in allowed:
            raise self.bad_request(
                "L'affectation organisationnelle ne correspond pas au rôle sélectionné.",
                error_code="INVALID_ORG_ASSIGNMENT_FOR_ROLE",
                field="unity_id",
                hint=hint,
            )

    # ── Listes ────────────────────────────────────────────────────────────────

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="name", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_role(self, role: str, *, page: int = 1, limit: int = 50):
        role = normalize_role(role)
        items, total = await self.repo.list_by_role(role, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_agents(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_agents(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_direction(self, direction_id: int, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_direction(direction_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_unit(self, unit_id: int, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_unit(unit_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_role_and_direction(self, role: str, direction_id: int, *, page: int = 1, limit: int = 50):
        role = normalize_role(role)
        items, total = await self.repo.list_by_role_and_direction(role, direction_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_role_and_unit(self, role: str, unit_id: int, *, page: int = 1, limit: int = 50):
        role = normalize_role(role)
        items, total = await self.repo.list_by_role_and_unit(role, unit_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    # ── Lecture ───────────────────────────────────────────────────────────────

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found(
                "Ce compte utilisateur n'existe pas.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="id",
                value=id,
                hint="Vérifiez que l'identifiant du compte est correct.",
            )
        return obj

    async def get_by_uuid(self, uuid: str):
        obj = await self.repo.get_by_uuid(uuid)
        if obj is None:
            raise self.not_found(
                "Ce compte utilisateur n'existe pas.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="uuid",
                value=uuid,
            )
        return obj

    async def get_by_email(self, email: str):
        obj = await self.repo.find_by_email(email)
        if obj is None:
            raise self.not_found(
                f"Aucun compte associé à l'adresse email '{email}'.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="email",
                value=email,
            )
        return obj

    async def get_by_keycloak_id(self, keycloak_id: str):
        obj = await self.repo.find_by_keycloak_id(keycloak_id)
        if obj is None:
            raise self.not_found(
                "Compte Keycloak introuvable.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="keycloak_id",
                value=keycloak_id,
            )
        return obj

    async def get_by_matricule(self, matricule: str):
        obj = await self.repo.find_by_matricule(matricule)
        if obj is None:
            raise self.not_found(
                f"Aucun compte avec le matricule '{matricule}'.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="matricule",
                value=matricule,
            )
        return obj

    # ── Écriture ──────────────────────────────────────────────────────────────

    async def create(self, data: dict, *, validate_org_assignment: bool = False):
        self._logger.info(f"Création d'un compte — email={data.get('email')!r}")

        unit_id = data.pop("unit_id", None)
        department_id = data.pop("department_id", None)
        direction_id = data.pop("direction_id", None)
        if not data.get("unity_id"):
            if unit_id is not None:
                data["unity_id"] = unit_id
            elif department_id is not None:
                data["unity_id"] = department_id
            elif direction_id is not None:
                data["unity_id"] = direction_id
        if data.get("role"):
            data["role"] = normalize_role(data["role"])

        # Unicité e-mail
        existing = await self.repo.find_by_email(data.get("email", ""))
        if existing:
            raise self.conflict(
                "Cette adresse email est déjà utilisée.",
                error_code=ErrorCode.EMAIL_ALREADY_EXISTS,
                field="email",
                value=data.get("email"),
                hint="Utilisez une adresse email différente ou connectez-vous à votre compte existant.",
            )

        # Unicité matricule
        if data.get("matricule"):
            await self._check_matricule_unique(data["matricule"])

        # Normalisation + unicité téléphone
        if data.get("phone"):
            data["phone"] = normalize_phone(data["phone"])
            await self._check_phone_unique(data["phone"])

        # Validation référentiel account_status
        if data.get("account_status"):
            await check_ref_code(self.session, AccountStatusRepository, data["account_status"], "account_status")

        # Auto is_edg_employee
        data = self._auto_edg_employee(data)

        if validate_org_assignment:
            await self._validate_role_org_assignment(
                role=data.get("role", "user"),
                unity_id=data.get("unity_id"),
            )

        obj = await self.repo.create(data)
        self._logger.info(f"✅ Compte créé — id={obj.id}")
        return obj

    async def update(self, id: int, data: dict, *, validate_org_assignment: bool = False):
        self._logger.info(f"Mise à jour du compte — id={id}")

        current = await self.repo.get_by_id(id)
        if current is None:
            raise self.not_found(
                "Ce compte utilisateur n'existe pas.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="id",
                value=id,
            )

        # unit_id/direction_id ne sont pas de vraies colonnes (alias frontend) —
        # seul unity_id l'est. Sans cette traduction, ces valeurs étaient
        # silencieusement ignorées par le filtrage de colonnes du repository.
        unit_id = data.pop("unit_id", None)
        department_id = data.pop("department_id", None)
        direction_id = data.pop("direction_id", None)
        if not data.get("unity_id"):
            if unit_id is not None:
                data["unity_id"] = unit_id
            elif department_id is not None:
                data["unity_id"] = department_id
            elif direction_id is not None:
                data["unity_id"] = direction_id
        if data.get("role"):
            data["role"] = normalize_role(data["role"])

        # Unicité e-mail
        if data.get("email"):
            existing = await self.repo.find_by_email(data["email"])
            if existing and existing.id != id:
                raise self.conflict(
                    "Cette adresse email est déjà utilisée par un autre compte.",
                    error_code=ErrorCode.EMAIL_ALREADY_EXISTS,
                    field="email",
                    value=data["email"],
                    hint="Utilisez une adresse email différente.",
                )
        # Si l'email change, invalider la vérification d'email (nécessite nouvelle vérification)
        if data.get("email") and current.email and data.get("email") != current.email:
            data["email_verified"] = False

        # Unicité matricule
        if data.get("matricule"):
            await self._check_matricule_unique(data["matricule"], exclude_id=id)

        # Normalisation + unicité téléphone
        if data.get("phone"):
            data["phone"] = normalize_phone(data["phone"])
            await self._check_phone_unique(data["phone"], exclude_id=id)

        # Validation référentiel account_status
        if data.get("account_status"):
            await check_ref_code(self.session, AccountStatusRepository, data["account_status"], "account_status")

        # Auto is_edg_employee
        data = self._auto_edg_employee(data)

        if validate_org_assignment and ("role" in data or "unity_id" in data):
            await self._validate_role_org_assignment(
                role=data.get("role", current.role),
                unity_id=data.get("unity_id", current.unity_id),
            )

        obj = await self.repo.update(id, data)
        return obj

    async def delete(self, id: int) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def set_availability(self, id: int, availability: str):
        obj = await self.repo.set_availability(id, availability)
        if obj is None:
            raise self.not_found(
                "Ce compte utilisateur n'existe pas.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="id",
                value=id,
            )
        return obj

    async def verify_email(self, id: int):
        obj = await self.repo.verify_email(id)
        if obj is None:
            raise self.not_found(
                "Ce compte utilisateur n'existe pas.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="id",
                value=id,
            )
        return obj

    async def activate(self, id: int) -> bool:
        await self.get_by_id(id)
        return await self.repo.activate(id)

    async def deactivate(self, id: int) -> bool:
        await self.get_by_id(id)
        return await self.repo.deactivate(id)

    async def search(self, q: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def set_role(self, id: int, role: str):
        return await self.update(id, {"role": normalize_role(role)}, validate_org_assignment=True)

    # ── Auth ──────────────────────────────────────────────────────────────────

    async def register(self, data: dict):
        """
        Crée un compte avec un mot de passe haché Argon2.
        Le rôle est TOUJOURS forcé à 'user' — toute valeur client est ignorée.
        Lève ConflictException si l'email/matricule/téléphone est déjà utilisé.
        """
        plain_password = data.pop("password", None)
        if not plain_password:
            raise self.bad_request(
                "Un mot de passe est requis.",
                error_code="PASSWORD_REQUIRED",
                field="password",
            )
        data["role"] = "user"  # C-01 — auto-élévation impossible
        obj = await self.create(data)
        await self.repo.update(obj.id, {"password_hash": hash_password(plain_password)})
        return await self.repo.get_by_id(obj.id)

    async def authenticate(self, identifier: str, password: str):
        """
        Cherche un compte par email, téléphone ou matricule, vérifie le mot de passe.
        Retourne le compte si l'authentification réussit.
        Lève UnauthorizedException sinon.
        """
        from api.core.exceptions import UnauthorizedException
        from api.core.phone import is_phone_identifier

        import re as _re

        # 1. Email
        obj = await self.repo.find_by_email(identifier)
        # 2. Téléphone (détection automatique du format)
        if obj is None and is_phone_identifier(identifier):
            normalized = normalize_phone(identifier)
            obj = await self.repo.find_by_phone(normalized)
            if obj is None:
                # Fallback : essayer les chiffres seuls (comptes non encore normalisés)
                digits = _re.sub(r"[^\d]", "", identifier)
                if digits != normalized:
                    obj = await self.repo.find_by_phone(digits)
                    if obj is None and digits != normalized.lstrip("+"):
                        obj = await self.repo.find_by_phone("+" + digits)
        # 3. Matricule
        if obj is None and not identifier.startswith("@"):
            obj = await self.repo.find_by_matricule(identifier)

        if obj is None or not obj.password_hash:
            raise UnauthorizedException("Identifiant ou mot de passe incorrect.")

        if not verify_password(password, obj.password_hash):
            raise UnauthorizedException("Identifiant ou mot de passe incorrect.")

        if not obj.status or obj.deleted_at is not None:
            from api.core.exceptions import UnauthorizedException as UE
            raise UE(
                "Compte désactivé. Contactez l'administration EDG.",
                error_code="ACCOUNT_DISABLED",
            )

        return obj

    async def change_password(self, id: int, current_password: str, new_password: str):
        """Permet à un utilisateur de changer son propre mot de passe."""
        from api.core.exceptions import UnauthorizedException

        obj = await self.get_by_id(id)
        if not obj.password_hash or not verify_password(current_password, obj.password_hash):
            raise UnauthorizedException(
                "Mot de passe actuel incorrect.",
                error_code="WRONG_PASSWORD",
            )
        return await self.repo.update(id, {"password_hash": hash_password(new_password)})

    async def set_password(self, id: int, new_password: str):
        """Réinitialisation admin : définit un nouveau mot de passe sans vérifier l'ancien."""
        await self.get_by_id(id)
        return await self.repo.update(id, {"password_hash": hash_password(new_password)})
