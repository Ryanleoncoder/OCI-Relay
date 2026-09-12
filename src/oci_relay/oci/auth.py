"""Autenticação OCI — Instance Principal (na VPS) ou API Key (fora dela)."""

import logging
from pathlib import Path

import oci

from ..config.settings import settings

log = logging.getLogger(__name__)

# (config, signer) resolvidos uma única vez por processo.
_auth: tuple[dict, object | None] | None = None

# Um OCID tem a forma ocid1.<tipo>.<realm>.<região>.<único>. Conferir o tipo
# transforma um 404 NotAuthorizedOrNotFound (que parece falta de permissão)
# em erro de configuração explícito.
_TIPO_ESPERADO = {
    "OCI_USER_OCID": ("user",),
    "OCI_TENANCY_OCID": ("tenancy",),
    "OCI_INSTANCE_OCID": ("instance",),
    "OCI_COMPARTMENT_OCID": ("compartment", "tenancy"),
}


def _tipo_ocid(valor: str) -> str:
    partes = valor.split(".")
    if len(partes) < 2 or partes[0] != "ocid1":
        return "?"
    return partes[1]


def validar_ocids() -> list[str]:
    """Lista os OCIDs cujo tipo de recurso não corresponde ao campo."""
    atuais = {
        "OCI_USER_OCID": settings.oci_user_ocid,
        "OCI_TENANCY_OCID": settings.oci_tenancy_ocid,
        "OCI_INSTANCE_OCID": settings.oci_instance_ocid,
        "OCI_COMPARTMENT_OCID": settings.oci_compartment_ocid,
    }

    problemas = []
    for chave, valor in atuais.items():
        if not valor:
            continue
        tipo = _tipo_ocid(valor)
        esperados = _TIPO_ESPERADO[chave]
        if tipo not in esperados:
            problemas.append(
                f"{chave} parece um 'ocid1.{tipo}', mas deveria ser "
                f"'ocid1.{esperados[0]}'"
            )
    return problemas


def _build_auth() -> tuple[dict, object | None]:
    """Monta o par (config, signer) conforme o modo configurado.

    Instance Principal só funciona de dentro de uma instância OCI: o signer
    busca um certificado no serviço de metadados. Fora da OCI, use API Key.
    """
    if not settings.oci_configured:
        raise ValueError(
            "OCI não configurada: defina OCI_REGION e OCI_INSTANCE_OCID no .env."
        )

    if settings.oci_use_instance_principal:
        signer = oci.auth.signers.InstancePrincipalsSecurityTokenSigner()
        return {"region": settings.oci_region}, signer

    faltando = [
        nome for nome, valor in (
            ("OCI_USER_OCID", settings.oci_user_ocid),
            ("OCI_TENANCY_OCID", settings.oci_tenancy_ocid),
            ("OCI_FINGERPRINT", settings.oci_fingerprint),
            ("OCI_PRIVATE_KEY_PATH", settings.oci_private_key_path),
        ) if not valor
    ]
    if faltando:
        raise ValueError(
            "Modo API Key exige no .env: " + ", ".join(faltando)
        )

    key_path = Path(settings.oci_private_key_path).expanduser()
    if not key_path.is_file():
        raise FileNotFoundError(
            f"Chave privada OCI não encontrada: {key_path}. "
            "Verifique OCI_PRIVATE_KEY_PATH no .env."
        )

    config = {
        "user": settings.oci_user_ocid,
        "tenancy": settings.oci_tenancy_ocid,
        "fingerprint": settings.oci_fingerprint,
        "key_file": str(key_path),
        "region": settings.oci_region,
    }
    oci.config.validate_config(config)
    return config, None


def get_auth() -> tuple[dict, object | None]:
    """Obtém (config, signer), construindo na primeira chamada."""
    global _auth
    if _auth is None:
        _auth = _build_auth()
    return _auth


def _client_kwargs() -> dict:
    """Argumentos de construção para qualquer client do SDK OCI."""
    config, signer = get_auth()
    if signer is not None:
        return {"config": config, "signer": signer}
    return {"config": config}


def get_compute_client() -> oci.core.ComputeClient:
    return oci.core.ComputeClient(**_client_kwargs())


def get_identity_client() -> oci.identity.IdentityClient:
    return oci.identity.IdentityClient(**_client_kwargs())


def get_network_client() -> oci.core.VirtualNetworkClient:
    return oci.core.VirtualNetworkClient(**_client_kwargs())


def get_monitoring_client() -> oci.monitoring.MonitoringClient:
    return oci.monitoring.MonitoringClient(**_client_kwargs())


def get_usage_client() -> oci.usage_api.UsageapiClient:
    return oci.usage_api.UsageapiClient(**_client_kwargs())


def get_budget_client() -> oci.budget.BudgetClient:
    return oci.budget.BudgetClient(**_client_kwargs())


def validate_auth() -> bool:
    """Valida credenciais lendo a própria instância.

    Uma leitura real cobre de uma vez as credenciais, a policy de leitura
    e o OCID da instância — mais útil que validar só a identidade.
    """
    if not settings.oci_configured:
        log.warning("OCI não configurada (OCI_REGION / OCI_INSTANCE_OCID vazios).")
        return False

    for problema in validar_ocids():
        log.error("Configuração OCI: %s", problema)

    modo = "Instance Principal" if settings.oci_use_instance_principal else "API Key"
    try:
        instance = get_compute_client().get_instance(settings.oci_instance_ocid).data
    except oci.exceptions.ServiceError as e:
        log.error(
            "OCI recusou a chamada (%s): HTTP %s — %s [opc-request-id=%s]",
            modo, e.status, e.message, e.request_id,
        )
        return False
    except Exception as e:
        log.error("Falha ao autenticar na OCI (%s): %s", modo, e)
        return False

    log.info(
        "OCI autenticada via %s — instância '%s' está %s",
        modo, instance.display_name, instance.lifecycle_state,
    )
    return True
