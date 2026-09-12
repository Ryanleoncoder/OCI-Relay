"""Handler /network."""

import oci

from ....oci import network
from .. import formatter as fmt


async def handle(client, token: str, chat_id: int,
                 actor_id: int | None = None):
    """Envia a configuração de rede da instância vista pela OCI."""
    from ..adapter import tg_send_text

    try:
        cfg = await network.get_network_config()

        if not cfg:
            await tg_send_text(client, token, chat_id,
                f"🌐 **Network**\n\n{fmt.NEUTRO} Nenhuma VNIC primária encontrada.")
            return

        entradas = cfg["entradas"]
        abertas = [r for r in entradas if r["aberta"]]
        e_exposicao = fmt.AVISO if abertas else fmt.OK

        partes = [
            fmt.titulo("🌐", "Network"),
            "",
            fmt.tabela([
                ("VCN", f"{cfg['vcn']['nome']}  {cfg['vcn']['cidr']}"),
                ("Subnet", f"{cfg['subnet']['nome']}  {cfg['subnet']['cidr']}"),
                ("Tipo", "pública" if cfg["subnet"]["publica"] else "privada"),
                ("IP público", cfg["ips"]["publico"] or "nenhum"),
                ("IP privado", cfg["ips"]["privado"] or "n/d"),
            ]),
        ]

        if entradas:
            partes.append(fmt.secao(f"Entrada ({len(entradas)} regras)"))
            partes.append(fmt.bloco([
                f"{fmt.AVISO if r['aberta'] else fmt.OK} "
                f"{r['origem']:<18} {r['protocolo']:<6} {r['portas']}"
                for r in entradas[:15]
            ]))

        partes.append(fmt.tabela([
            ("Regras de saída", str(cfg["saidas"])),
            ("Rotas", ", ".join(cfg["rotas"]) or "nenhuma"),
            ("NSGs", ", ".join(cfg["nsgs"]) or "nenhum"),
        ]))

        if abertas:
            # Protocolo junto da porta: "ICMP todas" e "TCP 22" são coisas
            # bem diferentes, e listar só as portas confunde as duas.
            descricoes = sorted({
                r["protocolo"] if r["portas"] == "todas"
                else f"{r['protocolo']} {r['portas']}"
                for r in abertas
            })
            partes.append(
                f"{fmt.AVISO} Aberto a qualquer origem: "
                f"{', '.join(descricoes)}.")

        partes.append(f"Overall: {fmt.veredito(e_exposicao)}")

        await tg_send_text(client, token, chat_id, "\n".join(partes))
    except oci.exceptions.ServiceError as e:
        await tg_send_text(client, token, chat_id,
            f"🌐 **Network**\n\n{fmt.CRITICO} HTTP {e.status} — {e.message}")
    except Exception as e:
        await tg_send_text(client, token, chat_id, f"Erro ao obter rede: {e}")
