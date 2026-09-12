"""Handler /uptime."""

import asyncio

from ....i18n import t
from ....system import get_boot_time, get_uptime
from .. import formatter as fmt


def _coletar() -> tuple[int, str]:
    return get_uptime(), get_boot_time().strftime("%Y-%m-%d %H:%M")


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
                (t("uptime.booted"), boot),
            ]),
        ]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="uptime", reason=e))
