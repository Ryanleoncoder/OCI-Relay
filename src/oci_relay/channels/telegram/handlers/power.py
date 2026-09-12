"""Ações de energia da instância: parar, reiniciar e ligar.

Os três comandos compartilham o mesmo fluxo — pré-voo, prévia, confirmação,
execução — e diferem apenas na ação enviada à OCI e no estado que exigem.

Nenhum executa direto. A prévia existe para que a decisão seja tomada com o
estado real da máquina à vista, não de memória.
"""

from dataclasses import dataclass

import oci

from ....config.settings import settings
from ....i18n import t
from ....oci import compute, metadata
from ....safety import confirmation as conf
from .. import formatter as fmt


@dataclass(frozen=True)
class AcaoEnergia:
    comando: str
    acao_oci: str
    chave_titulo: str
    chave_efeito: str
    # Estados em que a ação faz sentido. Pedir para parar uma máquina já
    # parada é engano, não intenção.
    estados_validos: tuple[str, ...]
    estado_resultante: str


ACOES: dict[str, AcaoEnergia] = {
    "/stop": AcaoEnergia(
        comando="/stop",
        acao_oci="SOFTSTOP",
        chave_titulo="power.suspend_title",
        chave_efeito="power.suspend_effect",
        estados_validos=("RUNNING",),
        estado_resultante="STOPPED",
    ),
    "/restart": AcaoEnergia(
        comando="/restart",
        acao_oci="SOFTRESET",
        chave_titulo="power.restart_title",
        chave_efeito="power.restart_effect",
        estados_validos=("RUNNING",),
        estado_resultante="RUNNING",
    ),
    "/poweron": AcaoEnergia(
        comando="/poweron",
        acao_oci="START",
        chave_titulo="power.start_title",
        chave_efeito="power.start_effect",
        estados_validos=("STOPPED",),
        estado_resultante="RUNNING",
    ),
}


async def _avisos(acao: AcaoEnergia) -> list[str]:
    """Riscos que dependem de onde o Relay roda e de como a rede está."""
    if acao.estado_resultante != "STOPPED":
        return []

    avisos = []

    # Parar a máquina que hospeda o bot o mata junto: não sobra ninguém
    # para religá-la pelo Telegram.
    if await metadata.rodando_na_instancia_alvo():
        avisos.append(t("power.self_hosted", emoji=fmt.CRITICO))

    try:
        ips = await compute.get_instance_ips()
        if ips.get("public_ip"):
            avisos.append(t("power.ephemeral_ip", emoji=fmt.AVISO,
                            ip=ips["public_ip"]))
    except Exception:
        # Aviso é complemento; não pode impedir a ação.
        pass

    return avisos


async def pedir_confirmacao(client, token: str, chat_id: int,
                            actor_id: int | None, comando: str):
    """Valida o pré-voo e envia a prévia com os botões de decisão."""
    from ..adapter import tg_send_confirmation, tg_send_text

    acao = ACOES[comando]
    titulo = t(acao.chave_titulo)

    if actor_id is None:
        await tg_send_text(client, token, chat_id,
                           f"{fmt.CRITICO} {t('errors.no_requester')}")
        return

    if not settings.oci_configured:
        await tg_send_text(client, token, chat_id,
            f"**{titulo}**\n\n{fmt.NEUTRO} {t('errors.oci_not_configured')}")
        return

    try:
        status = await compute.get_instance_status()
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"**{titulo}**\n\n{fmt.CRITICO} "
            + t("errors.oci_refused", status=e.status, message=e.message))
        return

    # Pré-voo: o estado atual precisa admitir a ação.
    if status.state not in acao.estados_validos:
        await tg_send_text(client, token, chat_id, "\n".join([
            f"**{titulo}**",
            "",
            t("power.wrong_state", emoji=fmt.NEUTRO, current=status.state,
              expected=" / ".join(acao.estados_validos)),
        ]))
        return

    confirmacao = conf.criar(
        actor_id=actor_id,
        chat_id=chat_id,
        comando=comando,
        alvo=settings.oci_instance_ocid,
    )

    partes = [
        f"**{titulo}**",
        "",
        fmt.tabela([
            (t("power.instance"), status.display_name or "n/d"),
            (t("power.state"),
             f"{fmt.emoji_estado_oci(status.state)} {status.state}"),
            (t("power.action"), acao.acao_oci),
            (t("power.result"), acao.estado_resultante),
        ]),
        t(acao.chave_efeito),
    ]

    avisos = await _avisos(acao)
    if avisos:
        partes.append("")
        partes += avisos

    partes += [
        "",
        f"__{t('power.confirm_within', seconds=confirmacao.segundos_restantes)}__",
    ]

    await tg_send_confirmation(client, token, chat_id, "\n".join(partes),
                               confirmacao.nonce)


async def executar(confirmacao) -> str:
    """Envia a ação à OCI depois da confirmação aprovada."""
    acao = ACOES[confirmacao.comando]

    request_id = await compute.instance_action(acao.acao_oci)

    linhas = [
        f"**{t(acao.chave_titulo)}**",
        "",
        t("power.sent", emoji=fmt.OK, action=acao.acao_oci),
        "",
        t("power.transition", state=acao.estado_resultante),
    ]
    if request_id:
        # Amarra esta execução ao registro correspondente no Audit da OCI.
        linhas += ["", f"__{t('power.request_id', id=request_id)}__"]

    return "\n".join(linhas)
