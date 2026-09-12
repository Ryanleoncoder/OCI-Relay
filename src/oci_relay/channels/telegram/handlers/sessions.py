"""Handler /sessions."""

import asyncio

from ....i18n import t
from ....system import get_sessions
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia as sessões de usuário abertas no host."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho_local(t("sessions.title"))

    try:
        sessoes = await asyncio.to_thread(get_sessions)

        if not sessoes:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.OK} {t('sessions.none')}")
            return

        partes = [cabecalho, ""]
        for s in sessoes:
            partes.append(fmt.tabela([
                (t("sessions.user"), s["nome"]),
                (t("sessions.from_host"), s["origem"]),
                (t("sessions.since"), s["desde"].strftime("%d/%m %H:%M")),
                (t("sessions.terminal"), s["terminal"]),
            ]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="sessions", reason=e))
