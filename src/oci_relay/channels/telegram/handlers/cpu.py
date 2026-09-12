"""Handler /cpu."""

import asyncio

from ....config.settings import settings
from ....i18n import t
from ....system import get_cpu_usage, get_top_processes
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia detalhamento de CPU."""
    from ..adapter import tg_send_text

    try:
        cpu = await asyncio.to_thread(get_cpu_usage)
        top = await asyncio.to_thread(get_top_processes, 5)

        emoji = fmt.emoji_percentual(
            cpu["percent"], settings.alert_cpu_warning_percent,
            settings.alert_cpu_critical_percent)

        partes = [
            fmt.cabecalho_local(t("cpu.title")),
            "",
            fmt.tabela([
                (t("cpu.usage"), f"{cpu['percent']}%  {emoji}"),
                (t("cpu.cores"), str(cpu["cores"])),
                (t("cpu.load"), fmt.carga(cpu["load_avg"])),
            ]),
            fmt.secao(t("cpu.per_core")),
            fmt.tabela([
                (t("cpu.core", index=i), f"{v}%")
                for i, v in enumerate(cpu["per_core"])
            ]),
        ]

        if top:
            partes.append(fmt.secao(t("cpu.top")))
            partes.append(fmt.tabela(
                [(p["name"][:22], f"{p['cpu_percent']}%") for p in top]))

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="CPU", reason=e))
