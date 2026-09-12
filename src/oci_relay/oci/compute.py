"""Operações de computação OCI."""

import asyncio

from ..config.settings import settings
from .auth import get_compute_client, get_network_client


class InstanceStatus:
    def __init__(self, state: str, shape: str, ocpus: float, memory_gb: float,
                 display_name: str = "", region: str = ""):
        self.state = state
        self.shape = shape
        self.ocpus = ocpus
        self.memory_gb = memory_gb
        self.display_name = display_name
        self.region = region


def _fetch_instance():
    return get_compute_client().get_instance(settings.oci_instance_ocid).data


async def get_instance_status() -> InstanceStatus:
    """Obtém status da instância."""
    instance = await asyncio.to_thread(_fetch_instance)

    # shape_config só existe em shapes Flex (ex.: VM.Standard.A1.Flex).
    shape_config = getattr(instance, "shape_config", None)

    return InstanceStatus(
        state=instance.lifecycle_state,
        shape=instance.shape,
        ocpus=getattr(shape_config, "ocpus", None),
        memory_gb=getattr(shape_config, "memory_in_gbs", None),
        display_name=instance.display_name,
        region=instance.region,
    )


def _fetch_ips() -> dict:
    """IPs da VNIC primária da instância."""
    compute = get_compute_client()
    instancia = compute.get_instance(settings.oci_instance_ocid).data

    anexos = compute.list_vnic_attachments(
        compartment_id=instancia.compartment_id,
        instance_id=settings.oci_instance_ocid,
    ).data

    rede = get_network_client()
    for anexo in anexos:
        vnic = rede.get_vnic(anexo.vnic_id).data
        if vnic.is_primary:
            return {
                "public_ip": vnic.public_ip,
                "private_ip": vnic.private_ip,
                "hostname": vnic.hostname_label,
                "nsg_count": len(vnic.nsg_ids or []),
            }
    return {}


async def get_instance_ips() -> dict:
    """Obtém IP público e privado da instância."""
    return await asyncio.to_thread(_fetch_ips)


# Ações de energia que o Relay pode executar. As variantes abruptas — STOP e
# RESET — equivalem a cortar a energia e podem corromper o sistema de
# arquivos, então não são oferecidas.
ACOES_PERMITIDAS = frozenset({"SOFTSTOP", "SOFTRESET", "START"})


def _executar_acao(acao: str):
    return get_compute_client().instance_action(
        settings.oci_instance_ocid, acao)


async def instance_action(acao: str) -> str:
    """Executa uma ação de energia e devolve o opc-request-id.

    O identificador da requisição é o que liga esta chamada ao registro no
    Audit da OCI quando for preciso reconstruir o que aconteceu.
    """
    if acao not in ACOES_PERMITIDAS:
        raise ValueError(f"ação não permitida: {acao}")

    resposta = await asyncio.to_thread(_executar_acao, acao)
    return getattr(resposta, "request_id", "") or ""
