"""Registro de comandos: fonte única para menu, ajuda e roteamento.

O menu do Telegram, o texto da ajuda e o despacho derivam desta lista. Sem
isso, listas paralelas divergem em silêncio — o comando responde mas não
aparece na ajuda, ou é anunciado no menu e não responde.

O handler é uma referência de módulo, não um nome em texto: erro de
digitação vira falha de import, detectada pelos testes, em vez de surpresa
quando alguém manda o comando.
"""

from dataclasses import dataclass, field
from typing import Callable, Iterable

from ...i18n import t as msg

from .handlers import (
    alerts, container, cpu, disk, docker, docker_logs, fail2ban, failed,
    health, language, memory, network, oci_ip, ports, reativar, reiniciar,
    security, services, sessions, shape, status, summary, suspender, top,
    uptime, usage, watch,
)


@dataclass(frozen=True)
class Comando:
    nome: str
    handler: Callable | None = None   # None = tratado pelo próprio adapter
    oculto: bool = False              # fora do menu e da ajuda
    # Nomes antigos que continuam respondendo, sem aparecer no menu.
    apelidos: tuple[str, ...] = field(default_factory=tuple)

    @property
    def descricao(self) -> str:
        """Texto do menu, no idioma da conversa."""
        return msg(f"commands.{self.nome}")


COMANDOS: tuple[Comando, ...] = (
    Comando("start"),
    Comando("help"),
    Comando("language", language.handle),

    Comando("summary", summary.handle),
    Comando("status", status.handle),
    Comando("usage", usage.handle),
    Comando("oci_ip", oci_ip.handle),
    Comando("shape", shape.handle),
    Comando("network", network.handle),
    Comando("health", health.handle),

    Comando("cpu", cpu.handle),
    Comando("memory", memory.handle),
    Comando("disk", disk.handle),
    Comando("top", top.handle),
    Comando("uptime", uptime.handle),

    Comando("docker", docker.handle),
    Comando("services", services.handle),
    Comando("failed", failed.handle),
    Comando("container", container.handle),
    Comando("docker_logs", docker_logs.handle),
    Comando("security", security.handle),
    Comando("ports", ports.handle),
    Comando("fail2ban", fail2ban.handle),
    Comando("sessions", sessions.handle),

    Comando("alerts", alerts.handle),
    Comando("watch", watch.handle),

    # Os nomes em português vieram primeiro e seguem válidos como apelidos:
    # renomear um comando não pode quebrar quem já o digita de memória.
    Comando("stop", suspender.handle, apelidos=("suspender",)),
    Comando("restart", reiniciar.handle, apelidos=("reiniciar",)),
    Comando("poweron", reativar.handle, apelidos=("reativar",)),
)

# Despacho por nome e por apelido, montado uma vez.
POR_NOME: dict[str, Comando] = {}
for _c in COMANDOS:
    POR_NOME[_c.nome] = _c
    for _apelido in _c.apelidos:
        POR_NOME[_apelido] = _c


def visiveis() -> Iterable[Comando]:
    return (c for c in COMANDOS if not c.oculto)


def para_telegram(idioma: str | None = None) -> list[dict]:
    """Payload do setMyCommands, opcionalmente num idioma específico."""
    from ...i18n import definir_idioma, idioma_atual

    if idioma is None:
        return [{"command": c.nome, "description": c.descricao}
                for c in visiveis()]

    anterior = idioma_atual()
    definir_idioma(idioma)
    try:
        return [{"command": c.nome, "description": c.descricao}
                for c in visiveis()]
    finally:
        definir_idioma(anterior)


def texto_de_ajuda() -> str:
    """Lista de comandos usada por /start e /help."""
    linhas = [f"/{c.nome} — {c.descricao}" for c in visiveis()]
    return "\n".join(linhas)


def buscar(comando: str) -> Comando | None:
    """Resolve '/health' ou 'health' para o comando correspondente."""
    return POR_NOME.get(comando.lstrip("/").lower())
