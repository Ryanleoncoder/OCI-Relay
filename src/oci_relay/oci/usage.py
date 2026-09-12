"""Custo e uso da tenancy via Usage API.

A Usage API não é um feed de cobrança em tempo real: os dados são
consolidados com atraso de horas. Qualquer valor daqui deve ser apresentado
como "reportado até agora", nunca como o custo do instante.
"""

import asyncio
import datetime as dt
import logging

import oci

from ..config.settings import settings
from .auth import get_budget_client, get_usage_client

log = logging.getLogger(__name__)


class Custo:
    """Custo consolidado de um período."""

    def __init__(self, total: float, moeda: str, inicio: dt.datetime,
                 fim: dt.datetime, por_servico: list):
        self.total = total
        self.moeda = moeda
        self.inicio = inicio
        self.fim = fim
        self.por_servico = por_servico


def _inicio_do_mes() -> tuple[dt.datetime, dt.datetime]:
    """Intervalo do mês corrente. A API exige meia-noite UTC nas bordas."""
    agora = dt.datetime.now(dt.timezone.utc)
    meia_noite = agora.replace(hour=0, minute=0, second=0, microsecond=0)
    return meia_noite.replace(day=1), meia_noite + dt.timedelta(days=1)


def _consultar_custo() -> Custo:
    """Custo do mês corrente, agregado por serviço. Chamada bloqueante."""
    inicio, fim = _inicio_do_mes()

    detalhes = oci.usage_api.models.RequestSummarizedUsagesDetails(
        tenant_id=settings.oci_tenancy_ocid,
        time_usage_started=inicio,
        time_usage_ended=fim,
        granularity="MONTHLY",
        query_type="COST",
        group_by=["service"],
    )

    itens = get_usage_client().request_summarized_usages(
        request_summarized_usages_details=detalhes,
    ).data.items or []

    total = 0.0
    moeda = ""
    por_servico: dict[str, float] = {}

    for item in itens:
        valor = item.computed_amount or 0.0
        total += valor
        moeda = moeda or (item.currency or "")

        nome = item.service or "outros"
        por_servico[nome] = por_servico.get(nome, 0.0) + valor

    # Só serviços que de fato custaram algo; o resto é ruído.
    ranking = sorted(
        ((nome, v) for nome, v in por_servico.items() if v > 0),
        key=lambda par: par[1], reverse=True,
    )

    # Sem data de frescor: com granularidade MONTHLY, o time_usage_ended dos
    # itens é o fim do balde do mês, não o instante do último dado coletado.
    return Custo(
        total=round(total, 4),
        moeda=moeda or "USD",
        inicio=inicio,
        fim=fim,
        por_servico=ranking,
    )


async def get_current_period_usage() -> Custo:
    """Custo reportado para o mês corrente."""
    return await asyncio.to_thread(_consultar_custo)


class Budget:
    """Orçamento configurado na OCI."""

    def __init__(self, nome: str, limite: float, gasto: float):
        self.nome = nome
        self.limite = limite
        self.gasto = gasto

    @property
    def percentual(self) -> float | None:
        if not self.limite:
            return None
        return round(self.gasto / self.limite * 100, 1)


def _consultar_budgets() -> list:
    """Orçamentos da tenancy. Nenhum configurado não é erro."""
    try:
        registros = get_budget_client().list_budgets(
            compartment_id=settings.oci_tenancy_ocid,
        ).data or []
    except oci.exceptions.ServiceError as e:
        log.warning("Budgets indisponíveis: HTTP %s %s", e.status, e.code)
        return []

    return [
        Budget(
            nome=b.display_name or "sem nome",
            limite=float(b.amount or 0),
            gasto=float(b.actual_spend or 0),
        )
        for b in registros
    ]


async def get_budgets() -> list:
    """Orçamentos configurados, ou lista vazia."""
    return await asyncio.to_thread(_consultar_budgets)
