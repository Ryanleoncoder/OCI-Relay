"""Handler /language."""

import asyncio

from ....i18n import (
    definir_idioma,
    idioma_atual,
    idiomas_disponiveis,
    resolver,
    t,
)
from ....state import set_preferencia
from .. import formatter as fmt


def _nome(codigo: str) -> str:
    """Nome do idioma no próprio idioma, quando o catálogo o declara."""
    from ....i18n import carregar
    return carregar(codigo).get("language.name", codigo)


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Mostra ou troca o idioma desta conversa."""
    from ..adapter import tg_send_text

    disponiveis = idiomas_disponiveis()
    escolhido = args.strip()

    if not escolhido:
        await tg_send_text(client, token, chat_id, "\n".join([
            fmt.cabecalho(t("language.title")),
            "",
            t("language.current", language=_nome(idioma_atual())),
            "",
            fmt.secao(t("language.available")),
            fmt.bloco([f"{c:<8} {_nome(c)}" for c in disponiveis]),
            t("language.how_to", example=disponiveis[0]),
        ]))
        return

    # A mesma resolução usada para o idioma do cliente: `pt-br`, `PT_BR` e
    # `pt` chegam todos em pt_BR. Exigir o nome exato do arquivo faria o
    # comando ser mais rígido que a detecção automática.
    idioma = resolver(escolhido)

    if idioma is None:
        await tg_send_text(client, token, chat_id,
            t("language.unknown", language=escolhido,
              available=", ".join(disponiveis)))
        return

    await asyncio.to_thread(set_preferencia, chat_id, "idioma", idioma)
    definir_idioma(idioma)

    # A confirmação já sai no idioma novo — é a prova de que a troca pegou.
    await tg_send_text(client, token, chat_id,
                       t("language.changed", language=_nome(idioma)))
