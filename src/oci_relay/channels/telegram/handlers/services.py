"""Handler /services."""

import asyncio

from ....config.settings import settings
from ....i18n import t
from ....system.services import SystemdIndisponivel, get_services_status
from .. import formatter as fmt

# Uma VPS tem dezenas de serviços ativos; listar todos vira parede de texto.
_LIMITE_LISTAGEM = 30


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia serviços críticos, unidades em falha e serviços em execução."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho_local(t("services.title"))

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
            cabecalho,
            "",
            fmt.secao(t("services.critical")),
            fmt.tabela(criticos),
            fmt.tabela([
                (t("services.running_count"), str(len(rodando))),
                (t("services.failed_count"), f"{e_falhas} {len(falhas)}"),
            ]),
        ]

        if falhas:
            partes.append(fmt.secao(t("services.failures")))
            partes.append(fmt.bloco(falhas[:10]))

        if rodando:
            partes.append(fmt.secao(t("services.running")))
            partes.append(fmt.bloco(rodando[:_LIMITE_LISTAGEM]))
            if len(rodando) > _LIMITE_LISTAGEM:
                partes.append("__" + t("services.and_more",
                                       count=len(rodando) - _LIMITE_LISTAGEM)
                              + "__")

        partes.append(f"{t('common.overall')}: {fmt.veredito(*emojis)}")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except SystemdIndisponivel:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.NEUTRO} {t('services.no_systemd')}")
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="services", reason=e))
