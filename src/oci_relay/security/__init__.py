"""Segurança (Fail2Ban, SSH, ports)."""

from .ports import (
    get_listening_ports,
    get_listening_ports_summary,
    identificacao_limitada,
)
from .security import get_fail2ban_status, get_ssh_failures

__all__ = [
    "get_listening_ports",
    "get_listening_ports_summary",
    "identificacao_limitada",
    "get_fail2ban_status",
    "get_ssh_failures",
]
