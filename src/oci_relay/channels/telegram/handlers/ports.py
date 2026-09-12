"""Handler /ports."""

import asyncio

from ....i18n import t
from ....security import get_listening_ports_summary, identificacao_limitada
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia portas em escuta, destacando as públicas."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho_local(t("ports.title"))

    try:
        portas = await asyncio.to_thread(get_listening_ports_summary)

        if not portas:
            await tg_send_text(client, token, chat_id,
                               f"{cabecalho}\n\n{t('ports.none')}")
            return

        publicas = [p for p in portas if p["public"]]
        locais = [p for p in portas if not p["public"]]

        partes = [cabecalho, ""]

        if publicas:
            partes.append(fmt.secao(
                t("ports.public", emoji=fmt.AVISO, count=len(publicas))))
            partes.append(fmt.tabela([
                (f"{p['port']}/{p['proto']}", p["process"]) for p in publicas
            ]))

        if locais:
            partes.append(fmt.secao(t("ports.localhost", count=len(locais))))
            partes.append(fmt.tabela([
                (f"{p['port']}/{p['proto']}", p["process"]) for p in locais
            ]))

        partes.append(t("ports.total", count=len(portas)))

        if identificacao_limitada(portas):
            partes.append(f"__{t('ports.limited')}__")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="ports", reason=e))
