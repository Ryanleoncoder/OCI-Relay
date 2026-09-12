"""Consulta ao systemd.

Somente leitura. Todas as chamadas usam lista de argumentos fixa e nomes de
unidade que vêm da configuração, nunca do texto de uma mensagem — o bot não
executa comando arbitrário.
"""

import subprocess

_TIMEOUT = 10

# Sem systemd (Windows, macOS, contêiner enxuto) isto é esperado, não erro.
SYSTEMD_AUSENTE = "systemd não disponível neste host"


class SystemdIndisponivel(RuntimeError):
    """Levantada quando o systemctl não existe no host."""


def _systemctl(*args: str) -> str:
    """Executa systemctl e devolve a saída padrão."""
    try:
        resultado = subprocess.run(
            ["systemctl", *args],
            capture_output=True, text=True, timeout=_TIMEOUT,
        )
    except FileNotFoundError as e:
        raise SystemdIndisponivel(SYSTEMD_AUSENTE) from e
    return resultado.stdout


def is_active(unidade: str) -> str:
    """Estado de uma unidade: active, inactive, failed, unknown..."""
    return _systemctl("is-active", unidade).strip() or "unknown"


def _nomes_das_unidades(saida: str) -> list[str]:
    """Primeira coluna de cada linha de `systemctl list-units --plain`."""
    return [
        linha.split()[0]
        for linha in saida.splitlines()
        if linha.strip() and not linha.startswith(("●", "*"))
    ]


def failed_units() -> list[str]:
    """Unidades em estado de falha."""
    return _nomes_das_unidades(
        _systemctl("--failed", "--no-legend", "--plain"))


def running_services() -> list[str]:
    """Serviços em execução, sem o sufixo .service."""
    nomes = _nomes_das_unidades(_systemctl(
        "list-units", "--type=service", "--state=running",
        "--no-legend", "--plain"))
    return sorted(n.removesuffix(".service") for n in nomes)


def get_services_status(criticos: tuple[str, ...]) -> dict:
    """Panorama do systemd: críticos, falhas e serviços ativos."""
    return {
        "criticos": {u: is_active(u) for u in criticos},
        "failed": failed_units(),
        "running": running_services(),
    }
