"""Integração OCI."""

from .auth import (
    get_auth,
    get_compute_client,
    get_identity_client,
    get_network_client,
    validate_auth,
)
from .compute import get_instance_status
from .network import get_network_config
from .metadata import get_local_instance_id, rodando_na_instancia_alvo

__all__ = [
    "get_auth",
    "get_compute_client",
    "get_identity_client",
    "get_network_client",
    "validate_auth",
    "get_instance_status",
    "get_local_instance_id",
    "rodando_na_instancia_alvo",
    "get_network_config",
]
