"""
Boutons des e-mails de notification (« Voir le ticket », « Ouvrir la file
d'attente »…) : les notifications portent des chemins relatifs, morts dans un
client de messagerie. Le lien de l'e-mail doit être l'adresse complète du
frontend (première origine de CORS_ORIGINS).
"""
from __future__ import annotations

import pytest

from api.core import mailer

FRONT = "https://support.edgportal.com"


@pytest.fixture
def front(monkeypatch):
    monkeypatch.setattr(mailer._env, "CORS_ORIGINS", [FRONT + "/", "http://localhost:3000"])


def _html(action_url: str | None) -> str:
    return mailer.render_notification_html(
        title="Nouveau ticket à qualifier", body="Un ticket attend.",
        action_url=action_url, action_label="Voir le ticket",
    )


@pytest.mark.parametrize("path", ["/app/queue", "/app/requests/42", "/app/queue?tab=qualify"])
def test_relative_action_link_becomes_absolute(front, path):
    html = _html(path)
    assert f'href="{FRONT}{path}"' in html
    assert 'href="/app' not in html


def test_absolute_link_is_kept(front):
    assert 'href="https://ailleurs.example/x"' in _html("https://ailleurs.example/x")


def test_no_button_without_frontend_address_or_with_unsafe_path(monkeypatch):
    monkeypatch.setattr(mailer._env, "CORS_ORIGINS", [FRONT])
    assert "Voir le ticket" in _html("/app/queue")  # témoin : le bouton existe
    monkeypatch.setattr(mailer._env, "CORS_ORIGINS", [])
    assert "Voir le ticket" not in _html("/app/queue")
    monkeypatch.setattr(mailer._env, "CORS_ORIGINS", [FRONT])
    assert mailer._absolute_app_url("//evil.example/x") is None
    assert mailer._absolute_app_url("app/queue") is None
