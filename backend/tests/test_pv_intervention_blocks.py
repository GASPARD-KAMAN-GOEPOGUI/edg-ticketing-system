"""
PV d'intervention EDG/PS-GSI/PV-01 — blocs revus le 2026-10-13 :
  - « Requérant » en tête (nom, badge, fonction, direction, département,
    service), pointillés pour toute information manquante ;
  - « Réception » sans Mail / Téléphone, « Responsable » devenu « Chef de
    service » ;
  - « Affectation » avec le chef de division destinataire de l'orientation,
    figé à l'orientation, en pointillés si le ticket est allé directement au
    technicien ;
  - le formulaire tient toujours sur une page.
"""
from __future__ import annotations

import re
import zlib
from datetime import datetime
from types import SimpleNamespace

from sqlalchemy import select

from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelUnity import Unity
from api.services.ServicePvIntervention import PvInterventionService
from api.services.ServiceRequest import RequestService
from tests.support import TestSession

CHIEF = {
    "distributor_name": "Fatoumata Camara",
    "distributor_badge": "EDG-0815",
    "distributor_service_label": "Division Support Utilisateurs",
}


def _pdf_lines(pdf: bytes) -> list[str]:
    """Textes imprimés : chaînes des opérateurs Tj des flux (zlib) du PDF."""
    lines: list[str] = []
    for raw in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", pdf, re.S):
        try:
            content = zlib.decompress(raw)
        except zlib.error:
            content = raw
        for text in re.findall(rb"\((.*?)(?<!\\)\)\s*Tj", content, re.S):
            lines.append(text.decode("latin-1").replace("\\(", "(").replace("\\)", ")"))
    return lines


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page\b", pdf))


def _fake_request(*, distributor_id=None, full_requester=True) -> SimpleNamespace:
    infos = {
        "receiver_name": "Mamadou Diallo",
        "receiver_badge": "EDG-1042",
        "handler_department_label": "Departement Support",
        "handler_service_label": "Service Support",
    }
    requester = dict(
        employee_matricule="EDG-2201", requester_job="Comptable",
        requester_direction_label="Direction Financiere",
        requester_department_label="Departement Comptabilite",
        requester_service_label="Service Paie",
    ) if full_requester else dict(
        employee_matricule=None, requester_job=None, requester_direction_label=None,
        requester_department_label=None, requester_service_label=None,
    )
    intervention = {
        "intervention_id": "req1-c1-i1", "actor_name": "Ibrahima Sow", "actor_matricule": "EDG-3307",
        "actor_status": "titulaire",
        "started_at": datetime(2026, 10, 12, 9, 0), "ended_at": datetime(2026, 10, 12, 11, 30),
        "work_done": "Remplacement du cable reseau", "solution": "Cable change",
    }
    return SimpleNamespace(
        ref="EDG-26-00042", infos=infos, interventions=[intervention], timelines=[],
        requester_name="Aissatou Bah", location_label=None, sla_hours=24,
        resolved_at=datetime(2026, 10, 12, 11, 30), appreciation=None,
        distributor_id=distributor_id, **requester,
    )


def _render(req, chief: dict, direction_code: str | None = "DF") -> bytes:
    svc = PvInterventionService.__new__(PvInterventionService)
    return svc._render(svc._collect(req, chief, requester_direction_code=direction_code))


def test_requester_reception_and_division_chief_blocks():
    pdf = _render(_fake_request(distributor_id=7), CHIEF)
    text = "\n".join(_pdf_lines(pdf))

    for expected in (
        "Requerant",
        "Nom : Aissatou Bah", "Badge : EDG-2201", "Fonction : Comptable",
        "Direction : DF", "Departement : Departement Comptabilite",
        "Service : Service Paie",
        "Chef de service : Mamadou Diallo", "Badge : EDG-1042",
        "Chef de division", "Service : Division Support Utilisateurs",
        "Nom : Fatoumata Camara", "Badge : EDG-0815",
        "Technicien", "Nom : Ibrahima Sow", "Badge : EDG-3307",
    ):
        assert expected in text, expected
    for removed in ("Mail [", "Telephone [", "Responsable :", "Direction Financiere"):
        assert removed not in text, removed
    assert _page_count(pdf) == 1


def test_direct_to_technician_and_incomplete_requester_print_dots():
    req = _fake_request(distributor_id=None, full_requester=False)
    req.interventions[0]["actor_matricule"] = None  # stagiaire sans badge
    pdf = _render(req, {}, direction_code=None)
    lines = _pdf_lines(pdf)

    # Badge du technicien en pointillés : son nom a sa propre ligne.
    technician = lines[lines.index("Technicien") + 1:]
    assert technician[0] == "Nom : Ibrahima Sow"
    badge = next(line for line in technician if line.startswith("Badge : "))
    assert set(badge.split(" : ")[1]) == {"."}, badge
    direction = next(line for line in lines if line.startswith("Direction : "))
    assert set(direction.split("     ")[0].split(" : ")[1]) == {"."}, direction

    assert "Chef de division" in lines
    chief_block = lines[lines.index("Chef de division") + 1: lines.index("Chef de division") + 4]
    assert [line.split(" : ")[0] for line in chief_block] == ["Service", "Nom", "Badge"]
    assert all(set(line.split(" : ")[1]) == {"."} for line in chief_block), chief_block

    requester_line = next(line for line in lines if line.startswith("Nom : Aissatou Bah"))
    assert "Badge : ...." in requester_line and "Fonction : ...." in requester_line
    assert _page_count(pdf) == 1


def test_long_treatment_moves_the_whole_signature_table_to_next_page():
    req = _fake_request(distributor_id=7)
    req.interventions[0]["work_done"] = "Remplacement du cable reseau. " * 60
    pdf = _render(req, CHIEF)
    assert _page_count(pdf) == 2  # avant : tableau éparpillé sur plusieurs pages


async def _make_chief(session, *, name="Camara", firstname="Fatoumata") -> Account:
    unity = Unity(label="Division Support Utilisateurs", codename="DSU")
    session.add(unity)
    await session.flush()
    chief = Account(
        name=name, firstname=firstname, email=f"{firstname.lower()}@edg.gn",
        role="chef-division-support", matricule="EDG-0815", unity_id=unity.id,
        account_status="active", status=True,
    )
    session.add(chief)
    await session.flush()
    return chief


async def test_requester_direction_codename_from_frozen_direction_id():
    async with TestSession() as session:
        direction = Unity(label="Direction Financiere", codename="DF")
        session.add(direction)
        await session.flush()
        svc = PvInterventionService(session)
        assert await svc._requester_direction_code(SimpleNamespace(requester_direction_id=direction.id)) == "DF"
        assert await svc._requester_direction_code(SimpleNamespace(requester_direction_id=None)) is None


def test_logo_fits_inside_its_frame():
    from fpdf import FPDF

    from api.services.ServiceExport import get_logo_path, pdf_safe_text

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    placed: dict = {}
    real_image = pdf.image
    pdf.image = lambda path, **kw: placed.update(kw) or real_image(path, **kw)
    top = pdf.get_y()
    PvInterventionService._header(pdf, pdf_safe_text, get_logo_path(), pdf.w - pdf.l_margin - pdf.r_margin)

    left, width, frame_w, frame_h = pdf.l_margin, placed["w"], 40.0, 20.0
    x, y, height = placed["x"], placed["y"], placed["h"]
    assert left <= x and x + width <= left + frame_w           # dans le cadre
    assert top <= y and y + height <= top + frame_h            # ne touche plus la ligne du bas
    assert abs((x - left) - (left + frame_w - x - width)) < 0.01  # centré horizontalement
    assert abs((y - top) - (top + frame_h - y - height)) < 0.01   # centré verticalement
    assert abs(height / width - 780 / 720) < 0.01              # proportions conservées


async def test_division_chief_frozen_identity_else_live_account():
    async with TestSession() as session:
        chief = await _make_chief(session)
        svc = PvInterventionService(session)

        assert await svc._division_chief(SimpleNamespace(distributor_id=None, infos={})) == {}

        live = await svc._division_chief(SimpleNamespace(distributor_id=chief.id, infos={}))
        assert live["distributor_name"] == "Fatoumata Camara"
        assert live["distributor_badge"] == "EDG-0815"
        assert live["distributor_service_label"] == "Division Support Utilisateurs"

        frozen = {"distributor_snapshot_id": str(chief.id), "distributor_name": "Nom fige"}
        got = await svc._division_chief(SimpleNamespace(distributor_id=chief.id, infos=frozen))
        assert got["distributor_name"] == "Nom fige"

        stale = {"distributor_snapshot_id": "999", "distributor_name": "Autre chef"}
        got = await svc._division_chief(SimpleNamespace(distributor_id=chief.id, infos=stale))
        assert got["distributor_name"] == "Fatoumata Camara"


async def test_orientation_to_division_chief_freezes_its_identity():
    async with TestSession() as session:
        chief = await _make_chief(session)
        csshf = Account(
            name="Diallo", firstname="Mamadou", email="csshf@edg.gn", role="chief-service",
            matricule="EDG-1042", account_status="active", status=True,
        )
        requester = Account(
            name="Bah", firstname="Aissatou", email="user@edg.gn", role="user",
            account_status="active", status=True,
        )
        session.add_all([csshf, requester])
        statuses = {}
        for i, code in enumerate(("new", "qualifying", "assigned")):
            statuses[code] = RequestStatus(code=code, label=code, sort_order=i)
            session.add(statuses[code])
        prio = PriorityDefinition(slug="medium", label="Moyenne", sort_order=1, color="blue")
        cat = RequestCategory(code="incident", label="Incident", sort_order=1)
        session.add_all([prio, cat])
        await session.flush()
        req = Request(
            ref="EDG-26-00001", title="T", description="d", is_external=False, in_triage=True,
            request_status_id=statuses["new"].id, priority_definition_id=prio.id,
            request_category_id=cat.id, requester_id=requester.id,
        )
        session.add(req)
        await session.commit()
        chief_id, csshf_id, req_id = chief.id, csshf.id, req.id

    async with TestSession() as session:
        actor = (await session.execute(select(Account).where(Account.id == csshf_id))).scalar_one()
        await RequestService(session).qualify_triage(
            str(req_id), {"assignee_id": chief_id},
            actor_id=str(csshf_id), actor_name="Mamadou Diallo", actor_role="chief-service", actor=actor,
        )
        await session.commit()

    async with TestSession() as session:
        saved = (await session.execute(select(Request).where(Request.id == req_id))).scalar_one()
        assert saved.distributor_id == chief_id
        assert saved.infos["distributor_snapshot_id"] == str(chief_id)
        assert saved.infos["distributor_name"] == "Fatoumata Camara"
        assert saved.infos["distributor_badge"] == "EDG-0815"
        assert saved.infos["distributor_service_label"] == "Division Support Utilisateurs"
        assert saved.infos["receiver_name"] == "Mamadou Diallo"
