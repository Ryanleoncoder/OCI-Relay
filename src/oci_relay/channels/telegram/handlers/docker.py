"""Handler /docker."""

import asyncio

from ....docker import get_containers
from ....i18n import t
from .. import formatter as fmt

_EMOJI_STATUS = {
    "running": fmt.OK,
    "restarting": fmt.AVISO,
    "paused": fmt.AVISO,
    "created": fmt.NEUTRO,
    "exited": fmt.NEUTRO,
    "dead": fmt.CRITICO,
}


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia status dos containers."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("docker.title"))

    try:
        containers = await asyncio.to_thread(get_containers)

        if isinstance(containers, dict) and "error" in containers:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {containers['error']}")
            return

        if not containers:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {t('docker.none')}")
            return

        rodando = sum(1 for c in containers if c["status"] == "running")
        parados = sum(1 for c in containers if c["status"] == "exited")
        reiniciando = sum(1 for c in containers if c["status"] == "restarting")

        if reiniciando:
            veredito = fmt.veredito(fmt.AVISO)
        elif parados:
            veredito = fmt.veredito(fmt.NEUTRO)
        else:
            veredito = fmt.veredito(fmt.OK)

        await tg_send_text(client, token, chat_id, "\n".join([
            cabecalho,
            "",
            fmt.tabela([
                (t("docker.running"), str(rodando)),
                (t("docker.stopped"), str(parados)),
                (t("docker.restarting"), str(reiniciando)),
            ]),
            fmt.secao(t("docker.containers")),
            fmt.bloco([
                f"{_EMOJI_STATUS.get(c['status'], fmt.NEUTRO)} "
                f"{c['name'][:24]:<24} {c['status']}"
                for c in containers
            ]),
            f"{t('common.overall')}: {veredito}",
        ]))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="containers", reason=e))
