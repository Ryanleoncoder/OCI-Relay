"""Handler /memory."""

import asyncio

from ....config.settings import settings
from ....i18n import t
from ....system import get_memory, get_top_processes_by_memory
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia detalhamento de memória."""
    from ..adapter import tg_send_text

    try:
        mem = await asyncio.to_thread(get_memory)
        top = await asyncio.to_thread(get_top_processes_by_memory, 5)

        emoji = fmt.emoji_percentual(
            mem["percent"], settings.alert_memory_warning_percent,
            settings.alert_memory_critical_percent)

        partes = [
            fmt.cabecalho_local(t("memory.title")),
            "",
            fmt.tabela([
                (t("memory.total"), f"{fmt.gb(mem['total_gb'])} GB"),
                (t("memory.used"), f"{fmt.gb(mem['used_gb'])} GB"),
                (t("memory.available"), f"{fmt.gb(mem['available_gb'])} GB"),
                (t("memory.usage"), f"{mem['percent']}%  {emoji}"),
            ]),
            fmt.secao(t("memory.swap")),
            fmt.tabela([
                (t("memory.used"), f"{fmt.gb(mem['swap_used_gb'])} / "
                                   f"{fmt.gb(mem['swap_total_gb'])} GB"),
                (t("memory.usage"), f"{mem['swap_percent']}%"),
            ]),
        ]

        if top:
            partes.append(fmt.secao(t("memory.top")))
            partes.append(fmt.tabela(
                [(p["name"][:22], f"{p['memory_percent']}%") for p in top]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="memory", reason=e))
