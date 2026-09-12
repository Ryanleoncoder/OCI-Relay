"""Registro de comandos: fonte única para menu, ajuda e roteamento.

O menu do Telegram, o texto da ajuda e o despacho derivam desta lista. Sem
isso, listas paralelas divergem em silêncio — o comando responde mas não
aparece na ajuda, ou é anunciado no menu e não responde.

O handler é uma referência de módulo, não um nome em texto: erro de
digitação vira falha de import, detectada pelos testes, em vez de surpresa
quando alguém manda o comando.
"""

from dataclasses import dataclass
from typing import Callable, Iterable

from .handlers import (
    alerts, cpu, disk, docker, fail2ban, health, memory, network, oci_ip,
    ports, reiniciar, security, services, sessions, status,
    summary, suspender, top, usage, watch,
)


@dataclass(frozen=True)
class Comando:
    nome: str
    descricao: str
    handler: Callable | None = None   # None = tratado pelo próprio adapter
    oculto: bool = False              # fora do menu e da ajuda


COMANDOS: tuple[Comando, ...] = (
    Comando("start", "Iniciar conversa"),
    Comando("help", "Listar comandos disponíveis"),

    Comando("summary", "Resumo rápido do sistema", summary.handle),
    Comando("status", "Estado da instância OCI", status.handle),
    Comando("usage", "Custo reportado da tenancy", usage.handle),
    Comando("oci_ip", "IPs público e privado da VPS", oci_ip.handle),
    Comando("network", "VCN, subnet e regras de acesso", network.handle),
    Comando("health", "Saúde da VPS (OCI Monitoring)", health.handle),

    Comando("cpu", "Uso de CPU", cpu.handle),
    Comando("memory", "Uso de RAM", memory.handle),
    Comando("disk", "Uso de disco", disk.handle),
    Comando("top", "Processos que mais consomem", top.handle),

    Comando("docker", "Status dos containers", docker.handle),
    Comando("services", "Serviços systemd", services.handle),
    Comando("security", "Dashboard de segurança", security.handle),
    Comando("ports", "Portas escutando", ports.handle),
    Comando("fail2ban", "Status do Fail2Ban", fail2ban.handle),
    Comando("sessions", "Sessões SSH ativas", sessions.handle),

    Comando("alerts", "Configuração de alertas", alerts.handle),
    Comando("watch", "Monitoramentos ativos", watch.handle),
    Comando("suspender", "Suspender instância (com confirmação)", suspender.handle),
    Comando("reiniciar", "Reiniciar instância (com confirmação)", reiniciar.handle),
)

# Despacho por nome, montado uma vez.
POR_NOME: dict[str, Comando] = {c.nome: c for c in COMANDOS}


def visiveis() -> Iterable[Comando]:
    return (c for c in COMANDOS if not c.oculto)


def para_telegram() -> list[dict]:
    """Payload do setMyCommands."""
    return [{"command": c.nome, "description": c.descricao} for c in visiveis()]


def texto_de_ajuda() -> str:
    """Lista de comandos usada por /start e /help."""
    linhas = [f"/{c.nome} — {c.descricao}" for c in visiveis()]
    return "\n".join(linhas)


def buscar(comando: str) -> Comando | None:
    """Resolve '/health' ou 'health' para o comando correspondente."""
    return POR_NOME.get(comando.lstrip("/").lower())
