"""Handler /disk."""

import asyncio

from ....config.settings import settings
from ....i18n import t
from ....system import get_disks
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia uso de disco por ponto de montagem."""
    from ..adapter import tg_send_text

    try:
        discos = await asyncio.to_thread(get_disks)

        if not discos:
            await tg_send_text(client, token, chat_id, t("disk.none"))
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

        await tg_send_text(client, token, chat_id, "\n".join([
            fmt.cabecalho_local(t("disk.title")),
            "",
            fmt.bloco(linhas),
            f"{t('common.overall')}: {fmt.veredito(*emojis)}",
        ]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="disk", reason=e))
