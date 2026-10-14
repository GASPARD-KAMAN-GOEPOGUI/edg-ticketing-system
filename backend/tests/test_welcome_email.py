"""E-mail envoyé à la création d'un compte : ton « Bienvenue » (2026-10-14)."""
from __future__ import annotations

import email
from email.header import decode_header, make_header

from api.core import mailer


async def test_account_created_email_says_welcome(monkeypatch):
    sent = []
    monkeypatch.setattr(mailer, "_is_configured", lambda: True)

    async def capture(msg):
        sent.append(msg)

    monkeypatch.setattr(mailer, "_smtp_send", capture)
    monkeypatch.setattr(mailer._env, "CORS_ORIGINS", ["https://support.edgportal.com"])

    assert await mailer.send_account_created_email("aissatou.bah@edg.gn", "Aissatou Bah") is True
    msg = email.message_from_bytes(sent[0].as_bytes())
    assert str(make_header(decode_header(msg["Subject"]))) == "Bienvenue sur EDG Support"
    html = next(
        part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        for part in msg.walk() if part.get_content_type() == "text/html"
    )
    assert "Bienvenue sur EDG Support !" in html
    assert "Bonjour Aissatou Bah, bienvenue sur EDG Support" in html
    assert 'href="https://support.edgportal.com/login"' in html
