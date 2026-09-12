"""Métricas da instância via OCI Monitoring.

O plugin "Compute Instance Monitoring" publica as métricas da máquina no
namespace `oci_computeagent`, e o Relay as consulta pela API — sem precisar
estar dentro da instância.

A granularidade mínima é de 1 minuto e a publicação tem atraso de alguns
minutos, então os valores não são instantâneos como os do psutil.
"""

import asyncio
import datetime as dt
import logging

import oci

from ..config.settings import settings
from .auth import get_monitoring_client

log = logging.getLogger(__name__)

NAMESPACE = "oci_computeagent"

# Cada métrica precisa da agregação certa:
#   gauge   -> valor instantâneo (percentual, load). Usa mean().
#   counter -> acumulado desde o boot. Precisa de rate(), que devolve a
#              derivada em unidades por segundo. Usar mean() aqui renderia
#              o total histórico (centenas de GB) no lugar da taxa.
_METRICAS = {
    "cpu": ("CpuUtilization", "mean"),
    "memory": ("MemoryUtilization", "mean"),
    "load": ("LoadAverage", "mean"),
    "disk_read": ("DiskBytesRead", "rate"),
    "disk_write": ("DiskBytesWritten", "rate"),
    "net_in": ("NetworksBytesIn", "rate"),
    "net_out": ("NetworksBytesOut", "rate"),
}

# Métricas cujo valor sai em bytes por segundo.
TAXAS_BYTES = {"disk_read", "disk_write", "net_in", "net_out"}


def _compartimento() -> str:
    """Compartment para a consulta; cai na tenancy se não configurado."""
    return settings.oci_compartment_ocid or settings.oci_tenancy_ocid


def _consultar(nome_metrica: str, agregacao: str, minutos: int) -> list:
    """Série temporal de uma métrica para esta instância."""
    fim = dt.datetime.now(dt.timezone.utc)
    inicio = fim - dt.timedelta(minutes=minutos)

    consulta = (f'{nome_metrica}[1m]{{resourceId = '
                f'"{settings.oci_instance_ocid}"}}.{agregacao}()')

    detalhes = oci.monitoring.models.SummarizeMetricsDataDetails(
        namespace=NAMESPACE,
        query=consulta,
        start_time=inicio,
        end_time=fim,
    )

    resultado = get_monitoring_client().summarize_metrics_data(
        compartment_id=_compartimento(),
        summarize_metrics_data_details=detalhes,
    ).data

    if not resultado:
        return []
    return resultado[0].aggregated_datapoints or []


def _ultimo_valor(nome_metrica: str, agregacao: str,
                  minutos: int = 15) -> float | None:
    """Ponto mais recente de uma métrica, ou None se não houver dado."""
    try:
        pontos = _consultar(nome_metrica, agregacao, minutos)
    except oci.exceptions.ServiceError as e:
        log.warning("Monitoring %s: HTTP %s %s", nome_metrica, e.status, e.code)
        return None
    except Exception as e:
        log.warning("Monitoring %s: %s", nome_metrica, e)
        return None

    if not pontos:
        return None
    return pontos[-1].value


def _coletar(minutos: int) -> dict:
    """Lê todas as métricas de interesse. Chamada bloqueante."""
    return {
        chave: _ultimo_valor(metrica, agregacao, minutos)
        for chave, (metrica, agregacao) in _METRICAS.items()
    }


async def get_instance_metrics(minutos: int = 15) -> dict:
    """Métricas mais recentes da instância, lidas do OCI Monitoring."""
    return await asyncio.to_thread(_coletar, minutos)


async def get_metric_series(chave: str, minutos: int = 60) -> list:
    """Série temporal de uma métrica, para gráficos ou janelas de alerta."""
    entrada = _METRICAS.get(chave)
    if not entrada:
        raise ValueError(f"métrica desconhecida: {chave}")

    metrica, agregacao = entrada
    pontos = await asyncio.to_thread(_consultar, metrica, agregacao, minutos)
    return [(p.timestamp, p.value) for p in pontos]
