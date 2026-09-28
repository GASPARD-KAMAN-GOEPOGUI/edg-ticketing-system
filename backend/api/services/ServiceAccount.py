from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core import central_auth, mailer
from api.core.error_codes import ErrorCode
from api.core.event_bus import AppEvent, emit as emit_event
from api.core.logger import get_logger
from api.core.phone import normalize_phone
from api.core.rbac import normalize_role
from api.models.ModelOrganigram import Organigram
from api.models.ModelUnity import Unity
from api.repositories import AccountRepository
from api.services.base_service import BaseService
from api.services.NotificationEmitter import _send_email_fire_and_forget

_CENTRAL_NOT_LINKED_MESSAGE = "Ce compte n'est pas rattaché à la plateforme centrale."

_account_email_logger = get_logger("service.AccountService.email")


async def _dispatch_account_email(*, kind: str, account_id: int, email: str, name: str) -> None:
    """
    Envoi fire-and-forget de l'email de création/association de compte (§6) —
    même mécanisme que NotificationEmitter._send_email_fire_and_forget (le SMTP
    peut prendre plusieurs secondes, ça ne doit jamais retarder la réponse HTTP
    d'inscription/connexion). Ouvre sa PROPRE session DB pour persister le flag
    anti-doublon dans account.infos : la session de la requête d'origine est déjà
    fermée quand ce coroutine s'exécute (même pattern que core/scheduler.py).

    Ne relève jamais d'exception — la validation du compte (déjà commitée avant
    cet appel) ne doit jamais dépendre du succès de l'envoi de l'email.
    """
    send_fn = (
        mailer.send_account_created_email if kind == "created"
        else mailer.send_account_associated_email
    )
    try:
        sent = await send_fn(email, name)
    except Exception as exc:
        sent = False
        _account_email_logger.warning(
            "Email compte (%s) — échec inattendu (account_id=%s email=%r) : %s",
            kind, account_id, email, exc,
        )
    _account_email_logger.info(
        "Email compte (%s) — account_id=%s email=%r envoyé=%s",
        kind, account_id, email, sent,
    )
    if not sent:
        return

    flag_key = "account_created_email_sent_at" if kind == "created" else "app_associated_email_sent_at"
    try:
        from api.configs.Database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await AccountRepository(session).update_infos(account_id, {
                flag_key: datetime.utcnow().isoformat(),
            })
    except Exception as exc:
        _account_email_logger.warning(
            "Email compte (%s) — flag anti-doublon non persisté (account_id=%s) : %s",
            kind, account_id, exc,
        )


class AccountService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AccountRepository(session)

    # ── Helpers internes ──────────────────────────────────────────────────────

    @staticmethod
    def _fold_intervenant_status(data: dict, current=None) -> dict:
        """Traduit `intervenant_status` (PV EDG/PS-GSI/PV-01) vers `infos`.

        Pas de colonne dédiée : la table `account` est partagée avec la
        plateforme centrale et son schéma n'est pas modifié. La valeur est donc
        FUSIONNÉE dans `infos` — jamais substituée — pour ne pas effacer ce que
        ce champ porte déjà (indicateur d'e-mail de bienvenue, entre autres)."""
        from api.models.ModelAccount import INTERVENANT_STATUSES

        if "intervenant_status" not in data:
            return data
        status = data.pop("intervenant_status")
        base = data.get("infos")
        if not isinstance(base, dict):
            existing = getattr(current, "infos", None) if current is not None else None
            base = dict(existing) if isinstance(existing, dict) else {}
        else:
            base = dict(base)
        if status in INTERVENANT_STATUSES:
            base["intervenant_status"] = status
        elif status in (None, ""):
            base.pop("intervenant_status", None)
        else:
            raise ValueError(f"Statut d'intervenant invalide : {status!r}")
        data["infos"] = base
        return data

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
                "Ce badge est déjà utilisé par un autre compte.",
                error_code=ErrorCode.MATRICULE_ALREADY_EXISTS,
                field="matricule",
                value=matricule,
                hint="Chaque badge doit être unique. Vérifiez la valeur saisie.",
            )

    def _notify_account_created(self, account) -> None:
        """
        Email A (§6) — déclenché uniquement depuis create(), juste après la
        persistance locale qui elle-même ne survient qu'après une réponse de
        succès de central_auth.create_central_account() (aucune exception levée
        entretemps). Envoi en fire-and-forget (SMTP hors du chemin critique de
        la réponse HTTP d'inscription, cf. _dispatch_account_email). Idempotence :
        flag horodaté dans account.infos — chaque ligne Account n'est de toute
        façon créée qu'une fois (email/central_user_id uniques), ce flag protège
        surtout un futur appel additionnel (ex. resend manuel) plutôt qu'un
        doublon dans ce flux lui-même.
        """
        infos = account.infos or {}
        if infos.get("account_created_email_sent_at"):
            return
        full_name = f"{account.firstname or ''} {account.name or ''}".strip() or account.name
        _send_email_fire_and_forget(_dispatch_account_email(
            kind="created", account_id=account.id, email=account.email, name=full_name,
        ))

    def _notify_account_associated(self, account) -> None:
        """
        Email B (§6) — déclenché uniquement depuis provision_from_central(),
        appelée uniquement après revalidation centrale réussie (scopes/groupes
        re-vérifiés par dependencies.py::resolve_or_provision_login_account ou
        RouteAuth.py::accept_consent). Ne jamais mentionner de "groupe" dans le
        message — uniquement l'association à l'application.
        """
        infos = account.infos or {}
        if infos.get("app_associated_email_sent_at"):
            return
        full_name = f"{account.firstname or ''} {account.name or ''}".strip() or account.name
        _send_email_fire_and_forget(_dispatch_account_email(
            kind="associated", account_id=account.id, email=account.email, name=full_name,
        ))

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

        if role in {"user", "chief-service", "technicien", "chef-division-support", "admin"}:
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

    async def list_by_ids(self, ids: list[int]):
        """Fetch batch par IDs — évite le N+1 (un appel HTTP par auteur/demandeur
        unique) côté frontend sur les écrans qui affichent plusieurs comptes liés
        (auteurs de commentaires, demandeurs de tickets…)."""
        if not ids:
            return self.paginate([], 0, 1, 1)
        items, total = await self.repo.list(
            filters={"id": ids}, order_by="name", limit=len(ids),
        )
        return self.paginate(items, total, 1, len(ids))

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

    async def get_by_central_user_id(self, central_user_id: int):
        obj = await self.repo.find_by_central_user_id(central_user_id)
        if obj is None:
            raise self.not_found(
                "Compte introuvable pour cette identité centrale.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="central_user_id",
                value=central_user_id,
            )
        return obj

    async def get_by_matricule(self, matricule: str):
        obj = await self.repo.find_by_matricule(matricule)
        if obj is None:
            raise self.not_found(
                f"Aucun compte avec le badge '{matricule}'.",
                error_code=ErrorCode.ACCOUNT_NOT_FOUND,
                field="matricule",
                value=matricule,
            )
        return obj

    # ── Écriture ──────────────────────────────────────────────────────────────

    async def create(
        self, data: dict, *, validate_org_assignment: bool = False, actor_bearer_token: str | None = None,
    ):
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

        # Unicité e-mail (locale, avant tout appel réseau)
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


        # Auto is_edg_employee
        data = self._auto_edg_employee(data)
        try:
            data = self._fold_intervenant_status(data)
        except ValueError as exc:
            raise self.bad_request(
                str(exc), error_code=ErrorCode.INVALID_FIELD_VALUE, field="intervenant_status",
            )

        if validate_org_assignment:
            await self._validate_role_org_assignment(
                role=data.get("role", "user"),
                unity_id=data.get("unity_id"),
            )

        # ── Création centrale (README §12) — TOUJOURS avant l'écriture locale.
        # Invariant : aucun compte local ne doit exister sans identité centrale.
        password = data.pop("password")
        group_codename = central_auth.group_for_role(data.get("role", "user"))
        # BR-CENTRAL-CREATE-SOURCE-TOKEN-001 — la création de compte central
        # s'authentifie désormais par source_token (dans create_central_account),
        # plus par token machine ; celui-ci n'est récupéré que si l'activation
        # ci-dessous s'avère nécessaire.
        central_result = await central_auth.create_central_account(
            group_codename=group_codename,
            email=data["email"],
            phone=data.get("phone") or "",
            firstname=data.get("firstname") or data["name"],
            last_name=data["name"],
            password=password,
        )
        data["central_user_id"] = central_result["user_id"]
        data["central_user_uuid"] = central_result["user_uuid"]

        # Le central peut créer le compte inactif selon le groupe (le champ
        # user_is_activated de la réponse n'est pas garanti "true" pour tous les
        # groupes/instances — cf. §12 du README). Sans cette activation, le compte
        # local est marqué actif alors que le central refuse la connexion avec un
        # simple "identifiants invalides", indiscernable d'un mauvais mot de passe.
        if central_result.get("user_is_activated") is not True:
            machine_token = await central_auth.get_machine_token()
            await central_auth.activate_central_account(central_result["user_uuid"], machine_token)

        obj = await self.repo.create(data)
        self._logger.info(f"✅ Compte créé — id={obj.id} central_user_id={obj.central_user_id}")
        self._notify_account_created(obj)

        if actor_bearer_token:
            await central_auth.log_central_event(
                actor_bearer_token, object_id=str(obj.id), action="create", status="success",
                message=f"Compte créé : {obj.email}", after=data,
            )
        return obj

    async def provision_from_central(
        self, *, central_user_id: int, central_user_uuid: str | None, email: str,
        name: str, firstname: str | None, phone: str | None, role: str,
        consent_accepted_at: datetime | None = None, consent_version: str | None = None,
    ):
        """
        Matérialise le miroir local d'une identité centrale QUI EXISTE DÉJÀ côté
        manager-user (pas de création centrale ici, contrairement à create()) —
        cas d'un login réussi côté central sans compte local correspondant :
        auto-provisioning silencieux si déjà membre d'un groupe support central,
        ou rattachement après consentement explicite sinon (voir RouteAuth.py
        POST /auth/login et POST /auth/consent/accept).
        """
        role = normalize_role(role)
        email = (email or "").strip().lower()

        existing_email = await self.repo.find_by_email(email)
        if existing_email is not None:
            raise self.conflict(
                "Un compte local existe déjà pour cette adresse email.",
                error_code=ErrorCode.EMAIL_ALREADY_EXISTS,
                field="email", value=email,
            )

        data: dict = {
            "central_user_id": central_user_id,
            "central_user_uuid": central_user_uuid,
            "email": email,
            "name": name,
            "firstname": firstname,
            "role": role,
            "account_status": "active",
            "status": True,
            "activated_at": datetime.utcnow(),
        }
        if phone:
            phone = normalize_phone(phone)
            # Champ secondaire : un conflit ne doit pas bloquer un rattachement dont
            # l'ancrage fiable (email, garanti unique côté central) est déjà validé.
            if await self.repo.find_by_phone(phone) is None:
                data["phone"] = phone
        if consent_accepted_at is not None:
            data["consent_accepted_at"] = consent_accepted_at
        if consent_version is not None:
            data["consent_version"] = consent_version

        obj = await self.repo.create(data)
        self._logger.info(
            f"✅ Compte auto-provisionné depuis le central — id={obj.id} "
            f"central_user_id={central_user_id} role={role}"
        )
        self._notify_account_associated(obj)
        return obj

    async def update(
        self, id: int, data: dict, *, validate_org_assignment: bool = False, actor_bearer_token: str | None = None,
    ):
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


        # Auto is_edg_employee
        data = self._auto_edg_employee(data)
        try:
            data = self._fold_intervenant_status(data, current)
        except ValueError as exc:
            raise self.bad_request(
                str(exc), error_code=ErrorCode.INVALID_FIELD_VALUE, field="intervenant_status",
            )

        if validate_org_assignment and ("role" in data or "unity_id" in data):
            await self._validate_role_org_assignment(
                role=data.get("role", current.role),
                unity_id=data.get("unity_id", current.unity_id),
            )

        # ── Synchronisation centrale (README §12) ────────────────────────────
        identity_keys = {"email", "phone", "name", "firstname"}
        touches_identity = bool(identity_keys & data.keys())
        touches_role = "role" in data and data["role"] != current.role

        if touches_identity or touches_role:
            if not current.central_user_uuid:
                raise self.conflict(
                    _CENTRAL_NOT_LINKED_MESSAGE,
                    error_code="ACCOUNT_NOT_CENTRAL_LINKED",
                    hint="Ce compte doit être recréé via la plateforme centrale.",
                )
            machine_token = await central_auth.get_machine_token()

            if touches_identity:
                await central_auth.update_central_account(
                    current.central_user_uuid,
                    email=data.get("email", current.email),
                    phone=data.get("phone", current.phone) or "",
                    firstname=data.get("firstname", current.firstname) or data.get("name", current.name),
                    last_name=data.get("name", current.name),
                    machine_token=machine_token,
                )

            if touches_role:
                old_group = central_auth.group_for_role(current.role)
                new_group = central_auth.group_for_role(data["role"])
                if new_group != old_group:
                    await central_auth.add_group_membership(current.central_user_uuid, new_group, machine_token)
                    await central_auth.remove_group_membership(current.central_user_uuid, old_group, machine_token)

        obj = await self.repo.update(id, data)

        if actor_bearer_token:
            await central_auth.log_central_event(
                actor_bearer_token, object_id=str(id), action="update", status="success",
                message=f"Compte mis à jour : {obj.email}", after=data,
            )
        return obj

    async def delete(self, id: int, actor_bearer_token: str) -> bool:
        current = await self.get_by_id(id)
        if not current.central_user_id:
            raise self.conflict(
                _CENTRAL_NOT_LINKED_MESSAGE,
                error_code="ACCOUNT_NOT_CENTRAL_LINKED",
                hint="Ce compte doit être recréé via la plateforme centrale.",
            )
        await central_auth.delete_central_account(current.central_user_id, actor_bearer_token)
        await central_auth.log_central_event(
            actor_bearer_token, object_id=str(id), action="delete", status="success",
            message=f"Compte supprimé : {current.email}",
        )
        result = await self.repo.delete(id)
        await emit_event(AppEvent(
            type="account.deactivated",
            payload={"id": id},
            target={"user_ids": [id]},
        ))
        return result

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

    async def set_active(self, id: int, active: bool, *, actor_bearer_token: str | None = None):
        current = await self.get_by_id(id)
        if not current.central_user_uuid:
            raise self.conflict(
                _CENTRAL_NOT_LINKED_MESSAGE,
                error_code="ACCOUNT_NOT_CENTRAL_LINKED",
                hint="Ce compte doit être recréé via la plateforme centrale.",
            )
        machine_token = await central_auth.get_machine_token()
        if active:
            await central_auth.activate_central_account(current.central_user_uuid, machine_token)
        else:
            await central_auth.deactivate_central_account(current.central_user_uuid, machine_token)

        obj = await self.repo.update(id, {
            "status": active,
            "account_status": "active" if active else "inactive",
        })
        if actor_bearer_token:
            await central_auth.log_central_event(
                actor_bearer_token, object_id=str(id),
                action="activate" if active else "deactivate", status="success",
                message=f"Compte {'activé' if active else 'désactivé'} : {obj.email}",
            )
        if not active:
            # Déconnexion immédiate — sans ça, la personne ne serait rejetée qu'à
            # son prochain appel API (dependencies.py revérifie account_status à
            # chaque requête), mais resterait "connectée" en apparence si elle
            # n'interagit plus (page ouverte, flux SSE déjà établi). Un seul
            # événement ciblé suffit à couvrir tous ses onglets/appareils ouverts
            # (event_bus fan-out vers chaque connexion SSE abonnée à cet user_id).
            await emit_event(AppEvent(
                type="account.deactivated",
                payload={"id": id},
                target={"user_ids": [id]},
            ))
        return obj

    async def reset_password(self, id: int, *, actor_bearer_token: str | None = None) -> str:
        current = await self.get_by_id(id)
        if not current.central_user_uuid:
            raise self.conflict(
                _CENTRAL_NOT_LINKED_MESSAGE,
                error_code="ACCOUNT_NOT_CENTRAL_LINKED",
                hint="Ce compte doit être recréé via la plateforme centrale.",
            )
        machine_token = await central_auth.get_machine_token()
        default_password = await central_auth.reset_central_password(current.central_user_uuid, machine_token)
        if actor_bearer_token:
            await central_auth.log_central_event(
                actor_bearer_token, object_id=str(id), action="reset_password", status="success",
                message=f"Mot de passe réinitialisé : {current.email}",
            )
        return default_password

    async def search(
        self, q: str, *,
        direction_id: int | None = None,
        unit_id: int | None = None,
        page: int = 1, limit: int = 20,
    ):
        items, total = await self.repo.search(
            q, direction_id=direction_id, unit_id=unit_id, page=page, limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def set_role(self, id: int, role: str, *, actor_bearer_token: str | None = None):
        return await self.update(
            id, {"role": normalize_role(role)},
            validate_org_assignment=True, actor_bearer_token=actor_bearer_token,
        )
