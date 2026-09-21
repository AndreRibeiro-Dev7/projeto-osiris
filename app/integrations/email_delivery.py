"""Transactional email delivery through the Resend HTTP API."""

import httpx


async def send_email_change_code(
    *, api_key: str, from_email: str, to_email: str, code: str
) -> None:
    """Send the verification code to the requested login address."""
    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "from": from_email,
                "to": [to_email],
                "subject": "Confirme seu novo e-mail no Osiris",
                "html": (
                    "<h2>Confirmação de e-mail</h2>"
                    "<p>Use o código abaixo para confirmar seu novo e-mail no Osiris:</p>"
                    f"<p style='font-size:32px;font-weight:bold;letter-spacing:8px'>{code}</p>"
                    "<p>O código expira em 10 minutos. Se você não solicitou a troca, ignore esta mensagem.</p>"
                ),
            },
        )
        response.raise_for_status()
