"""Handler /fail2ban."""

import asyncio

from ....i18n import t
from ....security import get_fail2ban_status
from .. import formatter as fmt

_EMOJI_STATUS = {
    "active": fmt.OK,
    "inactive": fmt.CRITICO,
    "not_installed": fmt.NEUTRO,
    "error": fmt.CRITICO,
}

_CHAVE_STATUS = {
    "active": "fail2ban.active",
    "inactive": "fail2ban.inactive",
    "not_installed": "fail2ban.not_installed",
    "error": "fail2ban.error",
}


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia status do Fail2Ban."""
    from ..adapter import tg_send_text

    try:
        f2b = await asyncio.to_thread(get_fail2ban_status)
        status = f2b.get("status", "error")
        emoji = _EMOJI_STATUS.get(status, fmt.NEUTRO)
        rotulo = t(_CHAVE_STATUS.get(status, "fail2ban.error"))

        partes = [
            fmt.cabecalho(t("fail2ban.title")),
            "",
            f"{t('fail2ban.service')}: {emoji} {rotulo}",
        ]

        saida = (f2b.get("output") or "").strip()
        if saida:
            partes.append(fmt.secao(t("fail2ban.jails")))
            partes.append(fmt.bloco(saida.split("\n")[:12]))

        erro = (f2b.get("error") or "").strip()
        if erro:
            partes.append(fmt.bloco(erro.split("\n")[:6]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="Fail2Ban", reason=e))
