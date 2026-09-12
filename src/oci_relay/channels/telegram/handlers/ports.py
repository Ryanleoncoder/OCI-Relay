"""Handler /ports."""

import asyncio

from ....security import get_listening_ports_summary, identificacao_limitada
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia portas em escuta, destacando as públicas."""
    from ..adapter import tg_send_text

    try:
        portas = await asyncio.to_thread(get_listening_ports_summary)

        if not portas:
            await tg_send_text(client, token, chat_id,
                "🌐 **Listening Ports**\n\nNenhuma porta em escuta.")
            return

        publicas = [p for p in portas if p["public"]]
        locais = [p for p in portas if not p["public"]]

        partes = [fmt.titulo_local("🌐", "Listening Ports"), ""]

        if publicas:
            partes.append(fmt.secao(f"Públicas {fmt.AVISO} ({len(publicas)})"))
            partes.append(fmt.tabela([
                (f"{p['port']}/{p['proto']}", p["process"]) for p in publicas
            ]))

        if locais:
            partes.append(fmt.secao(f"Localhost ({len(locais)})"))
            partes.append(fmt.tabela([
                (f"{p['port']}/{p['proto']}", p["process"]) for p in locais
            ]))

        partes.append(f"Total: {len(portas)} portas")

        if identificacao_limitada(portas):
            partes.append(
                "__Processos marcados com '?' pertencem a outros usuários: "
                "identificá-los exige privilégio de root.__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter portas: {e}")
