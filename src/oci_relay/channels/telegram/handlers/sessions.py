"""Handler /sessions."""

import asyncio
import datetime as dt

import psutil

from ....i18n import t
from .. import formatter as fmt


def _coletar() -> list[dict]:
    """Usuários conectados, conforme o registro de sessões do sistema."""
    sessoes = []
    for u in psutil.users():
        sessoes.append({
            "nome": u.name,
            "origem": u.host or "local",
            "desde": dt.datetime.fromtimestamp(u.started).strftime("%d/%m %H:%M"),
            "terminal": u.terminal or "-",
        })
    return sessoes


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia as sessões de usuário abertas no host."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho_local(t("sessions.title"))

    try:
        sessoes = await asyncio.to_thread(_coletar)

        if not sessoes:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.OK} {t('sessions.none')}")
            return

        partes = [cabecalho, ""]
        for s in sessoes:
            partes.append(fmt.tabela([
                (t("sessions.user"), s["nome"]),
                (t("sessions.from_host"), s["origem"]),
                (t("sessions.since"), s["desde"]),
                (t("sessions.terminal"), s["terminal"]),
            ]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="sessions", reason=e))
