"""Identificação da instância que hospeda o Relay.

Toda instância OCI expõe seus próprios metadados num endereço link-local
que só é roteável de dentro dela. Consultá-lo responde a pergunta que o
controle de energia precisa fazer antes de agir: *a máquina que vou desligar
é a mesma em que eu estou rodando?*

Se for, um SOFTSTOP mata o Relay junto e não sobra ninguém para religar a
instância — a recuperação passa a exigir o console da OCI.
"""

import asyncio
import logging

import httpx

from ..config.settings import settings

log = logging.getLogger(__name__)

# Endereço link-local do serviço de metadados. Não é roteável fora da OCI.
URL_METADADOS = "http://169.254.169.254/opc/v2/instance/"

# A v2 exige este cabeçalho fixo; sem ele responde 401.
_CABECALHOS = {"Authorization": "Bearer Oracle"}

# Curto de propósito: fora da OCI o endereço não responde, e o comando que
# depende disso não pode ficar pendurado esperando.
_TIMEOUT = 2.0

# Resolvido uma vez por processo: a instância não muda durante a execução.
_cache: dict = {}


async def get_local_instance_id() -> str | None:
    """OCID da instância onde o Relay roda, ou None se não for uma."""
    if "id" in _cache:
        return _cache["id"]

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(URL_METADADOS, headers=_CABECALHOS)
        ocid = resp.json().get("id") if resp.status_code == 200 else None
    except (httpx.HTTPError, ValueError, asyncio.TimeoutError):
        # Fora da OCI o endereço é inalcançável; não é erro, é informação.
        ocid = None
    except Exception as e:
        log.warning("Metadados da instância indisponíveis: %s", e)
        ocid = None

    _cache["id"] = ocid
    return ocid


async def rodando_na_instancia_alvo() -> bool:
    """Indica se o Relay roda na mesma instância que ele monitora.

    Falso quando o Relay está fora da OCI, ou quando monitora uma instância
    diferente daquela que o hospeda. Na dúvida devolve False, que é o caso
    em que as ações de energia são reversíveis.
    """
    local = await get_local_instance_id()
    if not local or not settings.oci_instance_ocid:
        return False
    return local == settings.oci_instance_ocid


def limpar_cache() -> None:
    """Descarta o OCID memorizado. Existe para os testes."""
    _cache.clear()
