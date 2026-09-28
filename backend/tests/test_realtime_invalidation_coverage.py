"""Garde-fou temps reel — tout evenement SSE emis doit etre connu du frontend.

Le 2026-09-28, sept ecrans (File d'attente, Tickets transmis, Distribution,
Tickets resolus, Suivi des interventions et deux compteurs) ne se
rafraichissaient jamais en temps reel : leurs cles de cache n'avaient jamais ete
declarees dans `invalidation-map.ts`, et trois evenements emis par le backend
(`request.distributed`, `request.pv_submitted`, `request.pv_archived`) n'y
figuraient pas non plus.

Rien ne signalait l'oubli : l'application fonctionnait, elle affichait
simplement des donnees perimees. Ce test transforme cet echec silencieux en
echec bruyant — ajouter un `emit_event` sans l'inscrire dans la carte casse la
suite immediatement.

Volontairement un simple test de coherence textuelle : pas de dependance a un
runtime JS, et il lit la meme source de verite que l'application.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
_MAP = _BACKEND.parent / "frontend" / "src" / "lib" / "realtime" / "invalidation-map.ts"


def _emitted_events() -> set[str]:
    """Types d'evenements passes a AppEvent(type="...") dans tout le backend."""
    events: set[str] = set()
    for path in (_BACKEND / "api").rglob("*.py"):
        events |= set(
            re.findall(
                r'type\s*=\s*"((?:request|task|escalation|notification)\.[a-z_]+)"',
                path.read_text(encoding="utf-8", errors="ignore"),
            )
        )
    return events


def _mapped_events() -> set[str]:
    src = _MAP.read_text(encoding="utf-8")
    return set(re.findall(r'^\s{2}"([a-z]+\.[a-z_]+)"\s*:', src, re.M))


@pytest.mark.skipif(not _MAP.exists(), reason="frontend absent du checkout")
def test_tout_evenement_emis_est_declare_dans_la_carte_frontend():
    manquants = sorted(_emitted_events() - _mapped_events())
    assert not manquants, (
        "Ces evenements SSE sont emis par le backend mais absents de "
        f"invalidation-map.ts — les ecrans concernes ne se rafraichiront pas : {manquants}"
    )


@pytest.mark.skipif(not _MAP.exists(), reason="frontend absent du checkout")
def test_les_listes_de_tickets_sont_toutes_declarees():
    """Les cles des ecrans de tickets doivent figurer dans la carte.

    Liste tenue a la main : c'est le prix d'un garde-fou sans runtime JS, mais
    elle rend l'oubli visible la ou il se produit — en ajoutant un ecran.
    """
    src = _MAP.read_text(encoding="utf-8")
    attendues = [
        "qualify", "transmitted-by-me", "distribution", "resolved-by-me",
        "pv-tracking", "my-tickets", "requests", "requests-history",
        "my-tickets-transmitted-count", "my-tickets-retransmitted-count",
    ]
    manquantes = [k for k in attendues if f'["{k}"]' not in src]
    assert not manquantes, (
        f"Ecrans de tickets absents de invalidation-map.ts : {manquantes}"
    )
