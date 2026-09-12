"""Handler /disk."""

import asyncio

from ....config.settings import settings
from ....system import get_disks
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int):
    """Envia uso de disco por ponto de montagem."""
    from ..adapter import tg_send_text

    try:
        discos = await asyncio.to_thread(get_disks)

        if not discos:
            await tg_send_text(client, token, chat_id,
                "Nenhum ponto de montagem legível encontrado.")
            return

        emojis = [
            fmt.emoji_percentual(
                d["percent"], settings.alert_disk_warning_percent,
                settings.alert_disk_critical_percent)
            for d in discos
        ]

        linhas = [
            f"{e} {d['mount']:<14} "
            f"{fmt.gb(d['used_gb'])} / {fmt.gb(d['total_gb'])} GB  "
            f"{d['percent']:>5.1f}%"
            for d, e in zip(discos, emojis)
        ]

        partes = [
            fmt.titulo_local("💾", "Disk"),
            "",
            fmt.bloco(linhas),
            f"Overall: {fmt.veredito(*emojis)}",
        ]

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter disco: {e}")
