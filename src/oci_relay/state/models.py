"""Modelos de dados."""

from dataclasses import dataclass


@dataclass
class Baseline:
    """Baseline de configuração conhecida."""
    ocpus: int
    memory_gb: int
    shape: str
    public_ip: str
    critical_services: list[str]
    allowed_ports: list[int]


@dataclass
class Alert:
    """Alerta."""
    type: str
    level: str
    message: str
