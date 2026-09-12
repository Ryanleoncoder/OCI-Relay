"""Configuração de rede da instância: VCN, subnet e regras de acesso.

Somente leitura. Mutar regra de rede é operação perigosa — uma linha errada
numa security list abre a máquina para a internet ou derruba o próprio SSH —
e por isso não faz parte desta versão.
"""

import asyncio

from ..config.settings import settings
from .auth import get_compute_client, get_network_client

# A OCI usa o número de protocolo da IANA; "all" quando não restringe.
_PROTOCOLOS = {"1": "ICMP", "6": "TCP", "17": "UDP", "58": "ICMPv6", "all": "all"}

# Marcador para regra sem restrição de porta. O handler o traduz; a
# camada de dados não conhece idioma.
TODAS_AS_PORTAS = "*"

# Origens que aceitam tráfego de qualquer lugar da internet.
_ABERTO_AO_MUNDO = {"0.0.0.0/0", "::/0"}


def protocolo(numero: str | None) -> str:
    """Nome legível do protocolo."""
    return _PROTOCOLOS.get(str(numero), str(numero or "?"))


def _faixa_de_portas(regra) -> str:
    """Portas de destino de uma regra TCP ou UDP."""
    for atributo in ("tcp_options", "udp_options"):
        opcoes = getattr(regra, atributo, None)
        faixa = getattr(opcoes, "destination_port_range", None) if opcoes else None
        if faixa:
            if faixa.min == faixa.max:
                return str(faixa.min)
            return f"{faixa.min}-{faixa.max}"
    return TODAS_AS_PORTAS


def _regra_entrada(regra) -> dict:
    origem = regra.source or "?"
    return {
        "origem": origem,
        "protocolo": protocolo(regra.protocol),
        "portas": _faixa_de_portas(regra),
        "aberta": origem in _ABERTO_AO_MUNDO,
    }


def _coletar() -> dict:
    """Topologia e regras de rede da instância. Chamada bloqueante."""
    compute = get_compute_client()
    rede = get_network_client()

    instancia = compute.get_instance(settings.oci_instance_ocid).data
    anexos = compute.list_vnic_attachments(
        compartment_id=instancia.compartment_id,
        instance_id=settings.oci_instance_ocid,
    ).data

    vnic = next(
        (v for v in (rede.get_vnic(a.vnic_id).data for a in anexos)
         if v.is_primary),
        None,
    )
    if vnic is None:
        return {}

    subnet = rede.get_subnet(vnic.subnet_id).data
    vcn = rede.get_vcn(subnet.vcn_id).data
    compartimento = instancia.compartment_id

    entradas = []
    saidas = 0
    for sl_id in (subnet.security_list_ids or []):
        sl = rede.get_security_list(sl_id).data
        entradas += [_regra_entrada(r) for r in (sl.ingress_security_rules or [])]
        saidas += len(sl.egress_security_rules or [])

    rotas = []
    if subnet.route_table_id:
        tabela = rede.get_route_table(subnet.route_table_id).data
        rotas = [r.destination for r in (tabela.route_rules or [])]

    nsgs = [
        rede.get_network_security_group(n).data.display_name
        for n in (vnic.nsg_ids or [])
    ]

    return {
        "vcn": {"nome": vcn.display_name, "cidr": vcn.cidr_block},
        "subnet": {
            "nome": subnet.display_name,
            "cidr": subnet.cidr_block,
            "publica": not subnet.prohibit_public_ip_on_vnic,
        },
        "ips": {"publico": vnic.public_ip, "privado": vnic.private_ip},
        "entradas": entradas,
        "saidas": saidas,
        "rotas": rotas,
        "nsgs": nsgs,
        "compartimento": compartimento,
    }


async def get_network_config() -> dict:
    """Configuração de rede da instância."""
    return await asyncio.to_thread(_coletar)
