"""Handler /failed."""

import asyncio

from ....i18n import t
from ....system.services import SystemdIndisponivel, failed_units
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia as unidades systemd em falha."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho_local(t("failed.title"))

    try:
        falhas = await asyncio.to_thread(failed_units)

        if not falhas:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.OK} {t('failed.none')}")
            return

        await tg_send_text(client, token, chat_id, "\n".join([
            cabecalho,
            "",
            f"{fmt.CRITICO} {t('failed.count', count=len(falhas))}",
            fmt.bloco(falhas[:20]),
        ]))
    except SystemdIndisponivel:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.NEUTRO} {t('services.no_systemd')}")
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="failed units", reason=e))
