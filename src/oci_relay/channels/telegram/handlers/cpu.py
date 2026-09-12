"""Handler /cpu."""

import asyncio

from ....config.settings import settings
from ....system import get_cpu_usage, get_top_processes
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia detalhamento de CPU."""
    from ..adapter import tg_send_text

    try:
        cpu = await asyncio.to_thread(get_cpu_usage)
        top = await asyncio.to_thread(get_top_processes, 5)

        emoji = fmt.emoji_percentual(
            cpu["percent"], settings.alert_cpu_warning_percent,
            settings.alert_cpu_critical_percent)

        partes = [
            fmt.titulo_local("🔥", "CPU"),
            "",
            fmt.tabela([
                ("Usage", f"{cpu['percent']}%  {emoji}"),
                ("Cores", str(cpu["cores"])),
                ("Load", fmt.carga(cpu["load_avg"])),
            ]),
            fmt.secao("Per-core"),
            fmt.tabela([
                (f"core {i}", f"{v}%") for i, v in enumerate(cpu["per_core"])
            ]),
        ]

        if top:
            partes.append(fmt.secao("Top CPU"))
            partes.append(fmt.tabela(
                [(p["name"][:22], f"{p['cpu_percent']}%") for p in top]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter CPU: {e}")
