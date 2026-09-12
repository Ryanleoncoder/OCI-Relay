"""Handler /services."""

import asyncio

from ....config.settings import settings
from ....system.services import SystemdIndisponivel, get_services_status
from .. import formatter as fmt

# Uma VPS tem dezenas de serviços ativos; listar todos vira parede de texto.
_LIMITE_LISTAGEM = 30


async def handle(client, token: str, chat_id: int):
    """Envia serviços críticos, unidades em falha e serviços em execução."""
    from ..adapter import tg_send_text

    try:
        dados = await asyncio.to_thread(
            get_services_status, settings.critical_services)

        emojis = []
        criticos = []
        for unidade, estado in dados["criticos"].items():
            emoji = fmt.OK if estado == "active" else fmt.CRITICO
            emojis.append(emoji)
            criticos.append((unidade, f"{emoji} {estado}"))

        falhas = dados["failed"]
        e_falhas = fmt.CRITICO if falhas else fmt.OK
        emojis.append(e_falhas)

        rodando = dados["running"]

        partes = [
            fmt.titulo_local("⚙️", "Services"),
            "",
            fmt.secao("Críticos"),
            fmt.tabela(criticos),
            fmt.tabela([
                ("Em execução", str(len(rodando))),
                ("Em falha", f"{e_falhas} {len(falhas)}"),
            ]),
        ]

        if falhas:
            partes.append(fmt.secao("Falhas"))
            partes.append(fmt.bloco(falhas[:10]))

        if rodando:
            partes.append(fmt.secao("Em execução"))
            partes.append(fmt.bloco(rodando[:_LIMITE_LISTAGEM]))
            if len(rodando) > _LIMITE_LISTAGEM:
                partes.append(
                    f"__... e mais {len(rodando) - _LIMITE_LISTAGEM} "
                    "serviços.__")

        partes.append(f"Overall: {fmt.veredito(*emojis)}")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except SystemdIndisponivel as e:
        await tg_send_text(client, token, chat_id,
            f"⚙️ **Services**\n\n{fmt.NEUTRO} {e}.")
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter serviços: {e}")
