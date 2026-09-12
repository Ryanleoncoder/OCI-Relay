"""Formatação das mensagens do Telegram.

O adapter converte markdown para HTML e aplica strip() em cada linha, então
alinhamento em colunas só sobrevive dentro de blocos ``` (que viram <pre>).
Use `bloco()` sempre que o alinhamento importar.
"""

import socket

OK = "🟢"
AVISO = "🟡"
CRITICO = "🔴"
NEUTRO = "⚪"

_ESTADOS_OCI = {
    "RUNNING": OK,
    "STOPPED": CRITICO,
    "TERMINATED": CRITICO,
    "TERMINATING": CRITICO,
    "STARTING": AVISO,
    "STOPPING": AVISO,
    "PROVISIONING": AVISO,
    "CREATING_IMAGE": AVISO,
}

_ORDEM = {OK: 0, NEUTRO: 1, AVISO: 2, CRITICO: 3}

_ROTULO = {
    OK: "Healthy",
    NEUTRO: "Unknown",
    AVISO: "Warning",
    CRITICO: "Critical",
}


def emoji_percentual(valor: float | None, aviso: float, critico: float) -> str:
    """Semáforo para uma métrica percentual, conforme os limiares do .env."""
    if valor is None:
        return NEUTRO
    if valor >= critico:
        return CRITICO
    if valor >= aviso:
        return AVISO
    return OK


def emoji_estado_oci(estado: str | None) -> str:
    """Semáforo para o lifecycle_state da instância."""
    if not estado:
        return NEUTRO
    return _ESTADOS_OCI.get(estado.upper(), NEUTRO)


def veredito(*emojis: str) -> str:
    """Pior estado entre os recebidos, já com rótulo. Ex.: '🟡 Warning'."""
    candidatos = [e for e in emojis if e in _ORDEM]
    if not candidatos:
        return f"{NEUTRO} {_ROTULO[NEUTRO]}"
    pior = max(candidatos, key=lambda e: _ORDEM[e])
    return f"{pior} {_ROTULO[pior]}"


def host_local() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "host local"


def titulo(emoji: str, texto: str) -> str:
    return f"{emoji} **{texto}**"


def titulo_local(emoji: str, texto: str) -> str:
    """Cabeçalho de comando que mede a máquina do bot, não a VPS.

    Nomear a máquina evita ler dois comandos seguidos como se falassem do
    mesmo host, quando um mede a VPS e o outro a máquina do bot.
    """
    return f"{emoji} **{texto} — {host_local()}**"


def secao(texto: str) -> str:
    return f"**{texto}**"


def bloco(linhas: list[str]) -> str:
    """Envolve as linhas em ``` para preservar alinhamento no Telegram."""
    corpo = "\n".join(linhas)
    return f"```\n{corpo}\n```"


def tabela(pares: list[tuple[str, str]]) -> str:
    """Bloco de rótulo/valor com os rótulos alinhados."""
    if not pares:
        return ""
    largura = max(len(rotulo) for rotulo, _ in pares)
    return bloco([f"{rotulo:<{largura}}  {valor}" for rotulo, valor in pares])


def uptime(segundos: int | None) -> str:
    """Uptime legível. Ex.: '18d 04h'."""
    if not segundos or segundos < 0:
        return "desconhecido"
    dias, resto = divmod(int(segundos), 86400)
    horas, resto = divmod(resto, 3600)
    minutos = resto // 60
    if dias:
        return f"{dias}d {horas:02d}h"
    if horas:
        return f"{horas}h {minutos:02d}m"
    return f"{minutos}m"


def carga(valores) -> str:
    """Load average. Ex.: '0.82 / 0.64 / 0.51'."""
    if not valores:
        return "n/d"
    return " / ".join(f"{v:.2f}" for v in valores)


def gb(valor: float | None) -> str:
    """Formata gigabytes sem casas desnecessárias."""
    if valor is None:
        return "n/d"
    return f"{valor:.0f}" if float(valor).is_integer() else f"{valor:.1f}"


def nao_implementado(recurso: str) -> str:
    """Resposta padrão dos comandos ainda não implementados."""
    return f"🚧 {recurso} ainda não implementado."
