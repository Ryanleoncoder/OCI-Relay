"""Handler /network."""

import oci

from ....i18n import t
from ....oci import network
from ....oci.network import TODAS_AS_PORTAS
from .. import formatter as fmt

_LIMITE_REGRAS = 15


def _portas(regra: dict) -> str:
    """Faixa de portas da regra, com o caso irrestrito traduzido."""
    if regra["portas"] == TODAS_AS_PORTAS:
        return t("network.all_ports")
    return regra["portas"]


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None, args: str = ""):
    """Envia a configuração de rede da instância vista pela OCI."""
    from ..adapter import tg_send_text

    cabecalho = fmt.cabecalho(t("network.title"))

    try:
        cfg = await network.get_network_config()

        if not cfg:
            await tg_send_text(client, token, chat_id,
                f"{cabecalho}\n\n{fmt.NEUTRO} {t('network.no_vnic')}")
            return

        entradas = cfg["entradas"]
        abertas = [r for r in entradas if r["aberta"]]
        tipo = (t("network.public_subnet") if cfg["subnet"]["publica"]
                else t("network.private_subnet"))

        partes = [
            cabecalho,
            "",
            fmt.tabela([
                (t("network.vcn"),
                 f"{cfg['vcn']['nome']}  {cfg['vcn']['cidr']}"),
                (t("network.subnet"),
                 f"{cfg['subnet']['nome']}  {cfg['subnet']['cidr']}"),
                (t("network.kind"), tipo),
                (t("network.public_ip"),
                 cfg["ips"]["publico"] or t("network.no_ip")),
                (t("network.private_ip"), cfg["ips"]["privado"] or "n/d"),
            ]),
        ]

        if entradas:
            partes.append(fmt.secao(t("network.ingress", count=len(entradas))))
            partes.append(fmt.bloco([
                f"{fmt.AVISO if r['aberta'] else fmt.OK} "
                f"{r['origem']:<18} {r['protocolo']:<6} {_portas(r)}"
                for r in entradas[:_LIMITE_REGRAS]
            ]))

        partes.append(fmt.tabela([
            (t("network.egress_rules"), str(cfg["saidas"])),
            (t("network.routes"),
             ", ".join(cfg["rotas"]) or t("network.none")),
            (t("network.nsgs"), ", ".join(cfg["nsgs"]) or t("network.none")),
        ]))

        if abertas:
            # Protocolo junto da porta: "ICMP todas" e "TCP 22" são coisas
            # bem diferentes, e listar só as portas confunde as duas.
            descricoes = sorted({
                r["protocolo"] if r["portas"] == TODAS_AS_PORTAS
                else f"{r['protocolo']} {r['portas']}"
                for r in abertas
            })
            partes.append(t("network.open_to_world", emoji=fmt.AVISO,
                            rules=", ".join(descricoes)))

        e_exposicao = fmt.AVISO if abertas else fmt.OK
        partes.append(f"{t('common.overall')}: {fmt.veredito(e_exposicao)}")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"{cabecalho}\n\n{fmt.CRITICO} "
            + t("errors.oci_refused", status=e.status, message=e.message))
    except Exception as e:
        await tg_send_text(client, token, chat_id,
            t("errors.generic", subject="network", reason=e))
