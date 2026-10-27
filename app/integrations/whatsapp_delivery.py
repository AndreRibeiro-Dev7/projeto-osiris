"""Explicitly enabled WhatsApp Cloud API authentication messages."""

import re

import httpx

from app.core.config import Settings


def recovery_is_available(settings: Settings) -> bool:
    """Hide recovery until the operator has configured the approved template."""
    return bool(
        settings.whatsapp_recovery_enabled
        and settings.whatsapp_access_token
        and len(settings.jwt_secret_key) >= 32
        and re.fullmatch(r"[0-9]+", settings.whatsapp_phone_number_id)
        and re.fullmatch(r"v[0-9]+\.[0-9]+", settings.whatsapp_api_version)
        and re.fullmatch(r"[a-z0-9_]+", settings.whatsapp_auth_template)
        and re.fullmatch(r"[a-z]{2}(?:_[A-Z]{2})?", settings.whatsapp_template_language)
    )


async def send_booking_access_code(*, settings: Settings, phone: str, code: str) -> None:
    """Send an approved AUTHENTICATION template with a copy-code button."""
    if not recovery_is_available(settings):
        raise RuntimeError("WhatsApp recovery is not configured.")
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            f"https://graph.facebook.com/{settings.whatsapp_api_version}/"
            f"{settings.whatsapp_phone_number_id}/messages",
            headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
            json={
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone,
                "type": "template",
                "template": {
                    "name": settings.whatsapp_auth_template,
                    "language": {"code": settings.whatsapp_template_language},
                    "components": [
                        {"type": "body", "parameters": [{"type": "text", "text": code}]},
                        {
                            "type": "button",
                            "sub_type": "url",
                            "index": "0",
                            "parameters": [{"type": "text", "text": code}],
                        },
                    ],
                },
            },
        )
        response.raise_for_status()
