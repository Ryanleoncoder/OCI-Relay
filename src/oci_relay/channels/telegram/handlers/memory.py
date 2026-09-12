"""Handler /memory."""

import asyncio

from ....config.settings import settings
from ....system import get_memory, get_top_processes_by_memory
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int):
    """Envia detalhamento de memória."""
    from ..adapter import tg_send_text

    try:
        mem = await asyncio.to_thread(get_memory)
        top = await asyncio.to_thread(get_top_processes_by_memory, 5)

        emoji = fmt.emoji_percentual(
            mem["percent"], settings.alert_memory_warning_percent,
            settings.alert_memory_critical_percent)

        partes = [
            fmt.titulo_local("🧠", "Memory"),
            "",
            fmt.tabela([
                ("Total", f"{fmt.gb(mem['total_gb'])} GB"),
                ("Used", f"{fmt.gb(mem['used_gb'])} GB"),
                ("Available", f"{fmt.gb(mem['available_gb'])} GB"),
                ("Usage", f"{mem['percent']}%  {emoji}"),
            ]),
            fmt.secao("Swap"),
            fmt.tabela([
                ("Used", f"{fmt.gb(mem['swap_used_gb'])} / "
                         f"{fmt.gb(mem['swap_total_gb'])} GB"),
                ("Usage", f"{mem['swap_percent']}%"),
            ]),
        ]

        if top:
            partes.append(fmt.secao("Top RAM"))
            partes.append(fmt.tabela(
                [(p["name"][:22], f"{p['memory_percent']}%") for p in top]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter memória: {e}")
