"""Handler /uptime."""

import asyncio
import datetime as dt

import psutil

from ....i18n import t
from ....system import get_uptime
from .. import formatter as fmt


def _coletar() -> tuple[int, dt.datetime]:
    return get_uptime(), dt.datetime.fromtimestamp(psutil.boot_time())


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia há quanto tempo o host está no ar."""
    from ..adapter import tg_send_text

    try:
        segundos, boot = await asyncio.to_thread(_coletar)

        await tg_send_text(client, token, chat_id, "\n".join([
            fmt.cabecalho_local(t("uptime.title")),
            "",
            fmt.tabela([
                (t("uptime.up_for"), fmt.uptime(segundos)),
                (t("uptime.booted"), boot.strftime("%Y-%m-%d %H:%M")),
            ]),
        ]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="uptime", reason=e))
