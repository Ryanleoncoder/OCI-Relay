"""Health checks via psutil."""

import time
from datetime import datetime

import psutil

# Janela de amostragem de CPU. psutil precisa de dois pontos no tempo para
# calcular percentual; uma leitura única devolve acumulado desde o boot.
_INTERVALO = 0.5


def get_cpu_usage() -> dict:
    """Obtém uso de CPU."""
    por_nucleo = psutil.cpu_percent(interval=_INTERVALO, percpu=True)
    total = round(sum(por_nucleo) / len(por_nucleo), 1) if por_nucleo else 0.0

    try:
        load_avg = psutil.getloadavg()
    except (AttributeError, OSError):
        load_avg = None

    return {
        "percent": total,
        "per_core": [round(v, 1) for v in por_nucleo],
        "cores": len(por_nucleo),
        "load_avg": load_avg,
    }


def get_memory() -> dict:
    """Obtém uso de memória e swap."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 2),
        "used_gb": round(mem.used / (1024**3), 2),
        "available_gb": round(mem.available / (1024**3), 2),
        "percent": mem.percent,
        "swap_total_gb": round(swap.total / (1024**3), 2),
        "swap_used_gb": round(swap.used / (1024**3), 2),
        "swap_percent": swap.percent,
    }


def get_disk(mount: str = "/") -> dict:
    """Obtém uso de disco de um ponto de montagem."""
    disk = psutil.disk_usage(mount)
    return {
        "mount": mount,
        "total_gb": round(disk.total / (1024**3), 2),
        "used_gb": round(disk.used / (1024**3), 2),
        "free_gb": round(disk.free / (1024**3), 2),
        "percent": disk.percent,
    }


def get_disks() -> list:
    """Obtém uso de todos os pontos de montagem legíveis."""
    discos = []
    for part in psutil.disk_partitions(all=False):
        try:
            uso = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            # Mídia removível ou montagem sem permissão de leitura.
            continue
        discos.append({
            "mount": part.mountpoint,
            "fstype": part.fstype,
            "total_gb": round(uso.total / (1024**3), 2),
            "used_gb": round(uso.used / (1024**3), 2),
            "free_gb": round(uso.free / (1024**3), 2),
            "percent": uso.percent,
        })
    discos.sort(key=lambda d: d["percent"], reverse=True)
    return discos


def get_uptime() -> int:
    """Obtém uptime do sistema em segundos."""
    return int(datetime.now().timestamp() - psutil.boot_time())


def get_health() -> dict:
    """Obtém status de saúde completo."""
    return {
        "cpu": get_cpu_usage(),
        "memory": get_memory(),
        "disk": get_disk(),
        "uptime_seconds": get_uptime(),
    }


def _amostrar_processos() -> list:
    """Coleta CPU e memória de todos os processos visíveis.

    Exige duas leituras de `cpu_percent()` por processo: a primeira apenas
    estabelece a linha de base e sempre retorna 0.0. O percentual é
    normalizado pelo número de núcleos, como no `top`.
    """
    processos = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            proc.cpu_percent()
            processos.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    time.sleep(_INTERVALO)

    nucleos = psutil.cpu_count() or 1
    amostra = []
    for proc in processos:
        try:
            amostra.append({
                "pid": proc.pid,
                "name": proc.name(),
                "cpu_percent": round(proc.cpu_percent() / nucleos, 1),
                "memory_percent": round(proc.memory_percent(), 1),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return amostra


def get_top_processes(limite: int = 10) -> list:
    """Top processos por CPU."""
    amostra = _amostrar_processos()
    amostra.sort(key=lambda p: p["cpu_percent"], reverse=True)
    return amostra[:limite]


def get_top_processes_by_memory(limite: int = 10) -> list:
    """Top processos por memória."""
    amostra = _amostrar_processos()
    amostra.sort(key=lambda p: p["memory_percent"], reverse=True)
    return amostra[:limite]
