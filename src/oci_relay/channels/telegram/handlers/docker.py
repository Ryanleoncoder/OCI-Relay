"""Handler /docker."""

import asyncio

from ....docker import get_containers
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
                 actor_id: int | None = None):
    """Envia status dos containers."""
    from ..adapter import tg_send_text

    try:
        containers = await asyncio.to_thread(get_containers)

        if isinstance(containers, dict) and "error" in containers:
            await tg_send_text(client, token, chat_id,
                f"🐳 **Docker**\n\n{fmt.NEUTRO} {containers['error']}")
            return

        if not containers:
            await tg_send_text(client, token, chat_id,
                f"🐳 **Docker**\n\n{fmt.NEUTRO} Nenhum container encontrado.")
            return

        rodando = sum(1 for c in containers if c["status"] == "running")
        parados = sum(1 for c in containers if c["status"] == "exited")
        reiniciando = sum(1 for c in containers if c["status"] == "restarting")

        partes = [
            fmt.titulo("🐳", "Docker"),
            "",
            fmt.tabela([
                ("Running", str(rodando)),
                ("Stopped", str(parados)),
                ("Restarting", str(reiniciando)),
            ]),
            fmt.secao("Containers"),
            fmt.bloco([
                f"{_EMOJI_STATUS.get(c['status'], fmt.NEUTRO)} "
                f"{c['name'][:24]:<24} {c['status']}"
                for c in containers
            ]),
        ]

        if reiniciando:
            partes.append(f"Overall: {fmt.veredito(fmt.AVISO)}")
        elif parados:
            partes.append(f"Overall: {fmt.veredito(fmt.NEUTRO)}")
        else:
            partes.append(f"Overall: {fmt.veredito(fmt.OK)}")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter containers: {e}")
