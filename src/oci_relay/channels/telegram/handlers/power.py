"""Ações de energia da instância: parar, reiniciar e ligar.

Os três comandos compartilham o mesmo fluxo — pré-voo, prévia, confirmação,
execução — e diferem apenas na ação enviada à OCI e no estado que exigem.

Nenhum executa direto. A prévia existe para que a decisão seja tomada com o
estado real da máquina à vista, não de memória.
"""

from dataclasses import dataclass

import oci

from ....config.settings import settings
from ....oci import compute, metadata
from ....safety import confirmation as conf
from .. import formatter as fmt


@dataclass(frozen=True)
class AcaoEnergia:
    comando: str
    acao_oci: str
    emoji: str
    titulo: str
    # Estados em que a ação faz sentido. Pedir para parar uma máquina já
    # parada é engano, não intenção.
    estados_validos: tuple[str, ...]
    estado_resultante: str
    consequencia: str


ACOES: dict[str, AcaoEnergia] = {
    "/suspender": AcaoEnergia(
        comando="/suspender",
        acao_oci="SOFTSTOP",
        emoji="🛑",
        titulo="Suspender instância",
        estados_validos=("RUNNING",),
        estado_resultante="STOPPED",
        consequencia="A máquina desliga. Nada roda enquanto estiver parada.",
    ),
    "/reiniciar": AcaoEnergia(
        comando="/reiniciar",
        acao_oci="SOFTRESET",
        emoji="🔄",
        titulo="Reiniciar instância",
        estados_validos=("RUNNING",),
        estado_resultante="RUNNING",
        consequencia="A máquina reinicia e fica indisponível por ~1 minuto.",
    ),
    "/reativar": AcaoEnergia(
        comando="/reativar",
        acao_oci="START",
        emoji="▶️",
        titulo="Ligar instância",
        estados_validos=("STOPPED",),
        estado_resultante="RUNNING",
        consequencia="A máquina liga e os serviços sobem conforme configurado.",
    ),
}


async def _avisos(acao: AcaoEnergia, estado_atual: str) -> list[str]:
    """Riscos que dependem de onde o Relay roda e de como a rede está."""
    avisos = []

    # Parar a máquina que hospeda o bot o mata junto: não sobra ninguém
    # para religá-la pelo Telegram.
    if acao.estado_resultante == "STOPPED":
        if await metadata.rodando_na_instancia_alvo():
            avisos.append(
                f"{fmt.CRITICO} O Relay roda **nesta** instância. Após parar, "
                "o bot fica fora do ar e só o console da OCI religa.")

        try:
            ips = await compute.get_instance_ips()
            if ips.get("public_ip"):
                avisos.append(
                    f"{fmt.AVISO} Se o IP público for efêmero, ele muda ao "
                    f"religar. Atual: {ips['public_ip']}")
        except Exception:
            # Aviso é complemento; não pode impedir a ação.
            pass

    return avisos


async def pedir_confirmacao(client, token: str, chat_id: int,
                            actor_id: int | None, comando: str):
    """Valida o pré-voo e envia a prévia com os botões de decisão."""
    from ..adapter import tg_send_confirmation, tg_send_text

    acao = ACOES[comando]

    if actor_id is None:
        await tg_send_text(client, token, chat_id,
            f"{fmt.CRITICO} Não foi possível identificar quem pediu a ação.")
        return

    if not settings.oci_configured:
        await tg_send_text(client, token, chat_id,
            f"{acao.emoji} **{acao.titulo}**\n\n"
            f"{fmt.NEUTRO} OCI não configurada.")
        return

    try:
        status = await compute.get_instance_status()
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"{acao.emoji} **{acao.titulo}**\n\n"
            f"{fmt.CRITICO} HTTP {e.status} — {e.message}")
        return

    # Pré-voo: o estado atual precisa admitir a ação.
    if status.state not in acao.estados_validos:
        esperados = " ou ".join(acao.estados_validos)
        await tg_send_text(client, token, chat_id, "\n".join([
            fmt.titulo(acao.emoji, acao.titulo),
            "",
            f"{fmt.NEUTRO} A instância está **{status.state}**, e esta ação "
            f"só se aplica quando está **{esperados}**.",
        ]))
        return

    confirmacao = conf.criar(
        actor_id=actor_id,
        chat_id=chat_id,
        comando=comando,
        alvo=settings.oci_instance_ocid,
    )

    partes = [
        fmt.titulo(acao.emoji, acao.titulo),
        "",
        fmt.tabela([
            ("Instância", status.display_name or "n/d"),
            ("Estado", f"{fmt.emoji_estado_oci(status.state)} {status.state}"),
            ("Ação", acao.acao_oci),
            ("Resultado", acao.estado_resultante),
        ]),
        acao.consequencia,
    ]

    avisos = await _avisos(acao, status.state)
    if avisos:
        partes.append("")
        partes += avisos

    partes += [
        "",
        f"__Confirme em até {confirmacao.segundos_restantes}s.__",
    ]

    await tg_send_confirmation(client, token, chat_id, "\n".join(partes),
                               confirmacao.nonce)


async def executar(confirmacao) -> str:
    """Envia a ação à OCI depois da confirmação aprovada."""
    acao = ACOES[confirmacao.comando]

    request_id = await compute.instance_action(acao.acao_oci)

    linhas = [
        fmt.titulo(acao.emoji, acao.titulo),
        "",
        f"{fmt.OK} {acao.acao_oci} enviado para a OCI.",
        "",
        f"A instância vai para **{acao.estado_resultante}**. "
        "A transição leva alguns instantes; confira com /status.",
    ]
    if request_id:
        # Amarra esta execução ao registro correspondente no Audit da OCI.
        linhas += ["", f"__opc-request-id: {request_id}__"]

    return "\n".join(linhas)
