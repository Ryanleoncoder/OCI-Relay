"""Handler /fail2ban."""

import asyncio

from ....security import get_fail2ban_status
from .. import formatter as fmt

_EMOJI_STATUS = {
    "active": fmt.OK,
    "inactive": fmt.CRITICO,
    "not_installed": fmt.NEUTRO,
    "error": fmt.CRITICO,
}

_TEXTO_STATUS = {
    "active": "active",
    "inactive": "inactive",
    "not_installed": "não instalado neste host",
    "error": "erro ao consultar",
}


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia status do Fail2Ban."""
    from ..adapter import tg_send_text

    try:
        f2b = await asyncio.to_thread(get_fail2ban_status)
        status = f2b.get("status", "error")
        emoji = _EMOJI_STATUS.get(status, fmt.NEUTRO)

        partes = [
            fmt.titulo("🛡️", "Fail2Ban"),
            "",
            f"Service: {emoji} {_TEXTO_STATUS.get(status, status)}",
        ]

        saida = (f2b.get("output") or "").strip()
        if saida:
            partes.append(fmt.secao("Jails"))
            partes.append(fmt.bloco(saida.split("\n")[:12]))

        erro = (f2b.get("error") or "").strip()
        if erro:
            partes.append(fmt.bloco(erro.split("\n")[:6]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter Fail2Ban: {e}")
